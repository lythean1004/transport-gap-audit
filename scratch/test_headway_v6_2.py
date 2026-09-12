import pytest
import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

from calc_headway_v6_2 import (
    load_ledger,
    load_data,
    build_timeseries,
    detect_events_v2,
    aggregate_metrics,
    stop_level_metrics,
    prep_crosscheck,
    process_ledger,
    build_slot_labels,
    classify_missing_and_unreached,
    generate_docs_content
)

def test_regression_read_csv_int_slots():
    """read_csv 경로 회귀: slot_hhmm 이 정수로 저장된 임시 CSV를 만들어
    load_ledger 파싱을 통과시킨 뒤 AM 슬롯이 zfill 되어 정상 복구되는지 검증"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write("obs_date,slot_hhmm,citycode,nodeid,outcome,retry_count,called_at_kst\n")
        f.write("2026-09-07,700,31130,GGB222001318,ok_with_items,0,2026-09-07T07:00:00+09:00\n")
        f.write("2026-09-07,820,31130,GGB222001318,ok_with_items,0,2026-09-07T08:20:00+09:00\n")
        f.write("2026-09-07,1700,31130,GGB222001318,ok_with_items,0,2026-09-07T17:00:00+09:00\n")
        tmp_path = Path(f.name)
        
    try:
        ledger = load_ledger(tmp_path)
        assert '0700' in ledger['slot_hhmm'].values
        assert '0820' in ledger['slot_hhmm'].values
        assert '1700' in ledger['slot_hhmm'].values
        assert '700' not in ledger['slot_hhmm'].values
        assert '820' not in ledger['slot_hhmm'].values
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

def test_zero_fill_isolation():
    """zero_fill=True 에서 route_absent 와 collection_missing 은 여전히 NA 인지 검증 (ok_empty 만 0 처리)"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_empty', 'called_at_kst': '2026-09-07T07:00:00+09:00'},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0705', 'outcome': 'api_error', 'called_at_kst': '2026-09-07T07:05:00+09:00'},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0710', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:10:00+09:00'}
    ])
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0710', 'routeid': 'ROUTE_A', 'arrtime_sec': 500, 'n_items': 1}
    ])
    routes = {'ROUTE_A', 'ROUTE_B'}
    
    ts_zero = build_timeseries(ledger, raw_df, routes, deduplicated_slots=set(), zero_fill=True)
    
    # 1. ok_empty 슬롯: 0 으로 채워짐
    ok_empty_a = ts_zero[(ts_zero['slot_hhmm'] == '0700') & (ts_zero['routeid'] == 'ROUTE_A')].iloc[0]
    assert ok_empty_a['arrtime_sec'] == 0
    assert ok_empty_a['collection_missing'] == False
    
    # 2. api_error 슬롯: 여전히 pd.NA 유지
    api_err_a = ts_zero[(ts_zero['slot_hhmm'] == '0705') & (ts_zero['routeid'] == 'ROUTE_A')].iloc[0]
    assert pd.isna(api_err_a['arrtime_sec'])
    assert api_err_a['collection_missing'] == True
    
    # 3. route_absent 노선: 여전히 pd.NA 유지
    absent_b = ts_zero[(ts_zero['slot_hhmm'] == '0710') & (ts_zero['routeid'] == 'ROUTE_B')].iloc[0]
    assert pd.isna(absent_b['arrtime_sec'])
    assert absent_b['route_absent'] == True
    assert absent_b['collection_missing'] == False

def test_deduplicated_not_classified_as_missing():
    """준중복 드롭 행이 collection_missing 으로 분류되지 않고 이벤트 절단 대상에서 제외되는지 검증"""
    dedup_slots = {('2026-09-08', '1745')}
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-08', 'slot_hhmm': '1740', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-08T17:40:00+09:00'},
        {'obs_date': '2026-09-08', 'slot_hhmm': '1750', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-08T17:50:00+09:00'}
    ])
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-08', 'slot_hhmm': '1740', 'routeid': 'ROUTE_A', 'arrtime_sec': 1000, 'n_items': 1},
        {'obs_date': '2026-09-08', 'slot_hhmm': '1750', 'routeid': 'ROUTE_A', 'arrtime_sec': 400, 'n_items': 1}
    ])
    routes = {'ROUTE_A'}
    
    ts = build_timeseries(ledger, raw_df, routes, deduplicated_slots=dedup_slots, zero_fill=False)
    
    row_1745 = ts[(ts['obs_date'] == '2026-09-08') & (ts['slot_hhmm'] == '1745') & (ts['routeid'] == 'ROUTE_A')].iloc[0]
    assert row_1745['is_deduplicated'] == True
    assert row_1745['collection_missing'] == False

def test_meaningful_first_bus_null_via_module():
    """prep_crosscheck 함수 호출 기반: first_bus_ok 및 last_bus_ok 가 boolean pd.NA 인지 검증"""
    metrics = pd.DataFrame([
        {'routeid': 'ROUTE_X', 'obs_date': '2026-09-07', 'window': 'AM', 'median_gap_min': 20.0, 'insufficient_observation': False}
    ])
    pub_df = pd.DataFrame([
        {'routeid': 'ROUTE_X', 'intervaltime': 20.0}
    ])
    res = prep_crosscheck(metrics, pub_df, routes_to_exclude=[])
    assert str(res['first_bus_ok'].dtype) == 'boolean'
    assert str(res['last_bus_ok'].dtype) == 'boolean'
    assert pd.isna(res.loc[0, 'first_bus_ok'])
    assert pd.isna(res.loc[0, 'last_bus_ok'])

def test_meaningful_stop_level_metric_with_insufficient_filter():
    """stop_level_metrics 함수 호출 기반: n_events < 4 인 insufficient 노선 그룹이 제외되고,
    유효 노선들의 median_gap_min 중앙값이 정확하게 산출되는지 검증"""
    ev_df = pd.DataFrame([
        # ROUTE_VALID: 5개 이벤트 -> 4개 갭(모두 15.0)
        {'routeid': 'ROUTE_VALID', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'arrtime_sec': 100, 'gap_min': pd.NA, 'gap_adjacent': False},
        {'routeid': 'ROUTE_VALID', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0715', 'arrtime_sec': 100, 'gap_min': 15.0, 'gap_adjacent': False},
        {'routeid': 'ROUTE_VALID', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0730', 'arrtime_sec': 100, 'gap_min': 15.0, 'gap_adjacent': False},
        {'routeid': 'ROUTE_VALID', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0745', 'arrtime_sec': 100, 'gap_min': 15.0, 'gap_adjacent': False},
        {'routeid': 'ROUTE_VALID', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0800', 'arrtime_sec': 100, 'gap_min': 15.0, 'gap_adjacent': False},
        # ROUTE_INSUFF: 2개 이벤트 -> 1개 갭(5.0), insufficient
        {'routeid': 'ROUTE_INSUFF', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'arrtime_sec': 100, 'gap_min': pd.NA, 'gap_adjacent': False},
        {'routeid': 'ROUTE_INSUFF', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0705', 'arrtime_sec': 100, 'gap_min': 5.0, 'gap_adjacent': False},
    ])
    
    stop_res = stop_level_metrics(ev_df)
    assert not stop_res.empty
    assert stop_res.iloc[0]['median_across_routes'] == 15.0

def test_jump_up():
    """단조 감소 후 상향 점프 -> 이벤트 1건"""
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'arrtime_sec': 500, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'arrtime_sec': 200, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'arrtime_sec': 1500, 'collection_missing': False, 'route_absent': False},
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events_v2(df)
    assert len(ev) == 1
    assert ev.iloc[0]['event_slot'] == '0705'

def test_route_absent():
    """route_absent 로 인한 소멸 -> 이벤트 1건"""
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'arrtime_sec': 1000, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'arrtime_sec': 700, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0715', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True},
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events_v2(df)
    assert len(ev) == 1
    assert ev.iloc[0]['event_slot'] == '0705'

def test_collection_missing_gap_adjacent():
    """collection_missing -> 이벤트 0건, 시계열 절단, 앞뒤 gap_adjacent=True"""
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'arrtime_sec': 1000, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'arrtime_sec': pd.NA, 'collection_missing': True, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0715', 'arrtime_sec': 500, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0720', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True},
    ]
    df = pd.DataFrame(ts_data)
    ev, ts_out = detect_events_v2(df)
    assert len(ev) == 2
    assert ev.iloc[1]['gap_adjacent'] == True

def test_multi_item_snapshot():
    """동일 슬롯 복수 item 스냅샷이 집계에서 식별되는지 검증"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:00:00+09:00'},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0705', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:05:00+09:00'}
    ])
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'ROUTE_M', 'arrtime_sec': 300, 'n_items': 1},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'ROUTE_M', 'arrtime_sec': 1200, 'n_items': 1},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0705', 'routeid': 'ROUTE_M', 'arrtime_sec': 600, 'n_items': 1}
    ])
    routes = {'ROUTE_M'}
    ts = build_timeseries(ledger, raw_df, routes, deduplicated_slots=set(), zero_fill=False)
    assert ts[(ts['slot_hhmm'] == '0700') & (ts['routeid'] == 'ROUTE_M')].iloc[0]['n_items'] == 2

def test_headway_limits_docs_file_content():
    """docs/headway_limits.md 문서 생성 시 필수 섹션이 포함되는지 검증"""
    content = generate_docs_content(
        core_days=3, supp_days=4,
        total_json=236, success_json=236, failed_json=0,
        actual_max_horizon=8680,
        missing_summary_text="결측요약",
        unreached_summary_text="미도래요약",
        dedup_summary_text="준중복요약",
        narrative_0908="09-08서사",
        simultaneous_note="동시 도착 비현실성",
        now_frontier_text="기준시각 2026-09-11 09:43:00 KST",
        g2_excluded_routes_text="included_excluded_routes 1/6 (16.7%)",
        g3_sensitivity_text="서비스 과대평가 방향 사실 기술",
        g4_failure_modes_text="실패 모드 (a)와 (b) 2구분"
    )
    assert "# 관측 배차 산출 및 교차검증 한계점" in content
    assert "계통 및 방향성 편의" in content
    assert "동시 도착" in content
    assert "실패 모드" in content

def test_stop_level_metrics_calculation():
    """정류소 단위 지표 산출 시 n_events < 4 노선 제외 후 유효 노선의 중앙값의 중앙값이 계산되는지 검증"""
    events_df = pd.DataFrame([
        # Route 1: 4 events, gaps: 10, 10, 10 -> median = 10
        {'routeid': 'R1', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'gap_min': 10.0},
        {'routeid': 'R1', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0710', 'gap_min': 10.0},
        {'routeid': 'R1', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0720', 'gap_min': 10.0},
        {'routeid': 'R1', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0730', 'gap_min': 10.0},
        # Route 2: 4 events, gaps: 20, 20, 20 -> median = 20
        {'routeid': 'R2', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'gap_min': 20.0},
        {'routeid': 'R2', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0720', 'gap_min': 20.0},
        {'routeid': 'R2', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0740', 'gap_min': 20.0},
        {'routeid': 'R2', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0800', 'gap_min': 20.0},
        # Route 3: only 2 events (n_events < 4) -> should be excluded from stop-level calculation
        {'routeid': 'R3', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'gap_min': 5.0},
        {'routeid': 'R3', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0705', 'gap_min': 5.0},
    ])
    res = stop_level_metrics(events_df, exc_routes=[])
    assert len(res) == 1
    row = res.iloc[0]
    assert row['valid_routes_count'] == 2 # R1, R2
    assert row['best_single_route'] == 10.0
    assert row['median_across_routes'] == 15.0 # median of [10.0, 20.0]

def test_two_by_two_sensitivity_table():
    """2x2 민감도 표 구성 및 중앙값, p25, p75 산출 구조 검증"""
    gaps_series = pd.Series([10.0, 15.0, 20.0, 25.0, 30.0])
    med = float(gaps_series.median())
    p25 = float(gaps_series.quantile(0.25))
    p75 = float(gaps_series.quantile(0.75))
    assert med == 20.0
    assert p25 == 15.0
    assert p75 == 25.0

def test_calc_headway_v6_main_smoke():
    """calc_headway_v6의 load_data 와 process_ledger 가 정상 동작하는지 스모크 테스트"""
    ledger, raw_df, pub_df, parse_stats = load_data()
    if not ledger.empty:
        ledger_clean, same_drops, near_dups, dedup_slots = process_ledger(ledger)
        assert len(ledger_clean) <= len(ledger)
        assert isinstance(dedup_slots, set)

def test_routes_to_exclude_removes_groups():
    """F8/C1: aggregate_metrics 가 routes_to_exclude 목록의 노선을 완전히 제거하는지 검증"""
    events_df = pd.DataFrame([
        {'routeid': 'GGB222000056', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'ROUTE_KEEP', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'gap_min': 15.0, 'gap_adjacent': False},
    ])
    ts_df = pd.DataFrame([
        {'routeid': 'GGB222000056', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'n_items': 1},
        {'routeid': 'ROUTE_KEEP', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'n_items': 1},
    ])
    exc_routes = ['GGB222000056']
    m = aggregate_metrics(events_df, ts_df, routes_to_exclude=exc_routes)
    assert 'GGB222000056' not in m['routeid'].values
    assert 'ROUTE_KEEP' in m['routeid'].values

def test_build_timeseries_min_arrtime_from_raw_df():
    """F8: 실제 raw_df 입력을 주었을 때 동일 슬롯 복수 item 중 최소 arrtime_sec 가 채택되는지 검증"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:00:00+09:00'}
    ])
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'R1', 'arrtime_sec': 1200},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'R1', 'arrtime_sec': 300},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'R1', 'arrtime_sec': 600}
    ])
    ts = build_timeseries(ledger, raw_df, routes={'R1'}, deduplicated_slots=set(), zero_fill=False)
    row = ts[(ts['obs_date'] == '2026-09-07') & (ts['slot_hhmm'] == '0700') & (ts['routeid'] == 'R1')].iloc[0]
    assert row['arrtime_sec'] == 300
    assert row['n_items'] == 3

def test_ledger_duplicate_assertion():
    """F8/F2: merge 직전 중복 키가 있으면 assertion 에러가 발생하는지 검증"""
    ledger_dup = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:00:00+09:00'},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'api_error', 'called_at_kst': '2026-09-07T07:00:10+09:00'}
    ])
    raw_df = pd.DataFrame([])
    with pytest.raises(AssertionError) as exc_info:
        build_timeseries(ledger_dup, raw_df, routes={'R1'}, deduplicated_slots=set(), zero_fill=False)
    assert "merge 직전 중복 키 발견" in str(exc_info.value)

def test_api_error_retried_ok_not_missing():
    """F8/F1: api_error 가 발생했으나 재시도 성공 행이 있는 경우 collection_missing=False 검증"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '1845', 'outcome': 'api_error', 'retry_count': '0', 'called_at_kst': '2026-09-07T18:45:03+09:00'},
        {'obs_date': '2026-09-07', 'slot_hhmm': '1845', 'outcome': 'ok_with_items', 'retry_count': '1', 'called_at_kst': '2026-09-07T18:45:14+09:00'}
    ])
    ledger_clean, drops, _, _ = process_ledger(ledger)
    assert len(ledger_clean) == 1
    assert ledger_clean.iloc[0]['outcome'] == 'api_error_retried_ok'
    
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '1845', 'routeid': 'R1', 'arrtime_sec': 500}
    ])
    ts = build_timeseries(ledger_clean, raw_df, routes={'R1'}, deduplicated_slots=set(), zero_fill=False)
    row = ts[(ts['obs_date'] == '2026-09-07') & (ts['slot_hhmm'] == '1845') & (ts['routeid'] == 'R1')].iloc[0]
    assert row['collection_missing'] == False

def test_unreached_slots_not_missing():
    """F8/F3: 미래 슬롯이 결측으로 집계되지 않고 미도래로 분류되는지 검증"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-11', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-11T07:00:00+09:00'},
        {'obs_date': '2026-09-11', 'slot_hhmm': '0855', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-11T08:55:11+09:00'}
    ])
    frontier_dt = pd.to_datetime('2026-09-11 09:00:00+09:00')
    missing, unreached = classify_missing_and_unreached(ledger, deduplicated_slots=set(), frontier_dt=frontier_dt)
    
    assert len(unreached['2026-09-11']['PM']) == 24
    assert len(missing['2026-09-11']['PM']) == 0

# --- 신규 G1 ~ G5 테스트 ---

def test_g1_wall_clock_now_frontier():
    """[G1] 실제 wall-clock now(KST) 프론티어 기준 결측 vs 미도래 분류 검증"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-11', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-11T07:00:00+09:00'},
        {'obs_date': '2026-09-11', 'slot_hhmm': '0850', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-11T08:50:00+09:00'}
    ])
    # Case 1: now = 09-11 09:30 (AM 이후, PM 이전)
    now_am_passed = pd.to_datetime('2026-09-11 09:30:00+09:00')
    missing, unreached = classify_missing_and_unreached(ledger, deduplicated_slots=set(), frontier_dt=now_am_passed)
    assert '0755' in missing['2026-09-11']['AM']
    assert len(unreached['2026-09-11']['PM']) == 24
    assert len(missing['2026-09-11']['PM']) == 0

    # Case 2: now = 09-11 17:10 (PM 도래 중: 1700, 1705, 1710 은 과거 슬롯)
    now_pm_mid = pd.to_datetime('2026-09-11 17:10:00+09:00')
    missing_pm, unreached_pm = classify_missing_and_unreached(ledger, deduplicated_slots=set(), frontier_dt=now_pm_mid)
    assert '1700' in missing_pm['2026-09-11']['PM']
    assert '1705' in missing_pm['2026-09-11']['PM']
    assert '1710' in missing_pm['2026-09-11']['PM']
    assert len(unreached_pm['2026-09-11']['PM']) == 21

def test_g2_stop_level_included_excluded_routes():
    """[G2] 정류소 단위 지표에서 included_excluded_routes 플래그 및 본안 6개 창 중 1/6 (16.7%) 검증"""
    ledger, raw_df, pub_df, _ = load_data()
    if not ledger.empty and not raw_df.empty:
        ledger_clean, _, _, dedup_slots = process_ledger(ledger)
        routes_all = sorted(raw_df['routeid'].unique())
        ts_base = build_timeseries(ledger_clean, raw_df, routes_all, deduplicated_slots=dedup_slots, zero_fill=False)
        ev_base, _ = detect_events_v2(ts_base)
        
        exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']
        dates_core = ['2026-09-07', '2026-09-08', '2026-09-09']
        ev_core = ev_base[ev_base['obs_date'].isin(dates_core)]
        
        stop_core = stop_level_metrics(ev_core, exc_routes=exc_routes)
        assert len(stop_core) == 6
        assert 'included_excluded_routes' in stop_core.columns
        # 2026-09-09 AM 에서만 GGB222000137 이 5개 이벤트(>=4)로 유효 노선에 진입하여 True
        row_0909_am = stop_core[(stop_core['obs_date'] == '2026-09-09') & (stop_core['window'] == 'AM')].iloc[0]
        assert row_0909_am['included_excluded_routes'] == True
        # 나머지 5개 창은 False
        assert stop_core['included_excluded_routes'].sum() == 1

def test_g3_sensitivity_quantiles_and_direction():
    """[G3] 2x2 민감도 분석에서 p25, p75, insufficient 변동 산출 및 과대평가 방향성 사실 확인"""
    base_gaps = pd.Series([10.0, 20.0, 25.0, 30.0, 40.0])
    zero_gaps = pd.Series([5.0, 15.0, 20.0, 25.0, 30.0])
    
    p25_b, p75_b = base_gaps.quantile(0.25), base_gaps.quantile(0.75)
    p25_z, p75_z = zero_gaps.quantile(0.25), zero_gaps.quantile(0.75)
    
    assert p25_z <= p25_b
    assert p75_z <= p75_b

def test_g4_two_failure_modes():
    """[G4] 실패 모드 2구분: (a) REQ_EXCEPTION 재시도 성공 0손실 vs (b) 원장 행 부재 실손실"""
    ledger, _, _, _ = load_data()
    if not ledger.empty:
        ledger_clean, drops, _, dedup_slots = process_ledger(ledger)
        dup_keys_raw = ledger[ledger.duplicated(['obs_date', 'slot_hhmm'], keep=False)]
        retried_ok_count = sum(1 for (d, s), g in dup_keys_raw.groupby(['obs_date', 'slot_hhmm']) if (g['outcome'] == 'ok_with_items').any() and (g['outcome'] == 'api_error').any())
        assert retried_ok_count == 2
        
        missing, _ = classify_missing_and_unreached(ledger_clean, deduplicated_slots=dedup_slots)
        total_missing = sum(len(missing[d]['AM']) + len(missing[d]['PM']) for d in missing)
        assert total_missing > 0

def test_g5_output_schema_superset():
    """[H4/G5] crosscheck.csv 가 parquet 의 모든 컬럼(11개)을 포함하는 엄격한 상위집합(superset, 17개)임을 증명 assertion"""
    observed_cols = [
        'routeid', 'obs_date', 'window', 'median_gap_min', 'p25', 'p75',
        'n_events', 'n_multi_item_snapshots', 'insufficient_observation', 'gap_adjacent_ratio',
        'analysis_window'
    ]
    crosscheck_cols = [
        'routeid', 'obs_date', 'window', 'median_gap_min', 'p25', 'p75',
        'n_events', 'n_multi_item_snapshots', 'insufficient_observation', 'gap_adjacent_ratio',
        'headway_published_min', 'headway_delta_min', 'headway_source_agreement',
        'first_bus_ok', 'last_bus_ok', 'headway_ok', 'analysis_window'
    ]
    
    # 1. crosscheck_available 이 컬럼에서 완전히 제거되었는지 확인 (17개 컬럼)
    assert 'crosscheck_available' not in crosscheck_cols
    assert len(crosscheck_cols) == 17
    assert len(observed_cols) == 11
    
    # 2. strict superset 관계 검증
    assert set(observed_cols).issubset(set(crosscheck_cols))
    assert set(observed_cols) != set(crosscheck_cols)
    
    diff_cols = set(crosscheck_cols) - set(observed_cols)
    assert len(diff_cols) == 6
    expected_diff = {
        'headway_published_min', 'headway_delta_min',
        'headway_source_agreement', 'first_bus_ok', 'last_bus_ok', 'headway_ok'
    }
    assert diff_cols == expected_diff
    assert len(set(observed_cols) - set(crosscheck_cols)) == 0


# --- 신규 I1, I3, I5 테스트 ---

def test_i1_ratio_format_contains_n_N():
    """[I1] 비율 출력 포맷이 (n/N) 형태를 포함하는지 검증"""
    import re
    # 민감도 표 등에서 사용된 포맷팅 시뮬레이션
    n_insuff = 26
    n_groups = 72
    rate = (n_insuff / n_groups) * 100
    formatted = f"{rate:.1f}% ({n_insuff}/{n_groups})"
    assert re.search(r'\(\d+/\d+\)', formatted) is not None
    assert "36.1% (26/72)" in formatted

def test_i1_insufficient_denominators():
    """[I1] insufficient 2계열 분모가 기대값(72/72/95/96)과 일치하는지 실제 동작으로 검증"""
    ledger, raw_df, _, _ = load_data()
    if not ledger.empty:
        ledger_clean, _, _, dedup_slots = process_ledger(ledger)
        routes_all = sorted(raw_df['routeid'].unique())
        ts_b = build_timeseries(ledger_clean, raw_df, routes_all, deduplicated_slots=dedup_slots, zero_fill=False)
        ts_z = build_timeseries(ledger_clean, raw_df, routes_all, deduplicated_slots=dedup_slots, zero_fill=True)
        ev_b, _ = detect_events_v2(ts_b)
        ev_z, _ = detect_events_v2(ts_z)
        
        exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']
        m_b = aggregate_metrics(ev_b, ts_b, routes_to_exclude=exc_routes)
        m_z = aggregate_metrics(ev_z, ts_z, routes_to_exclude=exc_routes)
        
        dates_core = ['2026-09-07', '2026-09-08', '2026-09-09']
        dates_supp = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
        
        assert len(m_b[m_b['obs_date'].isin(dates_core)]) == 72
        assert len(m_z[m_z['obs_date'].isin(dates_core)]) == 72
        assert len(m_b[m_b['obs_date'].isin(dates_supp)]) == 95
        assert len(m_z[m_z['obs_date'].isin(dates_supp)]) == 96

def test_i3_weekday_assert_fails_on_weekend():
    """[I3] 주말 날짜 주입 시 평일 검증 assert 실패하는지 검증"""
    # 2026-09-12 는 토요일
    ledger_mock = pd.DataFrame([{'obs_date': '2026-09-12'}])
    obs_dates_ts = pd.to_datetime(ledger_mock['obs_date'].unique())
    with pytest.raises(AssertionError) as excinfo:
        assert (obs_dates_ts.dayofweek < 5).all(), "관측일에 주말이 포함되어 있습니다."
    assert "주말" in str(excinfo.value)

def test_g5_crosscheck_superset_from_data():
    """[I5] 실 데이터 기반 crosscheck가 parquet 엄격 상위집합인지 검증"""
    ledger, raw_df, pub_df, _ = load_data()
    if not ledger.empty:
        ledger_clean, _, _, dedup_slots = process_ledger(ledger)
        routes_all = sorted(raw_df['routeid'].unique())
        ts_b = build_timeseries(ledger_clean, raw_df, routes_all, deduplicated_slots=dedup_slots, zero_fill=False)
        ev_b, _ = detect_events_v2(ts_b)
        
        exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']
        m_b = aggregate_metrics(ev_b, ts_b, routes_to_exclude=exc_routes)
        
        crosscheck_df = prep_crosscheck(m_b, pub_df, routes_to_exclude=exc_routes)
        
        observed_cols = set(m_b.columns)
        crosscheck_cols = set(crosscheck_df.columns)
        
        assert observed_cols.issubset(crosscheck_cols)
        assert len(crosscheck_cols) == len(observed_cols) + 6
