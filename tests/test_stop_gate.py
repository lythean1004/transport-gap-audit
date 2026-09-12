"""
tests/test_stop_gate.py
7B′ 대표 정류소 확인 게이트 단위 테스트
"""
import pytest
import pandas as pd
import copy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from src.verify.stop_gate import (
    evaluate_gate,
    GateResult,
    within,
    select_authoritative_smoke_row,
    G2_COORD_DELTA_LIMIT_M,
    G3_DIST_LIMIT_M,
    GATE_CODE_VERSION
)
from src.verify.reasons import Reason, ALLOWED

KST = ZoneInfo("Asia/Seoul")
LAT_M = 111195.0  # 1도당 약 111,195m (위도)

@pytest.fixture
def base_citycodes_df(tmp_path):
    raw_file = tmp_path / "citycode_raw.json"
    raw_file.write_text('{"response": {"body": {"items": {"item": [{"citycode": "31130", "cityname": "남양주시"}]}}}}', encoding="utf-8")
    
    df = pd.DataFrame([{
        "citycode": "31130",
        "cityname": "남양주시",
        "raw_response_path": str(raw_file)
    }])
    return df

@pytest.fixture
def base_stops_df():
    df = pd.DataFrame([{
        "citycode": "31130",
        "nodeid": "GGB222001318",
        "nodenm": "도농역",
        "nodeno": 22001,
        "gpslati": 37.608000,
        "gpslong": 127.158000,
        "retrieved_at": "2026-09-02T23:24:48+00:00"
    }])
    return df

@pytest.fixture
def base_smoke_df(tmp_path):
    smoke_raw = tmp_path / "smoke_raw.json"
    smoke_raw.write_text("""{
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": {
                    "item": [{"routeid": "GGB222000009", "arrtime": 1800, "routeno": 9}]
                }
            }
        }
    }""", encoding="utf-8")

    df = pd.DataFrame([{
        "citycode": "31130",
        "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T14:00:00+09:00",
        "outcome": "ok_with_items",
        "items_with_routeid_and_arrtime": 1,
        "schema_version": "v2",
        "raw_path": str(smoke_raw)
    }])
    return df

@pytest.fixture
def base_complexes_df():
    return pd.DataFrame([{
        "cluster_id": "A10022364",
        "complex_name": "다산유보라마크뷰",
        "lat": 37.6054452938772,
        "lon": 127.15415038050315,
        "crs": "EPSG:4326"
    }])

@pytest.fixture
def base_stop_row(base_citycodes_df):
    raw_path = base_citycodes_df.iloc[0]["raw_response_path"]
    return {
        "cluster_id": "A10022364",
        "citycode": "31130",
        "nodeid": "GGB222001318",
        "nodenm": "도농역",
        "direction_label": "다산자이 방면",
        "stop_lat": 37.608000,
        "stop_lon": 127.158000,
        "raw_citycode_response_path": raw_path,
        "coord_verify_method": "kakao_map_cadastral_crosscheck",
        "verified_by": "reviewer_kim",
        "verified_at": "2026-09-03T12:00:00+09:00",
        "review_status": "pending",
        "notes": "정상 확인"
    }

# 1. 임계값 경계 순수 함수 검증
@pytest.mark.parametrize("d,limit,exp", [
    (50.0, 50, True), (50.000001, 50, False),
    (800.0, 800, True), (800.000001, 800, False),
])
def test_threshold_is_inclusive(d, limit, exp):
    assert within(d, limit) is exp

# 2. P1-3: within()이 evaluate_gate 경로에서 실제 적용되는지 검증하는 통합 테스트
def test_evaluate_gate_integrates_within_thresholds(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row_45 = base_stop_row.copy()
    row_45["stop_lat"] = 37.608000 + (45.0 / LAT_M)
    res_45 = evaluate_gate(row_45, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res_45.gates["G2"] is True

    row_55 = base_stop_row.copy()
    row_55["stop_lat"] = 37.608000 + (55.0 / LAT_M)
    res_55 = evaluate_gate(row_55, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res_55.gates["G2"] is False
    assert Reason.G2_COORD_DELTA in res_55.rejection_reasons

    c_lat = float(base_complexes_df.iloc[0]["lat"])
    c_lon = float(base_complexes_df.iloc[0]["lon"])

    # 780m 거리: 조인된 클러스터 좌표 기준 780m
    row_780 = base_stop_row.copy()
    row_780["stop_lat"] = c_lat + (780.0 / LAT_M)
    row_780["stop_lon"] = c_lon
    row_780["cluster_lat"] = 99.9999  # 행에 적힌 가짜 값은 무시되어야 함
    stops_780 = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318", "nodenm": "도농역",
        "nodeno": 22001, "gpslati": row_780["stop_lat"], "gpslong": row_780["stop_lon"],
        "retrieved_at": "2026-09-02T23:24:48+00:00"
    }])
    res_780 = evaluate_gate(row_780, base_citycodes_df, stops_780, base_smoke_df, base_complexes_df)
    assert res_780.gates["G3"] is True

    # 820m 거리: 조인된 클러스터 좌표 기준 820m
    row_820 = base_stop_row.copy()
    row_820["stop_lat"] = c_lat + (820.0 / LAT_M)
    row_820["stop_lon"] = c_lon
    row_820["cluster_lat"] = c_lat  # 행에 아무리 가까운 값을 적어도 무시됨
    stops_820 = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318", "nodenm": "도농역",
        "nodeno": 22001, "gpslati": row_820["stop_lat"], "gpslong": row_820["stop_lon"],
        "retrieved_at": "2026-09-02T23:24:48+00:00"
    }])
    res_820 = evaluate_gate(row_820, base_citycodes_df, stops_820, base_smoke_df, base_complexes_df)
    assert res_820.gates["G3"] is False
    assert Reason.G3_DISTANCE in res_820.rejection_reasons

# 3. P1-1: INPUT_NOT_PENDING 분리 및 gates 전원 None 미평가 검증
def test_evaluate_gate_rejects_non_pending_status(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    for bad_status in ["ai_draft", "candidate", "human_verified", "", None]:
        row = base_stop_row.copy()
        row["review_status"] = bad_status
        res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
        assert res.passed is False
        assert set(res.gates.keys()) == {"G1", "G2", "G3", "G4", "G5", "G6"}
        assert all(v is None for v in res.gates.values()), "미평가 행의 gates는 전원 None이어야 합니다."
        assert res.rejection_reasons == (Reason.INPUT_NOT_PENDING,)

# 4. P0-3: smoke_log 다중 행 선택 순서 독립성 검증 (v2 우선, 최신 시각 우선)
def test_g4_authoritative_row_selection_order_independent(base_stop_row, base_citycodes_df, base_stops_df, base_complexes_df):
    row_v1 = {
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T12:30:00+09:00",
        "outcome": "ok_with_items", "items_with_routeid_and_arrtime": pd.NA,
        "schema_version": "v1"
    }
    row_v2 = {
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T12:30:00+09:00",
        "outcome": "ok_with_items", "items_with_routeid_and_arrtime": 24,
        "schema_version": "v2"
    }

    # 순서 1: v1 먼저, v2 나중
    df_order1 = pd.DataFrame([row_v1, row_v2])
    res1 = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, df_order1, base_complexes_df)
    assert res1.gates["G4"] is True, "v2가 선택되어 G4를 통과해야 합니다."

    # 순서 2: v2 먼저, v1 나중 (순서 뒤집음)
    df_order2 = pd.DataFrame([row_v2, row_v1])
    res2 = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, df_order2, base_complexes_df)
    assert res2.gates["G4"] is True, "행 순서를 뒤집어도 동일하게 v2가 선택되어야 합니다."

# 5. G4 ok_empty 테스트
def test_ok_empty_smoke_fails_g4_with_no_bus_running_now(base_stop_row, base_citycodes_df, base_stops_df, tmp_path, base_complexes_df):
    smoke_raw = tmp_path / "smoke_empty.json"
    smoke_raw.write_text('{"response": {"header": {"resultCode": "00"}, "body": {"items": ""}}}', encoding="utf-8")
    
    smoke_df = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T14:00:00+09:00",
        "outcome": "ok_empty", "items_with_routeid_and_arrtime": 0,
        "schema_version": "v2", "raw_path": str(smoke_raw)
    }])
    
    res = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, smoke_df, base_complexes_df)
    assert not res.passed
    assert res.gates["G4"] is False
    assert Reason.G4_NO_BUS_RUNNING_NOW in res.rejection_reasons
    assert "stop_invalid" not in [r.value for r in res.rejection_reasons]

# 6. G4 items_with_routeid_and_arrtime 결측 시 G4_EVIDENCE_MISSING
def test_g4_evidence_missing_when_column_absent(base_stop_row, base_citycodes_df, base_stops_df, tmp_path, base_complexes_df):
    smoke_raw = tmp_path / "smoke_v1.json"
    smoke_raw.write_text('{"response": {"header": {"resultCode": "00"}}}', encoding="utf-8")
    
    smoke_df = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T14:00:00+09:00",
        "outcome": "ok_with_items",
        "schema_version": "v1", "raw_path": str(smoke_raw)
    }])
    
    res = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, smoke_df, base_complexes_df)
    assert res.gates["G4"] is False
    assert Reason.G4_EVIDENCE_MISSING in res.rejection_reasons
    assert Reason.G4_NO_BUS_RUNNING_NOW not in res.rejection_reasons

# 7. G2 컬럼 불신뢰 및 하버사인 재계산 강제 검증
def test_g2_must_recompute_not_trust_column(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["coord_delta_m"] = 0.0
    row["stop_lat"] = 37.608000 + (90.0 / LAT_M)
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res.gates["G2"] is False
    assert Reason.G2_COORD_DELTA in res.rejection_reasons
    assert pytest.approx(res.metrics["coord_delta_recomputed_m"], abs=2) == 90

# 8. P1-4: G2 정류소 부재 검증 (G2_stop_not_found_in_tago)
def test_g2_stop_not_found(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["nodeid"] = "GGB_NON_EXISTENT_99999"
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res.gates["G2"] is False
    assert Reason.G2_STOP_NOT_FOUND in res.rejection_reasons
    assert res.rejection_reasons[0].value == "G2_stop_not_found_in_tago"

# 9. G3 컬럼 불신뢰 및 하버사인 재계산 강제 검증
def test_g3_must_recompute_not_trust_column(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["recomputed_dist_m"] = 10.0  # 가짜 거리 (무시되어야 함)
    row["cluster_lat"] = 37.200000   # 가짜 위도 (무시되어야 함)
    row["cluster_lon"] = 127.070000  # 가짜 경도 (무시되어야 함)

    c_lat = float(base_complexes_df.iloc[0]["lat"])
    c_lon = float(base_complexes_df.iloc[0]["lon"])
    row["stop_lat"] = c_lat + (900.0 / LAT_M)
    row["stop_lon"] = c_lon

    stops_df = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318", "nodenm": "도농역",
        "nodeno": 22001, "gpslati": row["stop_lat"], "gpslong": row["stop_lon"],
        "retrieved_at": "2026-09-02T23:24:48+00:00"
    }])
    res = evaluate_gate(row, base_citycodes_df, stops_df, base_smoke_df, base_complexes_df)
    assert res.gates["G3"] is False
    assert Reason.G3_DISTANCE in res.rejection_reasons
    assert pytest.approx(res.metrics["dist_recomputed_m"], abs=15) == 900
    # 행에 입력된 가짜 값은 metrics에만 참고로 보존됨
    assert res.metrics.get("cluster_lat_input") == 37.200000
    assert res.metrics.get("cluster_lon_input") == 127.070000

# 10. P0-1: G6 direction_label 공백/None/float('nan')/'nan' 거부 테스트
def test_direction_label_empty_or_none_or_nan(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    for bad_label in ["", "   ", None, float("nan"), "nan", "NAN", "None", "null"]:
        row = base_stop_row.copy()
        row["direction_label"] = bad_label
        res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
        assert res.gates["G6"] is False, f"방향라벨 {bad_label!r}은 G6을 통과해서는 안 됩니다."
        assert Reason.G6_NO_DIRECTION in res.rejection_reasons

# 11. G4 토요일 10:00 KST 요일 위반 단정 테스트
def test_smoke_taken_on_saturday_fails_g4_not_weekday(base_stop_row, base_citycodes_df, base_stops_df, tmp_path, base_complexes_df):
    smoke_raw = tmp_path / "smoke_sat.json"
    smoke_raw.write_text('{"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": [{"routeid": "GGB1", "arrtime": 100}]}}}}', encoding="utf-8")
    
    smoke_df = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-05T10:00:00+09:00",
        "outcome": "ok_with_items", "items_with_routeid_and_arrtime": 1,
        "schema_version": "v2", "raw_path": str(smoke_raw)
    }])
    
    res = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, smoke_df, base_complexes_df)
    assert res.gates["G4"] is False
    assert Reason.G4_NOT_WEEKDAY in res.rejection_reasons

# 12. G4 평일 08:59 / 18:01 시간 경계 테스트
def test_g4_time_boundary_weekday(base_stop_row, base_citycodes_df, base_stops_df, tmp_path, base_complexes_df):
    smoke_raw = tmp_path / "smoke_t.json"
    smoke_raw.write_text('{"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": [{"routeid": "GGB1", "arrtime": 100}]}}}}', encoding="utf-8")

    smoke_df_early = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T08:59:00+09:00",
        "outcome": "ok_with_items", "items_with_routeid_and_arrtime": 1,
        "schema_version": "v2", "raw_path": str(smoke_raw)
    }])
    res_early = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, smoke_df_early, base_complexes_df)
    assert res_early.gates["G4"] is False
    assert Reason.G4_OUTSIDE_HOURS in res_early.rejection_reasons

    smoke_df_late = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T18:01:00+09:00",
        "outcome": "ok_with_items", "items_with_routeid_and_arrtime": 1,
        "schema_version": "v2", "raw_path": str(smoke_raw)
    }])
    res_late = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, smoke_df_late, base_complexes_df)
    assert res_late.gates["G4"] is False
    assert Reason.G4_OUTSIDE_HOURS in res_late.rejection_reasons

# 13. G4 api_error 테스트
def test_g4_api_error_reason_not_no_bus_running_now(base_stop_row, base_citycodes_df, base_stops_df, tmp_path, base_complexes_df):
    smoke_raw = tmp_path / "smoke_err.json"
    smoke_raw.write_text('{"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "ERROR"}}}', encoding="utf-8")

    smoke_df = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": "2026-09-03T14:00:00+09:00",
        "outcome": "api_error", "items_with_routeid_and_arrtime": 0,
        "schema_version": "v2", "raw_path": str(smoke_raw)
    }])
    res = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, smoke_df, base_complexes_df)
    assert res.gates["G4"] is False
    assert Reason.G4_API_ERROR in res.rejection_reasons
    assert Reason.G4_NO_BUS_RUNNING_NOW not in res.rejection_reasons

# 14. G1 citycode 부재 검증
def test_g1_citycode_missing(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["citycode"] = "99999"
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res.gates["G1"] is False
    assert Reason.G1_CITYCODE_MISSING in res.rejection_reasons

# 15. G1 raw 파일 부재 검증 (NaN, 공백, 부재 파일 전수 탈락 검증)
def test_g1_raw_file_missing_fails(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    for bad_path in ["non_existent_file_path_12345.json", "", None, float("nan"), "nan", "NAN", "None"]:
        row = base_stop_row.copy()
        row["raw_citycode_response_path"] = bad_path
        res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
        assert res.gates["G1"] is False
        assert Reason.G1_RAW_MISSING in res.rejection_reasons

# 16. G5 coord_verify_method auto / api 거부 테스트
def test_g5_coord_verify_method_auto_or_api_fails(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    for bad_method in ["auto", "AUTO", "api", "api-based", "auto_generated", "API_CALL", "check_with_api"]:
        row = base_stop_row.copy()
        row["coord_verify_method"] = bad_method
        res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
        assert res.gates["G5"] is False, f"{bad_method}는 G5를 통과해서는 안 됩니다."
        assert Reason.G5_INVALID_METHOD in res.rejection_reasons

# 16-1. P1-1: G5 coord_verify_method 가 NaN일 때 "nan"으로 우회하지 않고 MISSING_VERIFIER 탈락 검증
def test_g5_coord_verify_method_nan_fails_missing_verifier(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    for bad_method in [None, float("nan"), "nan", "NAN", "None", "null", "", "   "]:
        row = base_stop_row.copy()
        row["coord_verify_method"] = bad_method
        res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
        assert res.gates["G5"] is False, f"검증방법 {bad_method!r}은 G5를 통과해서는 안 됩니다."
        assert Reason.G5_MISSING_VERIFIER in res.rejection_reasons

# 16-2. P1-2: rapid_transit_map_check 처럼 단어 내부에 'api'가 부분문자열로 들어있으나 토큰이 다른 경우 오탐 없이 통과 검증
def test_g5_coord_verify_method_token_matching_prevents_false_positive(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    for valid_method in ["rapid_transit_map_check", "human_onsite_map_review", "kakao_map_cadastral_crosscheck"]:
        row = base_stop_row.copy()
        row["coord_verify_method"] = valid_method
        res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
        assert res.gates["G5"] is True, f"{valid_method}는 토큰 단위 매칭에 의해 G5를 통과해야 합니다."

# 17. G5 검증자 정보 누락 테스트
def test_g5_missing_verifier(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row_no_by = base_stop_row.copy()
    row_no_by["verified_by"] = ""
    res_no_by = evaluate_gate(row_no_by, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res_no_by.gates["G5"] is False
    assert Reason.G5_MISSING_VERIFIER in res_no_by.rejection_reasons

    row_no_at = base_stop_row.copy()
    row_no_at["verified_at"] = None
    res_no_at = evaluate_gate(row_no_at, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res_no_at.gates["G5"] is False
    assert Reason.G5_MISSING_VERIFIER in res_no_at.rejection_reasons

# 18. evaluate_gate 호출 후 입력 row 무변형 검증
def test_evaluate_gate_does_not_mutate_input_row(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    original = copy.deepcopy(base_stop_row)
    evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert base_stop_row == original

# 19. 모든 게이트 통과 시 passed=True, review_status='pending' 유지
def test_all_gates_pass_review_status_stays_pending(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    assert row["review_status"] == "pending"
    
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res.passed is True
    assert all(res.gates.values())
    assert len(res.rejection_reasons) == 0
    assert row["review_status"] == "pending"
    assert res.review_status == "pending"

# 20. GateResult 계약 검사
def test_gate_result_contract(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["citycode"] = "invalid_code"
    row["direction_label"] = ""
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    
    assert set(res.gates.keys()) == {"G1", "G2", "G3", "G4", "G5", "G6"}
    for r in res.rejection_reasons:
        assert r in ALLOWED, f"{r}은 ALLOWED에 정의되지 않은 사유 코드입니다."
    if res.passed:
        assert res.rejection_reasons == ()

# 21. P0-F: 유니코드 NFC/NFD 한글 정규화 해시 일치 검증
def test_compute_registry_content_hash_nfc_nfd_equivalence():
    import unicodedata
    from src.verify.stop_gate import compute_registry_content_hash
    
    # "박재홍" - NFC vs NFD
    name_nfc = unicodedata.normalize("NFC", "박재홍")
    name_nfd = unicodedata.normalize("NFD", "박재홍")
    assert name_nfc != name_nfd, "NFC와 NFD는 서로 다른 바이트 시퀀스여야 합니다."

    row_nfc = pd.DataFrame([{
        "cluster_id": "A1", "citycode": "31130", "nodeid": "N1",
        "stop_lat": 37.1234567, "stop_lon": 127.1234567, "direction_label": "도농역 방면",
        "coord_verify_method": "kakao_map_cadastral_crosscheck",
        "raw_citycode_response_path": "path.json", "verified_by": name_nfc,
        "verified_at": "2026-09-03T12:00:00+09:00", "notes": "메모"
    }])
    row_nfd = pd.DataFrame([{
        "cluster_id": "A1", "citycode": "31130", "nodeid": "N1",
        "stop_lat": 37.1234567, "stop_lon": 127.1234567, "direction_label": "도농역 방면",
        "coord_verify_method": "kakao_map_cadastral_crosscheck",
        "raw_citycode_response_path": "path.json", "verified_by": name_nfd,
        "verified_at": "2026-09-03T12:00:00+09:00", "notes": "메모"
    }])
    
    hash_nfc = compute_registry_content_hash(row_nfc)
    hash_nfd = compute_registry_content_hash(row_nfd)
    assert hash_nfc == hash_nfd, "NFC와 NFD는 정규화 해시가 정확히 일치해야 합니다."

# 22. P1-9: G1 raw JSON 내용에 해당 citycode가 없으면 탈락
def test_g1_citycode_not_in_raw_fails(base_stop_row, base_stops_df, base_smoke_df, tmp_path, base_complexes_df):
    raw_other = tmp_path / "citycode_other.json"
    raw_other.write_text('{"response": {"body": {"items": {"item": [{"citycode": "99999", "cityname": "기타시"}]}}}}', encoding="utf-8")
    
    citycodes_df = pd.DataFrame([{
        "citycode": "31130", "cityname": "남양주시", "raw_response_path": str(raw_other)
    }])
    row = base_stop_row.copy()
    row["raw_citycode_response_path"] = str(raw_other)
    res = evaluate_gate(row, citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res.gates["G1"] is False
    assert Reason.G1_CITYCODE_NOT_IN_RAW in res.rejection_reasons

# 23. P1-6: G4 스모크 증거 30일 초과 시 G4_STALE_SMOKE 탈락
def test_g4_smoke_older_than_30_days_fails_stale(base_stop_row, base_citycodes_df, base_stops_df, tmp_path, base_complexes_df):
    smoke_raw = tmp_path / "smoke_old.json"
    smoke_raw.write_text('{"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": [{"routeid": "1", "arrtime": 100}]}}}}', encoding="utf-8")
    
    # 60일 전 평일 낮 12:00 KST
    old_time = (datetime.now(KST) - timedelta(days=60)).strftime("%Y-%m-%d") + "T12:00:00+09:00"
    smoke_df = pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "smoke_test_at_kst": old_time, "outcome": "ok_with_items",
        "items_with_routeid_and_arrtime": 1, "schema_version": "v2", "raw_path": str(smoke_raw)
    }])
    res = evaluate_gate(base_stop_row, base_citycodes_df, base_stops_df, smoke_df, base_complexes_df)
    assert res.gates["G4"] is False
    assert Reason.G4_STALE_SMOKE in res.rejection_reasons

# 24. P1-4: G5 verified_at 형식 검증 (오프셋 미포함 문자열 및 미래 시각 거부)
def test_g5_verified_at_invalid_format_or_future_fails(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    for bad_at in ["2026-09-03", "어제", "2026/09/03 12:00", "invalid_date"]:
        row = base_stop_row.copy()
        row["verified_at"] = bad_at
        res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
        assert res.gates["G5"] is False
        assert Reason.G5_INVALID_VERIFIED_AT in res.rejection_reasons

    # 미래 시각 (내일)
    future_time = (datetime.now(KST) + timedelta(days=1)).isoformat()
    row_future = base_stop_row.copy()
    row_future["verified_at"] = future_time
    res_future = evaluate_gate(row_future, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res_future.gates["G5"] is False
    assert Reason.G5_INVALID_VERIFIED_AT in res_future.rejection_reasons

# 25. P1-8: G6 direction_label이 nodenm과 동일한 경우(정류소명 복사) 거부
def test_g6_direction_equals_nodenm_fails(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["direction_label"] = "도농역"  # nodenm과 동일
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df)
    assert res.gates["G6"] is False
    assert Reason.G6_DIRECTION_EQUALS_NODENM in res.rejection_reasons

# 26. Phase 2: cluster_lat/lon 직접 주입 대신 complex_geocode.csv 조인으로 원정밀도 좌표 획득 및 통과 검증
def test_g3_joins_complex_geocode_and_passes(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    # 입력 행에서 cluster_lat/lon을 의도적으로 제거
    row.pop("cluster_lat", None)
    row.pop("cluster_lon", None)
    row["cluster_id"] = "A10022364"
    
    # 임시 complex_geocode 데이터프레임 주입 (정류소 근방 145m 지점)
    complexes_df = pd.DataFrame([{
        "cluster_id": "A10022364",
        "lat": 37.6054452938772,
        "lon": 127.15415038050315
    }])
    
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, complexes_df=complexes_df)
    assert res.gates["G3"] is True
    assert within(res.metrics["dist_recomputed_m"], 800.0)
    assert Reason.G3_CLUSTER_NOT_FOUND not in res.rejection_reasons

# 27. Phase 2: cluster_id 미존재 시 G3_CLUSTER_NOT_FOUND 탈락 및 NaN 조용한 통과 차단 검증
def test_g3_missing_cluster_id_fails_cluster_not_found(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row.pop("cluster_lat", None)
    row.pop("cluster_lon", None)
    row["cluster_id"] = "NON_EXISTENT_CLUSTER_9999"
    
    # 대상 cluster_id가 없는 데이터프레임
    complexes_df = pd.DataFrame([{
        "cluster_id": "A10022364",
        "lat": 37.605445,
        "lon": 127.154150
    }])
    
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, complexes_df=complexes_df)
    assert res.gates["G3"] is False
    assert Reason.G3_CLUSTER_NOT_FOUND in res.rejection_reasons
    assert pd.isna(res.metrics.get("dist_recomputed_m"))

# 28. Phase 2a: 동일 cluster_id 다중 매칭 시 G3_CLUSTER_AMBIGUOUS 탈락 및 match_count 노출 검증
def test_g3_cluster_ambiguous_fails_multiple_matches(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["cluster_id"] = "A10022364"
    
    # 동일 cluster_id 가 2건 존재하는 경우
    ambiguous_df = pd.DataFrame([
        {"cluster_id": "A10022364", "lat": 37.605445, "lon": 127.154150, "crs": "EPSG:4326"},
        {"cluster_id": "A10022364", "lat": 37.606000, "lon": 127.155000, "crs": "EPSG:4326"},
    ])
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, complexes_df=ambiguous_df)
    assert res.gates["G3"] is False
    assert Reason.G3_CLUSTER_AMBIGUOUS in res.rejection_reasons
    assert res.metrics.get("cluster_match_count") == 2
    assert pd.isna(res.metrics.get("dist_recomputed_m"))

# 29. Phase 2a: crs != 'EPSG:4326' 일 때 G3_INVALID_CRS 탈락 검증
def test_g3_invalid_crs_fails(base_stop_row, base_citycodes_df, base_stops_df, base_smoke_df, base_complexes_df):
    row = base_stop_row.copy()
    row["cluster_id"] = "A10022364"
    
    # crs가 EPSG:5179 (GRS80 UTM-K) 인 경우
    bad_crs_df = pd.DataFrame([{
        "cluster_id": "A10022364",
        "lat": 37.605445,
        "lon": 127.154150,
        "crs": "EPSG:5179"
    }])
    res = evaluate_gate(row, base_citycodes_df, base_stops_df, base_smoke_df, complexes_df=bad_crs_df)
    assert res.gates["G3"] is False
    assert Reason.G3_INVALID_CRS in res.rejection_reasons
    assert pd.isna(res.metrics.get("dist_recomputed_m"))


