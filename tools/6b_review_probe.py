"""
1단계: needs_review 6건 수동확인 프로브.
complex_geocode.csv를 수정하지 않는다.
bldg_query_plan.csv에서 직접 주소를 읽어 VWorld에 변형 질의를 보내고
비교표만 scratch/6b_probe_result.csv 에 저장한다.
"""
import math, time, sys, re
import pandas as pd
import requests
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import require_secret

VWORLD_BASE = "https://api.vworld.kr/req/address"
SLEEP = 0.15  # 일일 40,000건 제한 대비 여유. 프로브는 30건 미만.

GU_FIX_RE = re.compile(
    r"(화성|성남|수원|고양|용인|안양|안산|부천|청주|천안|전주|포항|창원|안동)(\w+구)"
)

def normalize_addr(s):
    return GU_FIX_RE.sub(r"\1시 \2", s)


def vworld_getcoord(address, typ):
    """VWorld Geocoder 2.0 호출. simple=false로 구조체 전체를 받는다."""
    params = {
        "service": "address", "version": "2.0", "request": "GetCoord",
        "key": require_secret("VWORLD_API_KEY"),
        "format": "json", "errorFormat": "json",
        "type": typ, "address": address,
        "refine": "true", "simple": "false", "crs": "EPSG:4326",
    }
    try:
        r = requests.get(VWORLD_BASE, params=params, timeout=10)
        body = r.json()
    except Exception as e:
        return {"status": f"TRANSPORT_ERROR", "lat": None, "lon": None,
                "refined_text": "", "level4L": "", "level5": "", "level4A": ""}

    status = body.get("response", {}).get("status")
    if status != "OK":
        return {"status": status, "lat": None, "lon": None,
                "refined_text": "", "level4L": "", "level5": "", "level4A": ""}

    pt = body["response"]["result"]["point"]
    ref = body["response"].get("refined", {})
    st = ref.get("structure", {})
    return {
        "status": status,
        "lat": float(pt["y"]),
        "lon": float(pt["x"]),
        "refined_text": ref.get("text", ""),
        "level4L": st.get("level4L", ""),
        "level4A": st.get("level4A", ""),
        "level5": st.get("level5", ""),
    }


def haversine_m(a, b):
    """(lat, lon) 쌍 두 개 사이 거리(m)."""
    (la1, lo1), (la2, lo2) = a, b
    R = 6371008.8
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def build_variants(plan_rows):
    """
    bldg_query_plan.csv 행(들)에서 질의 후보를 생성.
    산번지/부분매치/centroid_spread 케이스에 맞춰 변형을 만든다.
    """
    r0 = plan_rows.iloc[0]
    addr_legal = str(r0["addr_legal"]).strip()
    addr_road = str(r0.get("addr_road", "")).strip()
    plat = str(r0["platGbCd"])
    bun = str(int(r0["bun"]))
    ji = int(r0["ji"]) if pd.notna(r0["ji"]) and r0["ji"] != 0 else 0
    jibun = f"{bun}-{ji}" if ji > 0 else bun

    # addr_legal에서 시도-시군구-동 파싱
    parts = addr_legal.split()
    # "경기도 화성시동탄구 장지동 98" 형태
    # 마지막 토큰이 지번이므로 그 앞까지가 base
    if len(parts) >= 3:
        base = " ".join(parts[:-1])  # 지번 제외
    else:
        base = addr_legal

    base = normalize_addr(base)

    cluster_id = r0["cluster_id"]
    out = []

    # --- san_substituted 케이스 ---
    # platGbCd == 0인데 VWorld가 산번지를 반환하는 경우
    if plat in ("0", "0.0"):
        out.append(("parcel_as_is", normalize_addr(addr_legal), "PARCEL"))
        out.append(("san_explicit", f"{base} 산 {jibun}", "PARCEL"))

    # --- jibun_partial_match 케이스: 본번만 ---
    bon = jibun.split("-")[0]
    if ji > 0:
        out.append(("bon_only", f"{base} {bon}", "PARCEL"))

    # --- ROAD 변형 ---
    if addr_road and addr_road != "nan":
        out.append(("road", normalize_addr(addr_road), "ROAD"))

    # --- multi-parcel인 경우 각 필지 개별 ---
    if len(plan_rows) > 1:
        for idx, (_, rr) in enumerate(plan_rows.iterrows()):
            al = normalize_addr(str(rr["addr_legal"]).strip())
            out.append((f"parcel_{idx}", al, "PARCEL"))

    return out


def probe(df_plan, cluster_ids):
    """각 cluster_id에 대해 변형 질의를 실행하고 결과를 모은다."""
    rows = []
    for cid in cluster_ids:
        plan_rows = df_plan[df_plan["cluster_id"] == cid]
        if plan_rows.empty:
            print(f"  [SKIP] {cid}: bldg_query_plan.csv에 없음")
            continue

        print(f"\n--- {cid} ({plan_rows.iloc[0]['complex_name']}) ---")
        ref_coord = None

        for tag, addr, typ in build_variants(plan_rows):
            res = vworld_getcoord(addr, typ)
            time.sleep(SLEEP)

            if res["status"] == "OK" and res["lat"] is not None:
                coord = (res["lat"], res["lon"])
                if ref_coord is None:
                    ref_coord = coord
                res["d_from_first_m"] = round(haversine_m(ref_coord, coord), 1)
            else:
                res["d_from_first_m"] = None

            row = {
                "cluster_id": cid,
                "complex_name": plan_rows.iloc[0]["complex_name"],
                "variant": tag,
                "query": addr,
                "type": typ,
                **res,
            }
            rows.append(row)
            status_str = res["status"]
            lat_str = f"{res['lat']:.6f}" if res["lat"] else "N/A"
            lon_str = f"{res['lon']:.6f}" if res["lon"] else "N/A"
            d_str = f"{res['d_from_first_m']:.1f}m" if res.get("d_from_first_m") is not None else "N/A"
            print(f"  [{tag:15s}] {status_str:10s} ({lat_str}, {lon_str}) d={d_str}  refined={res.get('refined_text','')[:60]}")

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df_plan = pd.read_csv("bldg_query_plan.csv")

    # needs_review 대상 6건
    targets = [
        "A10026126",  # san_substituted: 장지동 98
        "A10026206",  # san_substituted: 장지동 95
        "A10025583",  # jibun_partial_match: 신동 623
        "A10026990",  # jibun_partial_match: 청계동 867
        "A10027957",  # jibun_partial_match: 구래동 6888
        "A10027692",  # centroid_spread: 창곡동 521 + 2-10
    ]

    print(f"프로브 대상 = {len(targets)}건: {targets}")
    out = probe(df_plan, targets)

    Path("scratch").mkdir(exist_ok=True)
    out.to_csv("scratch/6b_probe_result.csv", index=False, encoding="utf-8-sig")
    print(f"\n결과 저장: scratch/6b_probe_result.csv ({len(out)}행)")
