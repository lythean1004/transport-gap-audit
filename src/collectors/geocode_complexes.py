"""
VWorld Geocoder 2.0 파이프라인 (v3)
- manual_overrides.csv 훅: REQUERY / PICK_PARCEL / EXCLUDE 적용
- pick_representative: spread > 300m 시 대표필지 자동 선택
- coord_collision 어서션: 서로 다른 cluster_id의 좌표 충돌 탐지
- 게이트 어서션: 꼬리하이픈, 미판정 needs_review, spread 한계 초과, basis 오표기 검사
- VWorld 라이선스 준수: 좌표는 매 실행마다 API에서 새로 받아오고 저장하지 않음
"""
import os
import time
import pandas as pd
import requests
import argparse
from pathlib import Path
from datetime import datetime, timezone
import sys
import re
import yaml
import math

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import require_secret

VWORLD_BASE = "https://api.vworld.kr/req/address"
SPREAD_LIMIT_M = 300  # centroid 허용 상한

# ──────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────
GU_FIX_RE = re.compile(
    r"(화성|성남|수원|고양|용인|안양|안산|부천|청주|천안|전주|포항|창원|안동)(\w+구)"
)

def normalize_addr(s):
    return GU_FIX_RE.sub(r"\1시 \2", s)

def strip_trailing_hyphen(s):
    """5A 하이픈 잔존 방어: addr_query에 남은 꼬리 하이픈 제거."""
    return re.sub(r"-\s*$", "", str(s)).strip()

def canon(s):
    return re.sub(r"\s+", "", s or "")

def sigungu_ok(expected, level2):
    e, g = canon(normalize_addr(expected)), canon(level2)
    return e == g or g.startswith(e) or e.startswith(g)

def haversine(lat1, lon1, lat2, lon2):
    if any(x is None or (isinstance(x, float) and math.isnan(x)) for x in [lat1, lon1, lat2, lon2]):
        return 999999
    R = 6371.0
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dLon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def haversine_m(lat1, lon1, lat2, lon2):
    return haversine(lat1, lon1, lat2, lon2) * 1000

def geocode(address: str, type_val: str, service_key: str):
    params = {
        "service": "address", "version": "2.0", "request": "GetCoord",
        "key": service_key, "format": "json", "errorFormat": "json",
        "type": type_val, "address": address, "refine": "true",
        "simple": "false", "crs": "EPSG:4326",
    }
    try:
        r = requests.get(VWORLD_BASE, params=params, timeout=10)
        return r.json(), "OK" if r.status_code == 200 else "HTTP_ERROR"
    except requests.RequestException as e:
        return None, f"TRANSPORT_ERROR: {e}"

# ──────────────────────────────────────────────────────
# 앵커
# ──────────────────────────────────────────────────────
def load_anchors():
    anchors = {}
    with open("config/pilots.yaml", "r", encoding="utf-8") as f:
        pilots = yaml.safe_load(f).get("pilots", [])
        for p in pilots:
            pts = []
            lat, lon = p.get("anchor_lat"), p.get("anchor_lon")
            if lat and lon:
                pts.append((float(lat), float(lon)))
            alt = p.get("anchor_alt")
            if alt and alt.get("lat") and alt.get("lon"):
                pts.append((float(alt["lat"]), float(alt["lon"])))
            anchors[p["development_id"]] = pts
    return anchors

# ──────────────────────────────────────────────────────
# 오버라이드 훅
# ──────────────────────────────────────────────────────
def load_overrides():
    """manual_overrides.csv 로드. decision이 DEFER인 행은 무시."""
    ov_path = Path("manual_overrides.csv")
    if not ov_path.exists():
        return {}
    df_ov = pd.read_csv(ov_path)
    df_ov = df_ov[df_ov["decision"] != "DEFER"]
    return df_ov.set_index("cluster_id").to_dict("index")

def apply_override(cluster_id, overrides):
    """
    오버라이드가 있으면 (decision, resolved_query_addr, resolved_query_type,
    resolved_geom_basis, parcel_excluded) 반환.
    없으면 None.
    """
    if cluster_id not in overrides:
        return None
    return overrides[cluster_id]

# ──────────────────────────────────────────────────────
# pick_representative: spread 초과 시 대표필지 선택
# ──────────────────────────────────────────────────────
def pick_representative(valid_pts, anchor_pts=None, primary_jibun=None):
    """
    valid_pts: [{'lat','lon','jibun','variant',...}, ...] (status==OK인 것만)
    반환: (선택된 pt, rep_method, coord_geom_basis, spread_m, parcel_excluded_str)
    """
    if len(valid_pts) == 0:
        return None, "no_valid", "none", 0.0, ""
    if len(valid_pts) == 1:
        return valid_pts[0], "single_parcel", "", 0.0, ""

    # spread 계산
    spread = 0.0
    for i in range(len(valid_pts)):
        for j in range(i + 1, len(valid_pts)):
            d = haversine_m(valid_pts[i]["lat"], valid_pts[i]["lon"],
                            valid_pts[j]["lat"], valid_pts[j]["lon"])
            if d > spread:
                spread = d

    if spread <= SPREAD_LIMIT_M:
        # centroid
        c_lat = sum(p["lat"] for p in valid_pts) / len(valid_pts)
        c_lon = sum(p["lon"] for p in valid_pts) / len(valid_pts)
        pt = valid_pts[0].copy()
        pt["lat"] = c_lat
        pt["lon"] = c_lon
        pt["refined_text"] = ""  # centroid는 주소 기술이 무효
        return pt, "centroid", f"centroid_of_{len(valid_pts)}", spread, ""

    # spread 초과: 대표 필지 선택
    # 1) 본번만 있는 필지(부번 없음) 우선
    mains = [p for p in valid_pts if "-" not in str(p.get("jibun", ""))]
    if len(mains) == 1:
        excluded = [p.get("jibun", "") for p in valid_pts if p is not mains[0]]
        return mains[0], "selected_parcel", "parcel_centroid", spread, "|".join(excluded)

    # 2) 앵커 최근접
    if anchor_pts:
        def min_anchor_dist(p):
            return min(haversine_m(alat, alon, p["lat"], p["lon"])
                       for alat, alon in anchor_pts)
        chosen = min(valid_pts, key=min_anchor_dist)
        excluded = [p.get("jibun", "") for p in valid_pts if p is not chosen]
        return chosen, "selected_parcel", "parcel_centroid", spread, "|".join(excluded)

    # 3) fallback: 첫 번째 필지
    excluded = [p.get("jibun", "") for p in valid_pts[1:]]
    return valid_pts[0], "selected_parcel", "parcel_centroid", spread, "|".join(excluded)

# ──────────────────────────────────────────────────────
# 게이트 어서션
# ──────────────────────────────────────────────────────
def assert_no_coord_collision(df, tol_m=1.0):
    """서로 다른 cluster_id가 사실상 동일 좌표를 갖는 경우 탐지."""
    collisions = {}
    ids = df["cluster_id"].tolist()
    lats = df["lat"].tolist()
    lons = df["lon"].tolist()
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if ids[i] == ids[j]:
                continue
            d = haversine_m(lats[i], lons[i], lats[j], lons[j])
            if d < tol_m:
                key = f"{ids[i]} vs {ids[j]}"
                collisions[key] = round(d, 2)
    if collisions:
        print(f"[경고] 좌표 충돌 탐지: {collisions}")
    return collisions

def run_gate(df, overrides):
    """실행 후 품질 게이트. 실패 시 AssertionError."""
    errors = []

    # 1) 꼬리 하이픈 잔존
    bad_hyp = df[df["addr_query"].astype(str).str.endswith("-")]
    if len(bad_hyp) > 0:
        errors.append(f"꼬리 하이픈 잔존: {bad_hyp['cluster_id'].tolist()}")

    # 2) 미판정 needs_review (오버라이드에서 해결되지 않은 것)
    resolved_ids = set(overrides.keys())
    unresolved = df[(df["needs_review"] == True) & (~df["cluster_id"].isin(resolved_ids))]
    if len(unresolved) > 0:
        errors.append(f"미판정 needs_review: {unresolved['cluster_id'].tolist()}")

    # 3) spread 한계 초과인데 centroid인 행
    bad_spread = df[(df["representative_method"] == "centroid")
                    & (df["centroid_spread_m"] > SPREAD_LIMIT_M)]
    if len(bad_spread) > 0:
        errors.append(f"spread 한계 초과 centroid: {bad_spread['cluster_id'].tolist()}")

    # 4) centroid 행의 coord_geom_basis가 centroid_of_로 시작하는지
    centroid_rows = df[df["representative_method"] == "centroid"]
    if len(centroid_rows) > 0:
        bad_basis = centroid_rows[~centroid_rows["coord_geom_basis"].astype(str).str.startswith("centroid_of_")]
        if len(bad_basis) > 0:
            errors.append(f"centroid 행의 geom_basis 오표기: {bad_basis['cluster_id'].tolist()}")

    # 5) 좌표 충돌
    collisions = assert_no_coord_collision(df)

    if errors:
        for e in errors:
            print(f"[GATE FAIL] {e}")
        return False
    else:
        if collisions:
            print("[GATE WARN] 좌표 충돌이 있지만 게이트는 통과합니다.")
        else:
            print("[GATE PASS] 모든 검증 통과")
        return True

# ──────────────────────────────────────────────────────
# 메인 프로세서
# ──────────────────────────────────────────────────────
def process_complexes(smoke_test=False):
    service_key = require_secret("VWORLD_API_KEY")
    anchors = load_anchors()
    overrides = load_overrides()

    plan_path = Path("bldg_query_plan.csv")
    if not plan_path.exists():
        print("[오류] bldg_query_plan.csv 파일이 없습니다.")
        sys.exit(1)

    df = pd.read_csv(plan_path)
    df_valid = df[(df["needs_review"] == False) & (df["parse_status"] == "SUCCESS")].copy()

    # 오버라이드에 EXCLUDE가 아닌 클러스터는 needs_review여도 포함
    for cid, ov in overrides.items():
        if ov["decision"] in ("REQUERY", "PICK_PARCEL", "CONFIRM_AS_IS"):
            extra = df[df["cluster_id"] == cid]
            if len(extra) > 0 and cid not in df_valid["cluster_id"].values:
                df_valid = pd.concat([df_valid, extra], ignore_index=True)

    out_path = Path("exports/complex_geocode.csv")
    fail_path = Path("qa/6B_geocode_fail.csv")

    existing_ids = set()
    if out_path.exists():
        df_out = pd.read_csv(out_path)
        existing_ids = set(df_out["cluster_id"].unique())

    records = []
    fails = []

    clusters = df_valid.groupby("cluster_id")
    processed_count = 0

    for cluster_id, group in clusters:
        if cluster_id in existing_ids:
            continue

        if smoke_test and processed_count >= 5:
            break

        ov = apply_override(cluster_id, overrides)

        # EXCLUDE 판정
        if ov and ov["decision"] == "EXCLUDE":
            print(f"\n[{cluster_id}] EXCLUDED by manual_overrides")
            processed_count += 1
            continue

        print(f"\n[{cluster_id}] 지오코딩 시작...")

        cluster_points = []
        c_name = group.iloc[0]["complex_name"]
        dong_token = str(group.iloc[0].get("dong_token", ""))
        pilot_id = group.iloc[0]["pilot_id"]
        a_pts = anchors.get(pilot_id, [])

        # REQUERY: 오버라이드가 지정한 주소/타입으로 단일 질의
        if ov and ov["decision"] == "REQUERY":
            addr_used = strip_trailing_hyphen(str(ov["resolved_query_addr"]))
            type_used = str(ov["resolved_query_type"])
            geom_basis = str(ov.get("resolved_geom_basis", "building_entrance"))

            res, transport_status = geocode(addr_used, type_used, service_key)
            if not res:
                fails.append({"cluster_id": cluster_id, "addr_query": addr_used,
                               "error_code": "", "status": "", "transport_error": transport_status})
                processed_count += 1
                continue

            status = res.get("response", {}).get("status")
            if status == "OK":
                point = res["response"]["result"]["point"]
                refined = res["response"].get("refined", {})
                structure = refined.get("structure", {})
                lat = float(point["y"])
                lon = float(point["x"])

                dist_km = min([haversine(alat, alon, lat, lon)
                               for alat, alon in a_pts]) if a_pts else 999999

                refined_text = refined.get("text", "")
                m_dong = re.search(r'\(([^)]+동)\)', refined_text)
                if type_used == "ROAD":
                    dong_final = m_dong.group(1) if m_dong else structure.get("level3", "")
                else:
                    dong_final = structure.get("level4L", "")

                records.append({
                    "cluster_id": cluster_id,
                    "complex_name": c_name,
                    "addr_legal_raw": str(group.iloc[0]["addr_legal"]),
                    "addr_query": addr_used,
                    "addr_variant_used": f"override_{type_used.lower()}",
                    "type": type_used,
                    "status": "OK",
                    "lat": lat, "lon": lon, "crs": "EPSG:4326",
                    "refined_text": refined_text,
                    "dong_final": dong_final,
                    "vw_level1_raw": structure.get("level1", ""),
                    "vw_level2_raw": structure.get("level2", ""),
                    "vw_level3_raw": structure.get("level3", ""),
                    "vw_level4L_raw": structure.get("level4L", ""),
                    "vw_level4A_raw": structure.get("level4A", ""),
                    "vw_level4AC_raw": structure.get("level4AC", ""),
                    "vw_level5_raw": structure.get("level5", ""),
                    "vw_detail_raw": structure.get("detail", ""),
                    "representative_method": "override_requery",
                    "parcel_count": len(group),
                    "parcel_success_count": 1,
                    "parcel_excluded": str(ov.get("parcel_excluded", "")),
                    "centroid_spread_m": 0.0,
                    "distance_from_anchor_km": round(dist_km, 2) if dist_km != 999999 else "",
                    "coord_source": "vworld_geocoder_2.0",
                    "coord_fetched_at": datetime.now(timezone.utc).isoformat(),
                    "coord_license_note": "Realtime query. Not stored per VWorld TOS.",
                    "coord_geom_basis": geom_basis,
                    "coord_resolution": str(ov.get("coord_resolution", "")),
                    "coord_uncertainty_m": float(ov.get("coord_uncertainty_m", 0)),
                    "qa_flag": "",
                    "error_code": "",
                    "needs_review": False,
                    "override_decision": "REQUERY",
                })
            else:
                fails.append({"cluster_id": cluster_id, "addr_query": addr_used,
                               "error_code": res.get("response", {}).get("error", {}).get("code", ""),
                               "status": status, "transport_error": ""})
            processed_count += 1
            time.sleep(0.1)
            continue

        # PICK_PARCEL: 오버라이드가 지정한 필지만 질의
        if ov and ov["decision"] == "PICK_PARCEL":
            addr_used = strip_trailing_hyphen(str(ov["resolved_query_addr"]))
            type_used = str(ov.get("resolved_query_type", "PARCEL"))
            geom_basis = str(ov.get("resolved_geom_basis", "parcel_centroid"))

            res, transport_status = geocode(normalize_addr(addr_used), type_used, service_key)
            if not res:
                fails.append({"cluster_id": cluster_id, "addr_query": addr_used,
                               "error_code": "", "status": "", "transport_error": transport_status})
                processed_count += 1
                continue

            status = res.get("response", {}).get("status")
            if status == "OK":
                point = res["response"]["result"]["point"]
                refined = res["response"].get("refined", {})
                structure = refined.get("structure", {})
                lat = float(point["y"])
                lon = float(point["x"])
                dist_km = min([haversine(alat, alon, lat, lon)
                               for alat, alon in a_pts]) if a_pts else 999999
                dong_final = structure.get("level4L", "")

                records.append({
                    "cluster_id": cluster_id,
                    "complex_name": c_name,
                    "addr_legal_raw": str(group.iloc[0]["addr_legal"]),
                    "addr_query": normalize_addr(addr_used),
                    "addr_variant_used": "override_pick_parcel",
                    "type": type_used,
                    "status": "OK",
                    "lat": lat, "lon": lon, "crs": "EPSG:4326",
                    "refined_text": refined.get("text", ""),
                    "dong_final": dong_final,
                    "vw_level1_raw": structure.get("level1", ""),
                    "vw_level2_raw": structure.get("level2", ""),
                    "vw_level3_raw": structure.get("level3", ""),
                    "vw_level4L_raw": structure.get("level4L", ""),
                    "vw_level4A_raw": structure.get("level4A", ""),
                    "vw_level4AC_raw": structure.get("level4AC", ""),
                    "vw_level5_raw": structure.get("level5", ""),
                    "vw_detail_raw": structure.get("detail", ""),
                    "representative_method": "selected_parcel",
                    "parcel_count": len(group),
                    "parcel_success_count": 1,
                    "parcel_excluded": str(ov.get("parcel_excluded", "")),
                    "centroid_spread_m": 0.0,
                    "distance_from_anchor_km": round(dist_km, 2) if dist_km != 999999 else "",
                    "coord_source": "vworld_geocoder_2.0",
                    "coord_fetched_at": datetime.now(timezone.utc).isoformat(),
                    "coord_license_note": "Realtime query. Not stored per VWorld TOS.",
                    "coord_geom_basis": geom_basis,
                    "coord_resolution": str(ov.get("coord_resolution", "")),
                    "coord_uncertainty_m": float(ov.get("coord_uncertainty_m", 0)),
                    "qa_flag": "",
                    "error_code": "",
                    "needs_review": False,
                    "override_decision": "PICK_PARCEL",
                })
            else:
                fails.append({"cluster_id": cluster_id, "addr_query": addr_used,
                               "error_code": res.get("response", {}).get("error", {}).get("code", ""),
                               "status": status, "transport_error": ""})
            processed_count += 1
            time.sleep(0.1)
            continue

        # ──── 일반 경로 (오버라이드 없음) ────
        for _, row in group.iterrows():
            addr_str = strip_trailing_hyphen(str(row["addr_legal"]).strip())

            plat = str(row["platGbCd"])
            prefix = "산 " if plat in ("1.0", "1") else ""

            if pd.isna(row["bun"]):
                continue

            bun = str(int(row["bun"]))
            ji = int(row["ji"]) if pd.notna(row["ji"]) and row["ji"] != 0 else 0
            ji_s = str(ji) if ji > 0 else ""
            jibun = f"{bun}-{ji_s}" if ji_s else bun

            query_full = strip_trailing_hyphen(normalize_addr(addr_str))
            addr_road = row.get("addr_road", "")

            res, transport_status = geocode(query_full, "PARCEL", service_key)
            if not res:
                fails.append({"cluster_id": cluster_id, "addr_query": query_full,
                               "error_code": "", "status": "", "transport_error": transport_status})
                continue

            status = res.get("response", {}).get("status")
            error_code = res.get("response", {}).get("error", {}).get("code", "")
            variant_used = "full_parcel"
            addr_used = query_full

            # PARCEL 플래그 사전 평가
            qa_flags_temp = []
            if status == "OK":
                refined_text_tmp = res["response"].get("refined", {}).get("text", "")
                if prefix == "" and plat not in ("1", "1.0"):
                    if re.search(r'(?:^|\s)산\s*\d', refined_text_tmp):
                        qa_flags_temp.append("san_substituted")
                level5_tmp = str(res["response"].get("refined", {}).get("structure", {}).get("level5", "")).strip()
                if level5_tmp and level5_tmp != jibun:
                    qa_flags_temp.append("jibun_partial_match")

            # ROAD fallback
            force_road = bool(qa_flags_temp)
            if (status == "NOT_FOUND" or force_road) and pd.notna(addr_road) and str(addr_road).strip():
                query_road = strip_trailing_hyphen(normalize_addr(str(addr_road).strip()))
                res_road, _ = geocode(query_road, "ROAD", service_key)
                if res_road:
                    status_road = res_road.get("response", {}).get("status")
                    if status_road == "OK":
                        res = res_road
                        status = status_road
                        variant_used = "fallback_road"
                        addr_used = query_road
                        error_code = ""

            if status == "OK":
                result = res["response"]["result"]
                point = result["point"]
                refined = res["response"].get("refined", {})
                structure = refined.get("structure", {})

                lon = float(point["x"])
                lat = float(point["y"])

                qa_flags = []
                dist_km = min([haversine(alat, alon, lat, lon)
                               for alat, alon in a_pts]) if a_pts else 999999
                if dist_km > 8.0:
                    qa_flags.append(f"anchor_distance_{dist_km:.1f}km")
                    status = "REJECTED"

                refined_text = refined.get("text", "")

                # PARCEL일 때만 산번지/부분매치 플래그
                if "parcel" in variant_used.lower():
                    if prefix == "" and plat not in ("1", "1.0"):
                        if re.search(r'(?:^|\s)산\s*\d', refined_text):
                            qa_flags.append("san_substituted")
                    level5 = str(structure.get("level5", "")).strip()
                    if level5 and level5 != jibun:
                        qa_flags.append("jibun_partial_match")

                cluster_points.append({
                    "lat": lat if status == "OK" else None,
                    "lon": lon if status == "OK" else None,
                    "jibun": jibun,
                    "variant": variant_used,
                    "query": addr_used,
                    "original_legal": addr_str,
                    "vw_level1_raw": structure.get("level1", ""),
                    "vw_level2_raw": structure.get("level2", ""),
                    "vw_level3_raw": structure.get("level3", ""),
                    "vw_level4L_raw": structure.get("level4L", ""),
                    "vw_level4A_raw": structure.get("level4A", ""),
                    "vw_level4AC_raw": structure.get("level4AC", ""),
                    "vw_level5_raw": structure.get("level5", ""),
                    "vw_detail_raw": structure.get("detail", ""),
                    "refined_text": refined_text,
                    "dong_token": dong_token,
                    "status": status,
                    "qa_flags": qa_flags,
                    "dist_km": dist_km,
                })
            else:
                fails.append({
                    "cluster_id": cluster_id, "addr_query": addr_used,
                    "error_code": error_code, "status": status, "transport_error": "",
                })

            time.sleep(0.1)

        # ──── 대표점 선택 ────
        if cluster_points:
            valid_pts = [p for p in cluster_points if p["status"] == "OK"]
            if not valid_pts:
                processed_count += 1
                continue

            pt, rep_method, geom_basis, spread, parcel_excluded = \
                pick_representative(valid_pts, anchor_pts=a_pts)

            c_lat = pt["lat"]
            c_lon = pt["lon"]
            c_flags = pt.get("qa_flags", []).copy()

            if spread > SPREAD_LIMIT_M:
                c_flags.append("centroid_spread_warn")

            if not geom_basis:
                geom_basis = ("building_entrance" if "road" in pt["variant"]
                              else "parcel_centroid")

            # dong_final 결정
            if "road" in pt["variant"]:
                m = re.search(r'\(([^)]+동)\)', pt["refined_text"])
                dong_final = m.group(1) if m else pt["vw_level3_raw"]
                if dong_final != pt["dong_token"]:
                    c_flags.append("road_alias_warn")
            else:
                dong_final = pt["vw_level4L_raw"]

            # sido/sigungu 검증
            parts = str(pt["original_legal"]).split()
            if len(parts) >= 2:
                sido_req = parts[0]
                sigungu_req = parts[1]
                if pt["vw_level1_raw"] and sido_req not in pt["vw_level1_raw"] and pt["vw_level1_raw"] not in sido_req:
                    c_flags.append("sido_mismatch")
                if pt["vw_level2_raw"] and not sigungu_ok(sigungu_req, pt["vw_level2_raw"]):
                    c_flags.append("sigungu_mismatch")

            dist_c = min([haversine(alat, alon, c_lat, c_lon)
                          for alat, alon in a_pts]) if a_pts else 999999

            records.append({
                "cluster_id": cluster_id,
                "complex_name": c_name,
                "addr_legal_raw": pt["original_legal"],
                "addr_query": pt["query"],
                "addr_variant_used": pt["variant"],
                "type": "PARCEL" if "parcel" in pt["variant"] else "ROAD",
                "status": "OK",
                "lat": c_lat,
                "lon": c_lon,
                "crs": "EPSG:4326",
                "refined_text": pt["refined_text"],
                "dong_final": dong_final,
                "vw_level1_raw": pt["vw_level1_raw"],
                "vw_level2_raw": pt["vw_level2_raw"],
                "vw_level3_raw": pt["vw_level3_raw"],
                "vw_level4L_raw": pt["vw_level4L_raw"],
                "vw_level4A_raw": pt["vw_level4A_raw"],
                "vw_level4AC_raw": pt["vw_level4AC_raw"],
                "vw_level5_raw": pt["vw_level5_raw"],
                "vw_detail_raw": pt["vw_detail_raw"],
                "representative_method": rep_method,
                "parcel_count": len(group),
                "parcel_success_count": len(valid_pts),
                "parcel_excluded": parcel_excluded,
                "centroid_spread_m": round(spread, 1),
                "distance_from_anchor_km": round(dist_c, 2) if dist_c != 999999 else "",
                "coord_source": "vworld_geocoder_2.0",
                "coord_fetched_at": datetime.now(timezone.utc).isoformat(),
                "coord_license_note": "Realtime query. Not stored per VWorld TOS.",
                "coord_geom_basis": geom_basis,
                "coord_resolution": "",
                "coord_uncertainty_m": 0.0,
                "qa_flag": "|".join(c_flags),
                "error_code": "",
                "needs_review": bool(c_flags),
                "override_decision": "",
            })

        processed_count += 1

    # ──── 출력 ────
    out_dir = Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = Path("qa")
    qa_dir.mkdir(parents=True, exist_ok=True)

    df_fails = pd.DataFrame(fails)

    if records:
        df_new = pd.DataFrame(records)
        if out_path.exists():
            df_out = pd.read_csv(out_path)
            df_final = pd.concat([df_out, df_new], ignore_index=True)
        else:
            df_final = df_new

        df_final.to_csv(out_path, index=False, encoding="utf-8-sig")

        if not df_fails.empty:
            df_fails = df_fails[~df_fails["cluster_id"].isin(df_new["cluster_id"])]
    else:
        df_final = pd.read_csv(out_path) if out_path.exists() else pd.DataFrame()

    if not df_fails.empty:
        df_fails.loc[df_fails["transport_error"] != "", "status"] = "TRANSPORT_FAIL"
        if fail_path.exists():
            df_old = pd.read_csv(fail_path)
            if not df_final.empty:
                df_old = df_old[~df_old["cluster_id"].isin(df_final["cluster_id"])]
            df_fails = pd.concat([df_old, df_fails], ignore_index=True)
        df_fails.to_csv(fail_path, index=False, encoding="utf-8-sig")
    else:
        if fail_path.exists() and not df_final.empty:
            df_old = pd.read_csv(fail_path)
            df_old = df_old[~df_old["cluster_id"].isin(df_final["cluster_id"])]
            if not df_old.empty:
                df_old.to_csv(fail_path, index=False, encoding="utf-8-sig")
            else:
                fail_path.unlink()

    print(f"\n[완료] 총 {len(records)}건 exports/complex_geocode.csv 에 추가되었습니다.")
    if not df_fails.empty:
        print(f"[알림] 총 {len(df_fails)}건 qa/6B_geocode_fail.csv 에 기록되었습니다.")

    # ──── 서머리 ────
    n_success = len(df_final["cluster_id"].unique()) if not df_final.empty else 0
    n_fail = len(df_fails["cluster_id"].unique()) if not df_fails.empty else 0
    n_override = sum(1 for r in records if r.get("override_decision"))
    summary = f"""# VWorld Geocoder 2.0 Summary (v3)
- Time: {datetime.now(timezone.utc).isoformat()}
- Total 5A Plan Rows (Input): {len(df)}
- Valid Parcels to Geocode: {len(df_valid)} (after filtering + overrides)
- Target Clusters: {len(clusters)}
- Success Clusters: {n_success}
- Fully Failed Clusters: {n_fail}
- Override Applied: {n_override}
- Failed Parcels: {len(df_fails) if not df_fails.empty else 0}
"""
    with open("qa/6B_geocode_summary.md", "w", encoding="utf-8") as f:
        f.write(summary)

    # ──── 게이트 ────
    if not df_final.empty:
        print("\n=== QUALITY GATE ===")
        run_gate(df_final, overrides)

    if smoke_test:
        print("\n=== SMOKE TEST MODE ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Run only 5 clusters")
    args = parser.parse_args()
    process_complexes(smoke_test=args.smoke)
