"""
tests/test_stop_gate_cli.py
Phase 3 CLI promote 명령 단위 테스트
"""
import pytest
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from src.verify.stop_gate import promote_stop, compute_registry_content_hash

KST = ZoneInfo("Asia/Seoul")

def test_promote_stop_refuses_when_not_passed(tmp_path):
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"
    
    df_reg = pd.DataFrame([{
        "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB222001318",
        "review_status": "pending", "verified_by": "reviewer_kim"
    }])
    df_reg.to_csv(registry_file, index=False)
    
    pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "passed": False, "rejection_reasons": "G2_coord_delta_exceeded"
    }]).to_csv(report_file, index=False)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 1,
            "gate_code_version": "v2.3",
            "registry_content_hash": compute_registry_content_hash(df_reg)
        }, f)
    
    with pytest.raises(SystemExit) as exc_info:
        promote_stop(
            citycode="31130", nodeid="GGB222001318", reviewer="reviewer_kim",
            registry_csv=str(registry_file), report_csv=str(report_file),
            meta_json=str(meta_file), promotion_log_csv=str(log_file)
        )
    assert exc_info.value.code == 1

def test_promote_stop_refuses_when_zero_row_report(tmp_path):
    """P0-1: 0행 리포트 상태에서 promote 호출 시 거부"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    pd.DataFrame(columns=["citycode", "nodeid", "passed"]).to_csv(report_file, index=False)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 0,
            "gate_code_version": "v2.3",
            "registry_content_hash": "empty_registry"
        }, f)

    with pytest.raises(SystemExit) as exc_info:
        promote_stop(
            citycode="31130", nodeid="GGB222001318", reviewer="reviewer_kim",
            registry_csv=str(registry_file), report_csv=str(report_file),
            meta_json=str(meta_file), promotion_log_csv=str(log_file)
        )
    assert exc_info.value.code == 1

def test_promote_stop_refuses_when_input_source_mismatch(tmp_path):
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    df_reg = pd.DataFrame([{
        "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB222001318",
        "review_status": "pending", "verified_by": "reviewer_kim"
    }])
    df_reg.to_csv(registry_file, index=False)

    pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "passed": True, "rejection_reasons": ""
    }]).to_csv(report_file, index=False)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": "exports/other_candidates.csv",  # 불일치
            "input_row_count": 1,
            "gate_code_version": "v2.3",
            "registry_content_hash": compute_registry_content_hash(df_reg)
        }, f)

    with pytest.raises(SystemExit) as exc_info:
        promote_stop(
            citycode="31130", nodeid="GGB222001318", reviewer="reviewer_kim",
            registry_csv=str(registry_file), report_csv=str(report_file),
            meta_json=str(meta_file), promotion_log_csv=str(log_file)
        )
    assert exc_info.value.code == 1

def test_promote_refuses_when_registry_content_modified(tmp_path):
    """P0-3: 좌표 등 비-status 컬럼 변경 시 해시 불일치로 stale 거부"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    df_reg = pd.DataFrame([{
        "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB222001318",
        "stop_lat": 37.608000, "review_status": "pending", "verified_by": "reviewer_kim"
    }])
    df_reg.to_csv(registry_file, index=False)

    pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "passed": True, "rejection_reasons": ""
    }]).to_csv(report_file, index=False)

    # 과거 해시 저장
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 1,
            "gate_code_version": "v2.3",
            "registry_content_hash": "old_hash_value_12345"
        }, f)

    with pytest.raises(SystemExit) as exc_info:
        promote_stop(
            citycode="31130", nodeid="GGB222001318", reviewer="reviewer_kim",
            registry_csv=str(registry_file), report_csv=str(report_file),
            meta_json=str(meta_file), promotion_log_csv=str(log_file)
        )
    assert exc_info.value.code == 1

def test_promote_consecutive_two_stops_succeeds_with_same_report(tmp_path):
    """P0-3: 같은 리포트로 서로 다른 두 정류소를 연속 승격 성공 검증 (데드락 해소)"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    row1 = {
        "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB1",
        "nodenm": "정류소1", "direction_label": "서울 방면", "stop_lat": 37.608000, "stop_lon": 127.158000,
        "coord_verify_method": "kakao_map_cadastral", "verified_by": "reviewer_kim",
        "verified_at": "2026-09-03T11:00:00+09:00", "review_status": "pending", "notes": ""
    }
    row2 = {
        "cluster_id": "A10022365", "citycode": "31130", "nodeid": "GGB2",
        "nodenm": "정류소2", "direction_label": "다산 방면", "stop_lat": 37.609000, "stop_lon": 127.159000,
        "coord_verify_method": "kakao_map_cadastral", "verified_by": "reviewer_kim",
        "verified_at": "2026-09-03T11:00:00+09:00", "review_status": "pending", "notes": ""
    }
    df_reg = pd.DataFrame([row1, row2])
    df_reg.to_csv(registry_file, index=False)

    pd.DataFrame([
        {"citycode": "31130", "nodeid": "GGB1", "passed": True, "rejection_reasons": ""},
        {"citycode": "31130", "nodeid": "GGB2", "passed": True, "rejection_reasons": ""}
    ]).to_csv(report_file, index=False)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 2,
            "gate_code_version": "v2.3",
            "registry_content_hash": compute_registry_content_hash(df_reg)
        }, f)

    # 1번째 정류소 승격
    promote_stop(
        citycode="31130", nodeid="GGB1", reviewer="reviewer_kim",
        registry_csv=str(registry_file), report_csv=str(report_file),
        meta_json=str(meta_file), promotion_log_csv=str(log_file)
    )

    # 2번째 정류소 연속 승격 (같은 리포트로 즉시 실행)
    promote_stop(
        citycode="31130", nodeid="GGB2", reviewer="reviewer_kim",
        registry_csv=str(registry_file), report_csv=str(report_file),
        meta_json=str(meta_file), promotion_log_csv=str(log_file)
    )

    df_after = pd.read_csv(registry_file)
    assert len(df_after) == 2, "행 수는 2개로 유지되어야 합니다."
    assert df_after.loc[df_after["nodeid"] == "GGB1", "review_status"].iloc[0] == "human_verified"
    assert df_after.loc[df_after["nodeid"] == "GGB2", "review_status"].iloc[0] == "human_verified"

    df_log = pd.read_csv(log_file)
    assert len(df_log) == 2, "promotion_log.csv에 2건의 승격 이력이 기록되어야 합니다."

def test_check_7d_preconditions_blocks_when_zero_human_verified(tmp_path):
    from src.verify.stop_gate import check_7d_preconditions

    non_existent = tmp_path / "absent.csv"
    with pytest.raises(RuntimeError, match="파일이 존재하지 않습니다"):
        check_7d_preconditions(str(non_existent))

    empty_reg = tmp_path / "stop_registry_pending.csv"
    pd.DataFrame([{"review_status": "pending"}]).to_csv(empty_reg, index=False)
    with pytest.raises(RuntimeError, match="human_verified 상태의 정류소가 0건입니다"):
        check_7d_preconditions(str(empty_reg))

    valid_reg = tmp_path / "stop_registry_valid.csv"
    pd.DataFrame([{"review_status": "human_verified"}]).to_csv(valid_reg, index=False)
    count = check_7d_preconditions(str(valid_reg))
    assert count == 1

def test_run_gate_on_registry_rejects_header_mismatch(tmp_path):
    """P0-4: 레지스트리 헤더가 REGISTRY_COLUMNS와 불일치 시 거부"""
    from src.verify.stop_gate import run_gate_on_registry
    
    registry_file = tmp_path / "bad_registry.csv"
    report_file = tmp_path / "report.csv"
    meta_file = tmp_path / "report.meta.json"
    
    # 잘못된 헤더 (컬럼 누락 또는 오타)
    pd.DataFrame([{"wrong_col": 1, "citycode": "31130"}]).to_csv(registry_file, index=False)
    
    with pytest.raises(ValueError, match="레지스트리 헤더 스키마 불일치"):
        run_gate_on_registry(
            registry_csv=str(registry_file),
            output_report_csv=str(report_file),
            output_meta_json=str(meta_file)
        )

def test_promote_stop_refuses_when_gate_version_mismatch(tmp_path):
    """P1-1: 사이드카 메타의 gate_code_version 불일치 시 거부"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    pd.DataFrame([{
        "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB222001318",
        "review_status": "pending"
    }]).to_csv(registry_file, index=False)

    pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "passed": True, "rejection_reasons": ""
    }]).to_csv(report_file, index=False)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 1,
            "gate_code_version": "v1.0-outdated",  # 버전 불일치
            "registry_content_hash": "some_hash"
        }, f)

    with pytest.raises(SystemExit) as exc_info:
        promote_stop(
            citycode="31130", nodeid="GGB222001318", reviewer="reviewer_kim",
            registry_csv=str(registry_file), report_csv=str(report_file),
            meta_json=str(meta_file), promotion_log_csv=str(log_file)
        )
    assert exc_info.value.code == 1

def test_promote_stop_refuses_when_no_registry_sentinel(tmp_path):
    """P1-1: 사이드카 메타의 registry_content_hash가 센티널일 때 거부"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    pd.DataFrame([{
        "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB222001318",
        "review_status": "pending"
    }]).to_csv(registry_file, index=False)

    pd.DataFrame([{
        "citycode": "31130", "nodeid": "GGB222001318",
        "passed": True, "rejection_reasons": ""
    }]).to_csv(report_file, index=False)

    for sentinel in ["no_registry", "empty_registry", ""]:
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({
                "report_generated_at": datetime.now(KST).isoformat(),
                "input_source": str(registry_file).replace("\\", "/"),
                "input_row_count": 1,
                "gate_code_version": "v2.3",
                "registry_content_hash": sentinel  # 센티널 해시
            }, f)

        with pytest.raises(SystemExit) as exc_info:
            promote_stop(
                citycode="31130", nodeid="GGB222001318", reviewer="reviewer_kim",
                registry_csv=str(registry_file), report_csv=str(report_file),
                meta_json=str(meta_file), promotion_log_csv=str(log_file)
            )
        assert exc_info.value.code == 1

def test_promote_refuses_when_target_not_in_report(tmp_path):
    """P1-2: 대상 정류소가 리포트에 아예 없는 경우 거부"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    df_reg = pd.DataFrame([{
        "cluster_id": "A1", "citycode": "31130", "nodeid": "GGB222001318",
        "review_status": "pending"
    }])
    df_reg.to_csv(registry_file, index=False)

    # 리포트에는 다른 정류소만 있음
    pd.DataFrame([{
        "citycode": "31130", "nodeid": "OTHER_NODE",
        "passed": True, "rejection_reasons": ""
    }]).to_csv(report_file, index=False)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 1,
            "gate_code_version": "v2.3",
            "registry_content_hash": compute_registry_content_hash(df_reg)
        }, f)

    with pytest.raises(SystemExit) as exc_info:
        promote_stop(
            citycode="31130", nodeid="GGB222001318", reviewer="reviewer_kim",
            registry_csv=str(registry_file), report_csv=str(report_file),
            meta_json=str(meta_file), promotion_log_csv=str(log_file)
        )
    assert exc_info.value.code == 1

def test_promote_refuses_when_row_count_mismatch(tmp_path):
    """P1-2: 리포트 행 수 != 레지스트리 행 수 거부"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    # 레지스트리에는 2행
    df_reg = pd.DataFrame([
        {"cluster_id": "A1", "citycode": "31130", "nodeid": "GGB1", "review_status": "pending"},
        {"cluster_id": "A2", "citycode": "31130", "nodeid": "GGB2", "review_status": "pending"}
    ])
    df_reg.to_csv(registry_file, index=False)

    pd.DataFrame([
        {"citycode": "31130", "nodeid": "GGB1", "passed": True, "rejection_reasons": ""}
    ]).to_csv(report_file, index=False)

    # 메타의 input_row_count는 1 (불일치)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 1,
            "gate_code_version": "v2.3",
            "registry_content_hash": compute_registry_content_hash(df_reg)
        }, f)

    with pytest.raises(SystemExit) as exc_info:
        promote_stop(
            citycode="31130", nodeid="GGB1", reviewer="reviewer_kim",
            registry_csv=str(registry_file), report_csv=str(report_file),
            meta_json=str(meta_file), promotion_log_csv=str(log_file)
        )
    assert exc_info.value.code == 1


def test_promote_stop_succeeds_with_mixed_human_verified_and_pending(tmp_path):
    """Phase 2a: human_verified 1행 + pending 1행 혼재 상태에서 pending 통과 건 승격 성공 검증"""
    report_file = tmp_path / "stop_gate_report.csv"
    meta_file = tmp_path / "stop_gate_report.meta.json"
    registry_file = tmp_path / "stop_registry.csv"
    log_file = tmp_path / "promotion_log.csv"

    # human_verified 행과 pending 행 혼재
    df_reg = pd.DataFrame([
        {
            "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB222001318",
            "stop_lat": 37.608, "stop_lon": 127.158, "direction_label": "방면A",
            "coord_verify_method": "kakao_map_cadastral_crosscheck", "raw_citycode_response_path": "raw.json",
            "review_status": "human_verified", "verified_by": "prior_reviewer", "verified_at": "2026-09-01T10:00:00+09:00", "notes": "기승격"
        },
        {
            "cluster_id": "A10022364", "citycode": "31130", "nodeid": "GGB222001319",
            "stop_lat": 37.609, "stop_lon": 127.159, "direction_label": "방면B",
            "coord_verify_method": "kakao_map_cadastral_crosscheck", "raw_citycode_response_path": "raw.json",
            "review_status": "pending", "verified_by": "reviewer_kim", "verified_at": "2026-09-03T12:00:00+09:00", "notes": "신규 검증"
        }
    ])
    df_reg.to_csv(registry_file, index=False)

    # 리포트: 전체 2행 모두 기록 (비-pending은 passed=False/INPUT_NOT_PENDING, pending은 passed=True)
    pd.DataFrame([
        {
            "citycode": "31130", "nodeid": "GGB222001318",
            "passed": False, "rejection_reasons": "input_not_pending", "review_status": "human_verified"
        },
        {
            "citycode": "31130", "nodeid": "GGB222001319",
            "passed": True, "rejection_reasons": "", "review_status": "pending"
        }
    ]).to_csv(report_file, index=False)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "report_generated_at": datetime.now(KST).isoformat(),
            "input_source": str(registry_file).replace("\\", "/"),
            "input_row_count": 2,
            "gate_code_version": "v2.3",
            "registry_content_hash": compute_registry_content_hash(df_reg)
        }, f)

    # pending 상태였던 GGB222001319 승격 수행 -> 성공해야 함
    promote_stop(
        citycode="31130", nodeid="GGB222001319", reviewer="reviewer_kim",
        registry_csv=str(registry_file), report_csv=str(report_file),
        meta_json=str(meta_file), promotion_log_csv=str(log_file)
    )

    # 검증: 레지스트리에서 해당 행이 human_verified로 업데이트됨
    updated_reg = pd.read_csv(registry_file)
    row_promoted = updated_reg[updated_reg["nodeid"] == "GGB222001319"].iloc[0]
    assert row_promoted["review_status"] == "human_verified"
    assert row_promoted["verified_by"] == "reviewer_kim"

    # 기존 human_verified 행은 그대로 유지됨
    row_existing = updated_reg[updated_reg["nodeid"] == "GGB222001318"].iloc[0]
    assert row_existing["review_status"] == "human_verified"
    assert row_existing["verified_by"] == "prior_reviewer"

    # 프로모션 로그 기록 확인
    log_df = pd.read_csv(log_file)
    assert len(log_df) == 1
    assert log_df.iloc[0]["nodeid"] == "GGB222001319"



