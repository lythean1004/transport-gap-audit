import pytest
import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

from calc_headway_v5 import (
    load_ledger,
    build_timeseries,
    detect_events_v2,
    aggregate_metrics,
    stop_level_metrics,
    prep_crosscheck,
    process_ledger,
    build_slot_labels,
    classify_missing_and_unreached
)

def test_regression_read_csv_int_slots():
    """read_csv 경로 회귀: slot_hhmm 이 정수로 저장된 임시 CSV를 만들어
    load_ledger 파싱을 통과시킨 뒤 AM 슬롯이 zfill 되어 정상 복구되는지 검증
    (테스트 코드 내부 수동 zfill 금지)"""
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
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True}, # 이벤트 1 (0700)
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'arrtime_sec': pd.NA, 'collection_missing': True, 'route_absent': False},  # 결측 절단
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0715', 'arrtime_sec': 500, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0720', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True}, # 이벤트 2 (0715)
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events_v2(df)
    assert len(ev) == 2
    assert ev.iloc[0]['event_slot'] == '0700'
    assert ev.iloc[1]['event_slot'] == '0715'
    assert ev.iloc[1]['gap_adjacent'] == True

def test_right_censored():
    """그룹 말단 미확정 -> right-censored, 이벤트로 세지 않음"""
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'arrtime_sec': 1000, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'arrtime_sec': 700, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'arrtime_sec': 400, 'collection_missing': False, 'route_absent': False},
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events_v2(df)
    assert len(ev) == 0

def test_multi_item_snapshot():
    """n_items > 1 인 스냅샷(슬롯) 수가 집계 메트릭의 n_multi_item_snapshots 에 올바르게 카운트되는지 검증"""
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'n_items': 2},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'n_items': 1},
    ]
    ts_df = pd.DataFrame(ts_data)
    events_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0700', 'gap_min': pd.NA, 'gap_adjacent': False}
    ]
    ev_df = pd.DataFrame(events_data)
    met = aggregate_metrics(ev_df, ts_df, routes_to_exclude=[])
    assert len(met) == 1
    assert met.iloc[0]['n_multi_item_snapshots'] == 1

def test_insufficient_observation():
    """n_events < 4 -> insufficient, 중앙값 제외"""
    events_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0705', 'arrtime_sec': 200, 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0715', 'arrtime_sec': 200, 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0725', 'arrtime_sec': 200, 'gap_min': 10.0, 'gap_adjacent': False},
    ]
    ev_df = pd.DataFrame(events_data)
    ts_df = pd.DataFrame([{'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'n_items': 1}])
    met = aggregate_metrics(ev_df, ts_df, routes_to_exclude=[])
    assert len(met) == 1
    assert met.iloc[0]['insufficient_observation'] == True
    assert pd.isna(met.iloc[0]['median_gap_min'])

# === 신규 F8 테스트 5건 ===

def test_routes_to_exclude_removes_groups():
    """F8-1: aggregate_metrics(routes_to_exclude=[...]) 가 실제로 해당 노선 그룹을 완전히 제거하는지 검증"""
    events_data = [
        {'routeid': 'EXC_1', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0705', 'arrtime_sec': 100, 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'KEEP_1', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0705', 'arrtime_sec': 100, 'gap_min': 10.0, 'gap_adjacent': False},
    ]
    ev_df = pd.DataFrame(events_data)
    ts_df = pd.DataFrame([
        {'routeid': 'EXC_1', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'n_items': 1},
        {'routeid': 'KEEP_1', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'n_items': 1},
    ])
    
    met = aggregate_metrics(ev_df, ts_df, routes_to_exclude=['EXC_1'])
    assert 'EXC_1' not in met['routeid'].values
    assert 'KEEP_1' in met['routeid'].values

def test_build_timeseries_min_arrtime_from_raw_df():
    """F8-2: build_timeseries 가 동일 슬롯 복수 item 에서 최소 arrtime_sec 를 채택하는지
    (실제 raw_df 입력을 전달하여 검증)"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:00:00+09:00'}
    ])
    # 동일 노선, 동일 슬롯에 복수 도착정보 (600초와 200초)
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'ROUTE_A', 'arrtime_sec': 600},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'ROUTE_A', 'arrtime_sec': 200},
    ])
    routes = {'ROUTE_A'}
    
    ts = build_timeseries(ledger, raw_df, routes, zero_fill=False)
    row = ts[(ts['obs_date'] == '2026-09-07') & (ts['slot_hhmm'] == '0700') & (ts['routeid'] == 'ROUTE_A')].iloc[0]
    
    assert row['arrtime_sec'] == 200
    assert row['n_items'] == 2

def test_ledger_duplicate_assertion():
    """F8-3: 중복 키 원장 투입 시 merge 직전 assertion 이 정상 작동하는지 검증"""
    # 중복 키를 가진 ledger
    dup_ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:00:00+09:00'},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:00:05+09:00'}
    ])
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'ROUTE_A', 'arrtime_sec': 300}
    ])
    routes = {'ROUTE_A'}
    
    with pytest.raises(AssertionError):
        build_timeseries(dup_ledger, raw_df, routes)

def test_api_error_retried_ok_not_missing():
    """F8-4: api_error 이지만 동일 키 성공 행이 있는 경우 collection_missing=False 로 분류되는지 검증"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '1845', 'outcome': 'api_error_retried_ok', 'called_at_kst': '2026-09-07T18:45:14+09:00'}
    ])
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '1845', 'routeid': 'ROUTE_A', 'arrtime_sec': 500}
    ])
    routes = {'ROUTE_A'}
    
    ts = build_timeseries(ledger, raw_df, routes, zero_fill=False)
    row = ts[(ts['obs_date'] == '2026-09-07') & (ts['slot_hhmm'] == '1845') & (ts['routeid'] == 'ROUTE_A')].iloc[0]
    
    assert row['collection_missing'] == False
    assert row['arrtime_sec'] == 500

def test_unreached_slots_not_missing():
    """F8-5: slot_dt > max_called_at 인 미도래 슬롯이 결측으로 집계되지 않고 미도래로 분류되는지 검증"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-11', 'slot_hhmm': '0700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-11T07:00:00+09:00'},
        {'obs_date': '2026-09-11', 'slot_hhmm': '0855', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-11T08:55:00+09:00'}
    ])
    # 0705 는 결측(과거), 1700 은 미도래(미래)
    missing, unreached = classify_missing_and_unreached(ledger, deduplicated_slots=set())
    
    # 09-11 에 대해 0705 는 결측, 1700 은 미도래
    assert '0705' in missing.get('2026-09-11', {}).get('AM', [])
    assert '1700' in unreached.get('2026-09-11', {}).get('PM', [])
    assert '1700' not in missing.get('2026-09-11', {}).get('PM', [])
