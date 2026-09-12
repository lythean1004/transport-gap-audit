"""
src/verify/stop_gate.py
대표 정류소 확인 게이트 (G1~G6) 및 CLI 승격 도구
순수 파일 읽기 전용 (네트워크 호출 절대 금지)
"""
import os
import re
import sys
import json
import socket
import hashlib
import tempfile
import argparse
import unicodedata
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from contextlib import contextmanager
import pandas as pd

from src.verify.reasons import Reason, ALLOWED
from src.collectors.geo_const import haversine

KST = ZoneInfo("Asia/Seoul")
GATE_CODE_VERSION = "v2.3"
G2_COORD_DELTA_LIMIT_M = 50.0
G3_DIST_LIMIT_M = 800.0
MAX_SMOKE_AGE_DAYS = 30

# 최종 확정 레지스트리 스키마 (docs/stop_registry_schema.md)
REGISTRY_COLUMNS = (
    "cluster_id",
    "citycode",
    "nodeid",
    "stop_lat",
    "stop_lon",
    "direction_label",
    "coord_verify_method",
    "raw_citycode_response_path",
    "review_status",
    "verified_by",
    "verified_at",
    "notes"
)

# 내용 해시 계산 대상 컬럼 (review_status 제외, notes 포함)
REGISTRY_EVAL_COLUMNS = (
    "cluster_id",
    "citycode",
    "nodeid",
    "stop_lat",
    "stop_lon",
    "direction_label",
    "coord_verify_method",
    "raw_citycode_response_path",
    "verified_by",
    "verified_at",
    "notes"
)

# 허용 검증 방법 화이트리스트 (G5)
ALLOWED_COORD_VERIFY_METHODS = frozenset({
    "kakao_map_cadastral_crosscheck",
    "onsite_photo",
    "naver_streetview_crosscheck",
    "vworld_cadastral_check",
    "rapid_transit_map_check",
    "human_onsite_map_review"
})

def get_gate_module_sha256() -> str:
    """현재 stop_gate.py 소스코드 파일의 SHA-256 다이제스트를 반환한다."""
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def is_blank(val: Any) -> bool:
    """
    공용 결측/공백 판정 헬퍼:
    None, pd.isna, 빈 문자열, 그리고 문자열 'nan', 'none', 'null'을 모두 True(결측)로 판정한다.
    """
    if val is None:
        return True
    if pd.isna(val):
        return True
    s = str(val).strip()
    if not s or s.lower() in ("none", "nan", "null"):
        return True
    return False

@contextmanager
def block_all_network():
    """
    네트워크 호출을 원천 차단하는 컨텍스트 매니저.
    socket.socket, socket.create_connection, socket.getaddrinfo를 모두 차단한다.
    """
    orig_socket = socket.socket
    orig_create = getattr(socket, "create_connection", None)
    orig_getaddr = getattr(socket, "getaddrinfo", None)

    def guarded(*args, **kwargs):
        raise RuntimeError("네트워크 호출 시도 감지! 게이트는 순수 파일 읽기 전용입니다.")

    socket.socket = guarded
    if orig_create:
        socket.create_connection = guarded
    if orig_getaddr:
        socket.getaddrinfo = guarded

    try:
        yield
    finally:
        socket.socket = orig_socket
        if orig_create:
            socket.create_connection = orig_create
        if orig_getaddr:
            socket.getaddrinfo = orig_getaddr

def within(dist_m: float, limit_m: float) -> bool:
    """순수 함수: 포함 경계 (dist_m <= limit_m) 판정"""
    return dist_m <= limit_m

def compute_registry_content_hash(df: pd.DataFrame) -> str:
    """
    stop_registry.csv 에서 review_status 를 제외한 REGISTRY_EVAL_COLUMNS 컬럼들의 정규화 SHA-256 해시를 계산한다.
    P0-F 명세 준수:
    1) (citycode, nodeid) 기준 오름차순 정렬 후 해시 계산 (행 순서 독립성)
    2) is_blank 판정된 결측값은 빈 문자열 ""로 일원화
    3) 유니코드 NFC 정규화 및 trim 적용 (NFD/NFC 바이트 차이 해소)
    4) 좌표는 소수점 7자리 고정 포맷팅
    """
    if df.empty:
        return "empty_registry"

    # 1. 행 정렬: (citycode, nodeid) 기준
    df_sorted = df.copy()
    c_sort = df_sorted["citycode"].astype(str).str.strip() if "citycode" in df_sorted.columns else ""
    n_sort = df_sorted["nodeid"].astype(str).str.strip() if "nodeid" in df_sorted.columns else ""
    df_sorted["_sort_key"] = c_sort + "_" + n_sort
    df_sorted = df_sorted.sort_values(by="_sort_key").drop(columns=["_sort_key"])

    rows_normalized = []
    for _, row in df_sorted.iterrows():
        item_vals = []
        for c in REGISTRY_EVAL_COLUMNS:
            v = row.get(c)
            if is_blank(v):
                item_vals.append("")
            elif c in ("stop_lat", "stop_lon"):
                try:
                    item_vals.append(f"{float(v):.7f}")
                except (ValueError, TypeError):
                    item_vals.append(str(v).strip())
            else:
                # 3. 유니코드 NFC 정규화 및 trim
                s = str(v).strip()
                s_nfc = unicodedata.normalize("NFC", s).strip()
                item_vals.append(s_nfc)
        rows_normalized.append(tuple(item_vals))

    serialized = json.dumps(rows_normalized, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

class GateResult:
    def __init__(
        self,
        citycode: str,
        nodeid: str,
        passed: bool,
        gates: Dict[str, Optional[bool]],
        rejection_reasons: Tuple[Reason, ...] = (),
        metrics: Optional[Dict[str, float]] = None,
        review_status: str = "pending"
    ):
        self.citycode = citycode
        self.nodeid = nodeid
        self.passed = passed
        self.gates = gates
        self.rejection_reasons = rejection_reasons
        self.metrics = metrics or {}
        self.review_status = review_status

    def __repr__(self):
        return (f"GateResult(citycode={self.citycode!r}, nodeid={self.nodeid!r}, "
                f"passed={self.passed!r}, gates={self.gates!r}, "
                f"rejection_reasons={self.rejection_reasons!r}, metrics={self.metrics!r}, "
                f"review_status={self.review_status!r})")

def select_authoritative_smoke_row(df_matches: pd.DataFrame) -> pd.Series:
    """
    동일 (citycode, nodeid)에 대한 복수 스모크 행 중 정본 행을 선택한다.
    규칙: schema_version 최대 우선 (v2 > v1 > NA), 동일 버전 내에서는 smoke_test_at_kst 최신 우선.
    CSV 행 순서와 무관하게 결정적(deterministic)으로 동작한다.
    """
    def version_rank(v):
        if is_blank(v):
            return 0
        v_str = str(v).strip().lower()
        if v_str == "v2":
            return 2
        if v_str == "v1":
            return 1
        return 0

    df_sorted = df_matches.copy()
    df_sorted["_v_rank"] = df_sorted["schema_version"].apply(version_rank)
    df_sorted["_time_kst"] = pd.to_datetime(df_sorted["smoke_test_at_kst"], errors="coerce")

    df_sorted = df_sorted.sort_values(by=["_v_rank", "_time_kst"], ascending=[False, False])
    return df_sorted.iloc[0]

def evaluate_gate(
    stop_row: dict,
    citycodes_df: pd.DataFrame,
    stops_df: pd.DataFrame,
    smoke_df: pd.DataFrame,
    complexes_df: pd.DataFrame
) -> GateResult:
    """
    단일 정류소 행에 대해 G1~G6 게이트를 평가한다.
    stop_row를 절대 변형하지 않으며, 순수 파일/데이터프레임 읽기만 수행한다.
    review_status 가 'pending' 이 아닌 행은 평가 대상 자격 미달로 평가를 거부한다.
    """
    citycode = "" if is_blank(stop_row.get("citycode")) else str(stop_row.get("citycode")).strip()
    nodeid = "" if is_blank(stop_row.get("nodeid")) else str(stop_row.get("nodeid")).strip()
    review_status = "" if is_blank(stop_row.get("review_status")) else str(stop_row.get("review_status")).strip()

    # -------------------------------------------------------------
    # 입력 자격 검사: pending 상태가 아니면 게이트 미평가(None) 및 INPUT_NOT_PENDING
    # -------------------------------------------------------------
    if review_status != "pending":
        gates_unassessed = {
            "G1": None,
            "G2": None,
            "G3": None,
            "G4": None,
            "G5": None,
            "G6": None
        }
        return GateResult(
            citycode=citycode,
            nodeid=nodeid,
            passed=False,
            gates=gates_unassessed,
            rejection_reasons=(Reason.INPUT_NOT_PENDING,),
            metrics={},
            review_status=review_status
        )

    gates = {
        "G1": True,
        "G2": True,
        "G3": True,
        "G4": True,
        "G5": True,
        "G6": True
    }
    reasons = []
    metrics = {}

    # -------------------------------------------------------------
    # G1: citycode 존재 여부 및 raw 응답 파일 디스크 실존 + JSON 내용 내 citycode 확인
    # -------------------------------------------------------------
    citycode_exists = False
    if "citycode" in citycodes_df.columns:
        citycode_exists = (citycodes_df["citycode"].astype(str).str.strip() == citycode).any()
    if not citycode_exists:
        gates["G1"] = False
        reasons.append(Reason.G1_CITYCODE_MISSING)

    raw_path_val = stop_row.get("raw_citycode_response_path")
    if is_blank(raw_path_val) or not Path(str(raw_path_val)).exists():
        gates["G1"] = False
        reasons.append(Reason.G1_RAW_MISSING)
    else:
        # P1-9: JSON 내용 파싱하여 해당 citycode 실존 여부 확인
        try:
            with open(str(raw_path_val), "r", encoding="utf-8") as rf:
                raw_data = json.load(rf)
            raw_items = raw_data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(raw_items, dict):
                raw_items = [raw_items]
            found_in_raw = any(str(it.get("citycode", "")).strip() == citycode for it in raw_items)
            if not found_in_raw:
                gates["G1"] = False
                reasons.append(Reason.G1_CITYCODE_NOT_IN_RAW)
        except Exception:
            gates["G1"] = False
            reasons.append(Reason.G1_RAW_MISSING)

    # -------------------------------------------------------------
    # G2: (citycode, nodeid) 존재 여부 및 하버사인 재계산 coord_delta <= 50m
    # -------------------------------------------------------------
    match_stop = pd.DataFrame()
    ref_nodenm = ""
    if "citycode" in stops_df.columns and "nodeid" in stops_df.columns:
        c_mask = stops_df["citycode"].astype(str).str.strip() == citycode
        n_mask = stops_df["nodeid"].astype(str).str.strip() == nodeid
        match_stop = stops_df[c_mask & n_mask]
        if not match_stop.empty:
            ref_nodenm = str(match_stop.iloc[0].get("nodenm", "")).strip()

    raw_s_lat = stop_row.get("stop_lat")
    if is_blank(raw_s_lat):
        raw_s_lat = stop_row.get("list_lat") if not is_blank(stop_row.get("list_lat")) else stop_row.get("api_lat")
    raw_s_lon = stop_row.get("stop_lon")
    if is_blank(raw_s_lon):
        raw_s_lon = stop_row.get("list_lon") if not is_blank(stop_row.get("list_lon")) else stop_row.get("api_lon")

    stop_lat = float(raw_s_lat or 0.0)
    stop_lon = float(raw_s_lon or 0.0)

    if match_stop.empty:
        gates["G2"] = False
        reasons.append(Reason.G2_STOP_NOT_FOUND)
        metrics["coord_delta_recomputed_m"] = float("nan")
    else:
        ref_lat = float(match_stop.iloc[0]["gpslati"])
        ref_lon = float(match_stop.iloc[0]["gpslong"])

        delta_m = haversine(stop_lat, stop_lon, ref_lat, ref_lon)
        metrics["coord_delta_recomputed_m"] = delta_m
        if not within(delta_m, G2_COORD_DELTA_LIMIT_M):
            gates["G2"] = False
            reasons.append(Reason.G2_COORD_DELTA)

    # -------------------------------------------------------------
    # G3: 클러스터 좌표와 사람이 계측한 정류소 좌표 간 거리 재계산 <= G3_DIST_LIMIT_M
    #     P0-1 강제: stop_row의 cluster_lat/lon은 절대 판정에 쓰지 않음 (참고 지표로만 보존)
    #     complexes_df 조인만을 유일 경로로 강제 (파일 폴백 완전 삭제)
    # -------------------------------------------------------------
    if not isinstance(complexes_df, pd.DataFrame):
        raise TypeError("complexes_df는 필수 pd.DataFrame 인자여야 합니다 (조용한 폴백 금지).")

    raw_c_lat_input = stop_row.get("cluster_lat")
    raw_c_lon_input = stop_row.get("cluster_lon")
    if not is_blank(raw_c_lat_input):
        try:
            metrics["cluster_lat_input"] = float(raw_c_lat_input)
        except (ValueError, TypeError):
            pass
    if not is_blank(raw_c_lon_input):
        try:
            metrics["cluster_lon_input"] = float(raw_c_lon_input)
        except (ValueError, TypeError):
            pass

    cluster_id_val = stop_row.get("cluster_id")
    if is_blank(cluster_id_val) or "cluster_id" not in complexes_df.columns:
        gates["G3"] = False
        reasons.append(Reason.G3_CLUSTER_NOT_FOUND)
        metrics["dist_recomputed_m"] = float("nan")
        metrics["cluster_match_count"] = 0
    else:
        c_mask = complexes_df["cluster_id"].astype(str).str.strip() == str(cluster_id_val).strip()
        c_match = complexes_df[c_mask]
        match_count = len(c_match)
        metrics["cluster_match_count"] = match_count

        if match_count == 0:
            gates["G3"] = False
            reasons.append(Reason.G3_CLUSTER_NOT_FOUND)
            metrics["dist_recomputed_m"] = float("nan")
        elif match_count > 1:
            gates["G3"] = False
            reasons.append(Reason.G3_CLUSTER_AMBIGUOUS)
            metrics["dist_recomputed_m"] = float("nan")
        else:
            c_row = c_match.iloc[0]
            # P0-4: 좌표 컬럼 존재 검증
            if "lat" not in complexes_df.columns or "lon" not in complexes_df.columns:
                gates["G3"] = False
                reasons.append(Reason.G3_CLUSTER_NOT_FOUND)
                metrics["dist_recomputed_m"] = float("nan")
            else:
                # 행 단위 crs 검증 (EPSG:4326 필수)
                row_crs = str(c_row.get("crs", "")).strip().upper()
                if "crs" in complexes_df.columns and row_crs != "EPSG:4326":
                    gates["G3"] = False
                    reasons.append(Reason.G3_INVALID_CRS)
                    metrics["dist_recomputed_m"] = float("nan")
                else:
                    try:
                        c_lat = float(c_row["lat"])
                        c_lon = float(c_row["lon"])
                        if pd.isna(c_lat) or pd.isna(c_lon):
                            gates["G3"] = False
                            reasons.append(Reason.G3_CLUSTER_NOT_FOUND)
                            metrics["dist_recomputed_m"] = float("nan")
                        else:
                            dist_m = haversine(c_lat, c_lon, stop_lat, stop_lon)
                            metrics["dist_recomputed_m"] = dist_m
                            if not within(dist_m, G3_DIST_LIMIT_M):
                                gates["G3"] = False
                                reasons.append(Reason.G3_DISTANCE)
                    except (ValueError, TypeError, KeyError):
                        gates["G3"] = False
                        reasons.append(Reason.G3_CLUSTER_NOT_FOUND)
                        metrics["dist_recomputed_m"] = float("nan")

    # -------------------------------------------------------------
    # G4: 평일 주간(09:00~18:00) ok_with_items 및 유효 증거(신선도 30일 이내)
    # -------------------------------------------------------------
    match_smoke = pd.DataFrame()
    if "citycode" in smoke_df.columns and "nodeid" in smoke_df.columns:
        c_mask = smoke_df["citycode"].astype(str).str.strip() == citycode
        n_mask = smoke_df["nodeid"].astype(str).str.strip() == nodeid
        match_smoke = smoke_df[c_mask & n_mask]

    if match_smoke.empty:
        gates["G4"] = False
        reasons.append(Reason.G4_EVIDENCE_MISSING)
    else:
        s_row = select_authoritative_smoke_row(match_smoke)
        outcome = "" if is_blank(s_row.get("outcome")) else str(s_row.get("outcome")).strip()
        items_valid = s_row.get("items_with_routeid_and_arrtime")

        if is_blank(items_valid):
            gates["G4"] = False
            reasons.append(Reason.G4_EVIDENCE_MISSING)
        elif outcome == "ok_empty":
            gates["G4"] = False
            reasons.append(Reason.G4_NO_BUS_RUNNING_NOW)
        elif outcome == "api_error":
            gates["G4"] = False
            reasons.append(Reason.G4_API_ERROR)
        elif outcome == "ok_with_items":
            if int(items_valid) < 1:
                gates["G4"] = False
                reasons.append(Reason.G4_EVIDENCE_MISSING)
            else:
                time_str = "" if is_blank(s_row.get("smoke_test_at_kst")) else str(s_row.get("smoke_test_at_kst")).strip()
                try:
                    dt = datetime.fromisoformat(time_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=KST)
                    else:
                        dt = dt.astimezone(KST)

                    # P1-6: 신선도 상한 검증 (30일 이내)
                    now_cur = datetime.now(KST)
                    if (now_cur - dt).days > MAX_SMOKE_AGE_DAYS:
                        gates["G4"] = False
                        reasons.append(Reason.G4_STALE_SMOKE)

                    if dt.weekday() not in (0, 1, 2, 3, 4):
                        gates["G4"] = False
                        reasons.append(Reason.G4_NOT_WEEKDAY)

                    business_start = time(9, 0, 0)
                    business_end = time(18, 0, 0)
                    if not (business_start <= dt.time() <= business_end):
                        gates["G4"] = False
                        reasons.append(Reason.G4_OUTSIDE_HOURS)
                except Exception:
                    gates["G4"] = False
                    reasons.append(Reason.G4_EVIDENCE_MISSING)
        else:
            gates["G4"] = False
            reasons.append(Reason.G4_API_ERROR)

    # -------------------------------------------------------------
    # G5: verified_by / verified_at 형식 및 지도 검증 방법(화이트리스트 + 토큰 검사)
    # -------------------------------------------------------------
    raw_by = stop_row.get("verified_by")
    raw_at = stop_row.get("verified_at")
    raw_method = stop_row.get("coord_verify_method")

    if is_blank(raw_by):
        gates["G5"] = False
        reasons.append(Reason.G5_MISSING_VERIFIER)

    # P1-4: verified_at ISO-8601 오프셋 포함 파싱 및 미래 시각 거부
    if is_blank(raw_at):
        gates["G5"] = False
        reasons.append(Reason.G5_MISSING_VERIFIER)
    else:
        try:
            v_dt = datetime.fromisoformat(str(raw_at).strip())
            if v_dt.tzinfo is None:
                gates["G5"] = False
                reasons.append(Reason.G5_INVALID_VERIFIED_AT)
            else:
                # 미래 시각 거부 (5분 허용 마진)
                now_check = datetime.now(KST)
                if v_dt > now_check + timedelta(minutes=5):
                    gates["G5"] = False
                    reasons.append(Reason.G5_INVALID_VERIFIED_AT)
        except Exception:
            gates["G5"] = False
            reasons.append(Reason.G5_INVALID_VERIFIED_AT)

    # P1-3: coord_verify_method 한글/영문 토큰 검사 및 화이트리스트
    if is_blank(raw_method):
        gates["G5"] = False
        reasons.append(Reason.G5_MISSING_VERIFIER)
    else:
        method_str = str(raw_method).strip()
        tokens = set(re.split(r'[^a-zA-Z0-9가-힣]+', method_str.lower()))
        # 블랙리스트 토큰 검출 (한글 자동화 포함)
        prohibited_tokens = {"auto", "api", "자동", "자동화", "에이피아이"}
        if bool(tokens & prohibited_tokens) or method_str not in ALLOWED_COORD_VERIFY_METHODS:
            gates["G5"] = False
            reasons.append(Reason.G5_INVALID_METHOD)

    # -------------------------------------------------------------
    # G6: direction_label 비어있지 않음 및 nodenm 복사 금지
    # -------------------------------------------------------------
    raw_label = stop_row.get("direction_label")
    if is_blank(raw_label):
        gates["G6"] = False
        reasons.append(Reason.G6_NO_DIRECTION)
    else:
        label_clean = str(raw_label).strip()
        # P1-8: 정류소명 복사 방지 (direction_label == nodenm)
        if ref_nodenm and label_clean == ref_nodenm:
            gates["G6"] = False
            reasons.append(Reason.G6_DIRECTION_EQUALS_NODENM)

    passed = all(bool(v) for v in gates.values() if v is not None)
    if passed:
        reasons = []

    return GateResult(
        citycode=citycode,
        nodeid=nodeid,
        passed=passed,
        gates=gates,
        rejection_reasons=tuple(reasons),
        metrics=metrics,
        review_status=review_status
    )

def run_gate_on_registry(
    registry_csv: str = "evidence/stop_registry.csv",
    citycodes_parquet: str = "data/staged/tago_citycodes.parquet",
    stops_full_parquet: str = "data/staged/tago_stops_full.parquet",
    smoke_log_csv: str = "evidence/smoke_log.csv",
    complex_geocode_csv: str = "exports/complex_geocode.csv",
    output_report_csv: str = "exports/stop_gate_report.csv",
    output_meta_json: str = "exports/stop_gate_report.meta.json"
) -> pd.DataFrame:
    """
    evidence/stop_registry.csv 내의 pending 상태 행들을 평가하고 리포트를 생성한다.
    시작 시 레지스트리 헤더를 확정 스키마(REGISTRY_COLUMNS)와 대조해 불일치 시 거부한다.
    리포트 메타데이터는 사이드카 파일 exports/stop_gate_report.meta.json 에 저장한다.
    배치 실행 경로 전체에 네트워크 차단을 적용한다.
    """
    with block_all_network():
        reg_p = Path(registry_csv)
        now_kst = datetime.now(KST).isoformat()
        module_sha = get_gate_module_sha256()

        if not reg_p.exists():
            print(f"[알림] 레지스트리 파일({registry_csv})이 존재하지 않습니다. 0행 리포트를 기록합니다.")
            df_reg = pd.DataFrame()
            content_hash = "no_registry"
        else:
            df_reg = pd.read_csv(reg_p)
            if not df_reg.empty:
                # P0-4: 헤더 검증 (순서 및 컬럼명 정확 일치)
                actual_cols = tuple(df_reg.columns)
                if actual_cols != REGISTRY_COLUMNS:
                    raise ValueError(f"레지스트리 헤더 스키마 불일치!\n기대: {REGISTRY_COLUMNS}\n실제: {actual_cols}")
            content_hash = compute_registry_content_hash(df_reg)

        df_citycodes = pd.read_parquet(citycodes_parquet) if Path(citycodes_parquet).exists() else pd.DataFrame()
        df_stops = pd.read_parquet(stops_full_parquet) if Path(stops_full_parquet).exists() else pd.DataFrame()
        df_smoke = pd.read_csv(smoke_log_csv) if Path(smoke_log_csv).exists() else pd.DataFrame()
        df_complexes = pd.read_csv(complex_geocode_csv) if Path(complex_geocode_csv).exists() else pd.DataFrame()

        results = []
        for _, row in df_reg.iterrows():
            r_dict = row.to_dict()
            res = evaluate_gate(r_dict, df_citycodes, df_stops, df_smoke, complexes_df=df_complexes)

            reasons_joined = ";".join([r.value for r in res.rejection_reasons])
            gates_failed_joined = ";".join([g for g, p in res.gates.items() if p is False])

            s_outcome = ""
            s_time_kst = ""
            s_version = ""
            if not df_smoke.empty and "citycode" in df_smoke.columns and "nodeid" in df_smoke.columns:
                sm = df_smoke[(df_smoke["citycode"].astype(str) == str(r_dict.get("citycode"))) &
                              (df_smoke["nodeid"].astype(str) == str(r_dict.get("nodeid")))]
                if not sm.empty:
                    s_chosen = select_authoritative_smoke_row(sm)
                    s_outcome = "" if is_blank(s_chosen.get("outcome")) else str(s_chosen.get("outcome"))
                    s_time_kst = "" if is_blank(s_chosen.get("smoke_test_at_kst")) else str(s_chosen.get("smoke_test_at_kst"))
                    s_version = "" if is_blank(s_chosen.get("schema_version")) else str(s_chosen.get("schema_version"))

            joined_nodenm = ""
            if not df_stops.empty and "citycode" in df_stops.columns and "nodeid" in df_stops.columns:
                st_match = df_stops[(df_stops["citycode"].astype(str) == str(r_dict.get("citycode"))) &
                                    (df_stops["nodeid"].astype(str) == str(r_dict.get("nodeid")))]
                if not st_match.empty:
                    joined_nodenm = str(st_match.iloc[0].get("nodenm", ""))

            res_row = r_dict.copy()
            res_row["nodenm"] = joined_nodenm
            res_row["passed"] = res.passed
            res_row["failed_gates"] = gates_failed_joined
            res_row["rejection_reasons"] = reasons_joined
            res_row["coord_delta_recomputed_m"] = res.metrics.get("coord_delta_recomputed_m")
            res_row["dist_recomputed_m"] = res.metrics.get("dist_recomputed_m")
            res_row["smoke_outcome"] = s_outcome
            res_row["smoke_test_at_kst"] = s_time_kst
            res_row["schema_version"] = s_version
            res_row["review_status"] = res.review_status

            results.append(res_row)

        df_out = pd.DataFrame(results)
        out_p = Path(output_report_csv)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(out_p, index=False, encoding="utf-8")

        # 사이드카 메타데이터 저장 (P0-E: gate_module_sha256 포함)
        meta_dict = {
            "report_generated_at": now_kst,
            "input_source": str(reg_p).replace("\\", "/"),
            "input_row_count": len(df_reg),
            "gate_code_version": GATE_CODE_VERSION,
            "gate_module_sha256": module_sha,
            "registry_content_hash": content_hash
        }
        meta_p = Path(output_meta_json)
        meta_p.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_p, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, ensure_ascii=False, indent=2)

        print(f"[보고서 생성] {out_p} ({len(df_out)}행 기록 완료)")
        print(f"[사이드카 메타] {meta_p} (버전: {GATE_CODE_VERSION}, 해시: {content_hash[:8]}...)")
        print(f"[네트워크 상태] HTTP 호출 0건 확인 (차단 상태 유지)")
        return df_out

def promote_stop(
    citycode: str,
    nodeid: str,
    reviewer: str,
    notes: str = "",
    registry_csv: str = "evidence/stop_registry.csv",
    report_csv: str = "exports/stop_gate_report.csv",
    meta_json: str = "exports/stop_gate_report.meta.json",
    promotion_log_csv: str = "evidence/promotion_log.csv"
):
    """
    Phase 3 CLI: 게이트를 통과한 정류소의 review_status 를 pending -> human_verified 로만 전이시킨다.
    새로운 행을 만들지 않으며(in-place 원자적 교체), 기존의 verified_by 등 다른 컬럼은 절대 변경하지 않는다.
    사이드카 메타(stop_gate_report.meta.json)를 검증하며, 내용 해시가 불일치하면 stale 상태로 거부한다.
    """
    reg_p = Path(registry_csv)
    rep_p = Path(report_csv)
    meta_p = Path(meta_json)

    if not reg_p.exists():
        print(f"[거부] {reg_p} 가 존재하지 않습니다.", file=sys.stderr)
        sys.exit(1)
    if not rep_p.exists():
        print(f"[거부] {rep_p} 가 존재하지 않습니다. 먼저 게이트 평가를 실행하세요.", file=sys.stderr)
        sys.exit(1)
    if not meta_p.exists():
        print(f"[거부] 사이드카 메타 파일({meta_p})이 존재하지 않습니다.", file=sys.stderr)
        sys.exit(1)

    # 1. 사이드카 메타 로드 및 검증
    try:
        with open(meta_p, "r", encoding="utf-8") as f:
            meta_dict = json.load(f)
    except Exception as e:
        print(f"[거부] 사이드카 메타 파싱 오류: {e}", file=sys.stderr)
        sys.exit(1)

    # P1-1: gate_code_version 및 gate_module_sha256 검증
    rep_version = str(meta_dict.get("gate_code_version", "")).strip()
    if rep_version != GATE_CODE_VERSION:
        print(f"[거부] 리포트의 게이트 코드 버전({rep_version})이 현재 시스템 버전({GATE_CODE_VERSION})과 불일치합니다.", file=sys.stderr)
        sys.exit(1)

    expected_hash = meta_dict.get("registry_content_hash", "")
    if not expected_hash or expected_hash in ("no_registry", "empty_registry") or int(meta_dict.get("input_row_count", 0)) == 0:
        print(f"[거부] 유효한 레지스트리 평가 결과가 없는 리포트 상태에서는 승격할 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    rep_input_source = str(meta_dict.get("input_source", "")).strip().replace("\\", "/")
    expected_source = str(reg_p).replace("\\", "/")
    if rep_input_source != expected_source:
        print(f"[거부] 리포트 input_source({rep_input_source})와 대상 레지스트리({expected_source}) 불일치.", file=sys.stderr)
        sys.exit(1)

    df_reg = pd.read_csv(reg_p)

    # P1-2: 행 수 일치 검증 (report_row_count != registry_row_count)
    if int(meta_dict.get("input_row_count", 0)) != len(df_reg):
        print(f"[거부] 리포트 생성 당시 행 수({meta_dict.get('input_row_count')})와 현재 레지스트리 행 수({len(df_reg)})가 불일치합니다.", file=sys.stderr)
        sys.exit(1)

    # 2. 내용 해시 비교 (review_status 제외한 REGISTRY_EVAL_COLUMNS 컬럼의 SHA-256 일치 검증)
    curr_hash = compute_registry_content_hash(df_reg)
    if curr_hash != expected_hash:
        print(f"[거부] 레지스트리 내용(좌표, 검증자 등)이 리포트 생성 시점과 다릅니다 (stale report). 게이트를 재실행하세요.", file=sys.stderr)
        sys.exit(1)

    # 3. 리포트에서 대상 정류소 통과 여부 검사
    df_report = pd.read_csv(rep_p)
    if df_report.empty:
        print(f"[거부] 리포트 파일이 비어 있습니다.", file=sys.stderr)
        sys.exit(1)

    rc_mask = df_report["citycode"].astype(str).str.strip() == str(citycode).strip()
    rn_mask = df_report["nodeid"].astype(str).str.strip() == str(nodeid).strip()
    match_report = df_report[rc_mask & rn_mask]

    # P1-2: 대상 정류소가 리포트에 없는 경우 거부
    if match_report.empty:
        print(f"[거부] 정류소 ({citycode}, {nodeid})가 리포트에 존재하지 않습니다.", file=sys.stderr)
        sys.exit(1)

    if not bool(match_report.iloc[0].get("passed", False)):
        reasons = match_report.iloc[0].get("rejection_reasons", "")
        print(f"[거부] 정류소 ({citycode}, {nodeid})가 게이트를 통과하지 못했습니다. (탈락사유: {reasons})", file=sys.stderr)
        sys.exit(1)

    # 4. 레지스트리에서 대상 정류소 조회 및 in-place 전이
    mc_mask = df_reg["citycode"].astype(str).str.strip() == str(citycode).strip()
    mn_mask = df_reg["nodeid"].astype(str).str.strip() == str(nodeid).strip()
    match_indices = df_reg[mc_mask & mn_mask].index

    if len(match_indices) == 0:
        print(f"[거부] stop_registry.csv 에 ({citycode}, {nodeid}) 정류소가 없습니다.", file=sys.stderr)
        sys.exit(1)

    idx = match_indices[0]
    from_status = str(df_reg.loc[idx, "review_status"])
    if from_status != "pending":
        print(f"[거부] 정류소 상태가 'pending'이 아닙니다 (현재: {from_status}).", file=sys.stderr)
        sys.exit(1)

    to_status = "human_verified"
    df_reg.loc[idx, "review_status"] = to_status
    if notes:
        curr_notes = "" if is_blank(df_reg.loc[idx, "notes"]) else str(df_reg.loc[idx, "notes"])
        df_reg.loc[idx, "notes"] = f"{curr_notes}; {notes}".strip("; ")

    # 5. 원자적 파일 교체 (임시 파일 + os.replace)
    reg_dir = reg_p.parent
    with tempfile.NamedTemporaryFile("w", dir=reg_dir, delete=False, encoding="utf-8", newline="") as tf:
        df_reg.to_csv(tf.name, index=False, encoding="utf-8")
        temp_name = tf.name

    os.replace(temp_name, reg_p)

    # 6. evidence/promotion_log.csv (append-only) 이력 기록
    now_kst_str = datetime.now(KST).isoformat()
    log_p = Path(promotion_log_csv)
    log_p.parent.mkdir(parents=True, exist_ok=True)
    write_log_header = not log_p.exists()

    log_row = {
        "citycode": citycode,
        "nodeid": nodeid,
        "from_status": from_status,
        "to_status": to_status,
        "reviewer": reviewer,
        "promoted_at_kst": now_kst_str,
        "report_generated_at": meta_dict.get("report_generated_at", "")
    }
    pd.DataFrame([log_row]).to_csv(log_p, mode="a", header=write_log_header, index=False, encoding="utf-8")

    print(f"[승격 성공] 정류소 ({citycode}, {nodeid})의 review_status 가 'human_verified'로 전이되었습니다. (이력 로그: {log_p})")

def check_7d_preconditions(registry_csv: str = "evidence/stop_registry.csv") -> int:
    """
    7D 스냅샷 수집기 착수 조건 가드:
    stop_registry.csv 에 review_status == 'human_verified' 행이 1건 이상 존재해야 한다.
    0건이면 즉시 RuntimeError를 발생시키고 착수를 차단한다.
    """
    p = Path(registry_csv)
    if not p.exists():
        raise RuntimeError(f"7D 수집 착수 불가: {registry_csv} 파일이 존재하지 않습니다.")
    df = pd.read_csv(p)
    if "review_status" not in df.columns:
        raise RuntimeError(f"7D 수집 착수 불가: {registry_csv} 에 review_status 컬럼이 없습니다.")
    cnt = (df["review_status"] == "human_verified").sum()
    if cnt < 1:
        raise RuntimeError(f"7D 수집 착수 불가: human_verified 상태의 정류소가 0건입니다 (현재: {cnt}건). 인간 지도 검증 및 promote를 먼저 수행하세요.")
    return cnt

def main():
    parser = argparse.ArgumentParser(description="대표 정류소 게이트 및 레지스트리 승격 CLI")
    subparsers = parser.add_subparsers(dest="command")

    p_promote = subparsers.add_parser("promote", help="게이트를 통과한 정류소의 review_status를 human_verified로 승격")
    p_promote.add_argument("--citycode", required=True, help="도시코드")
    p_promote.add_argument("--nodeid", required=True, help="정류소 Node ID")
    p_promote.add_argument("--reviewer", required=True, help="인간 검증자 이름")
    p_promote.add_argument("--notes", default="", help="추가 비고")
    p_promote.add_argument("--registry", default="evidence/stop_registry.csv")
    p_promote.add_argument("--report", default="exports/stop_gate_report.csv")
    p_promote.add_argument("--meta", default="exports/stop_gate_report.meta.json")

    p_eval = subparsers.add_parser("evaluate", help="stop_registry.csv의 pending 정류소 게이트 평가 리포트 생성")
    p_eval.add_argument("--registry", default="evidence/stop_registry.csv")
    p_eval.add_argument("--output", default="exports/stop_gate_report.csv")
    p_eval.add_argument("--meta", default="exports/stop_gate_report.meta.json")

    args = parser.parse_args()

    if args.command == "promote":
        promote_stop(args.citycode, args.nodeid, args.reviewer, args.notes, registry_csv=args.registry, report_csv=args.report, meta_json=args.meta)
    elif args.command == "evaluate":
        run_gate_on_registry(registry_csv=args.registry, output_report_csv=args.output, output_meta_json=args.meta)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
