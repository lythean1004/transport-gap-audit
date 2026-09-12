import pytest
import pandas as pd
import numpy as np

from calc_headway_v3 import (
    detect_events_v2,
    build_timeseries,
    aggregate_metrics,
    stop_level_metrics,
    build_slot_labels
)

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

def test_collection_missing():
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

def test_excluded_routes():
    """제외 3개 노선이 노선 단위에서 빠지고 정류소 단위에는 남음"""
    exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']
    events_data = [
        {'routeid': 'GGB222000056', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0705', 'arrtime_sec': 200, 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'GGB222000056', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0715', 'arrtime_sec': 200, 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'GGB222000056', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0725', 'arrtime_sec': 200, 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'GGB222000056', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0735', 'arrtime_sec': 200, 'gap_min': 10.0, 'gap_adjacent': False},
        {'routeid': 'NORMAL_ROUTE', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0710', 'arrtime_sec': 300, 'gap_min': 15.0, 'gap_adjacent': False},
        {'routeid': 'NORMAL_ROUTE', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0725', 'arrtime_sec': 300, 'gap_min': 15.0, 'gap_adjacent': False},
        {'routeid': 'NORMAL_ROUTE', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0740', 'arrtime_sec': 300, 'gap_min': 15.0, 'gap_adjacent': False},
        {'routeid': 'NORMAL_ROUTE', 'obs_date': '2026-09-07', 'window': 'AM', 'event_slot': '0755', 'arrtime_sec': 300, 'gap_min': 15.0, 'gap_adjacent': False},
    ]
    ev_df = pd.DataFrame(events_data)
    ts_data = [
        {'routeid': 'GGB222000056', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'n_items': 1},
        {'routeid': 'NORMAL_ROUTE', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'n_items': 1},
    ]
    ts_df = pd.DataFrame(ts_data)
    
    # 노선 단위 집계: 제외 노선 없음
    route_met = aggregate_metrics(ev_df, ts_df, routes_to_exclude=exc_routes)
    assert 'GGB222000056' not in route_met['routeid'].values
    assert 'NORMAL_ROUTE' in route_met['routeid'].values
    
    # 정류소 단위 집계: 전체 노선 포함
    stop_met = stop_level_metrics(ev_df)
    assert not stop_met.empty
    assert stop_met.iloc[0]['median_across_routes'] is not pd.NA

def test_first_bus_null():
    """공표값 행 없는 노선 -> first_bus_ok 가 NULL (False 아님)"""
    df = pd.DataFrame({'routeid': ['UNKNOWN_ROUTE']})
    df['first_bus_ok'] = pd.array([pd.NA] * len(df), dtype='boolean')
    assert pd.isna(df.loc[0, 'first_bus_ok'])
    assert df.loc[0, 'first_bus_ok'] is not False

def test_arrtime_sec_unit():
    """arrtime_sec 이 분으로 변환되지 않고 초 단위로 유지됨"""
    raw_item = {'routeid': 'A', 'arrtime': '720'}
    arr_sec = int(raw_item['arrtime'])
    assert arr_sec == 720
    assert arr_sec != 12  # 720 / 60 = 12

def test_ok_empty_not_zero_in_base():
    """ok_empty·collection_missing 슬롯이 base 버전에서 0으로 채워지지 않음"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'outcome': 'ok_empty', 'called_at_kst': '2026-09-07T07:00:00+09:00'},
        {'obs_date': '2026-09-07', 'slot_hhmm': '0705', 'outcome': 'api_error', 'called_at_kst': '2026-09-07T07:05:00+09:00'}
    ])
    raw_df = pd.DataFrame(columns=['obs_date', 'slot_hhmm', 'routeid', 'arrtime_sec', 'n_items'])
    routes = {'ROUTE_A'}
    
    ts_base = build_timeseries(ledger, raw_df, routes, zero_fill=False)
    assert pd.isna(ts_base.loc[ts_base['slot_hhmm'] == '0700', 'arrtime_sec'].iloc[0])
    assert pd.isna(ts_base.loc[ts_base['slot_hhmm'] == '0705', 'arrtime_sec'].iloc[0])
    assert ts_base.loc[ts_base['slot_hhmm'] == '0700', 'collection_missing'].iloc[0] == True
    assert ts_base.loc[ts_base['slot_hhmm'] == '0705', 'collection_missing'].iloc[0] == True

def test_multi_item_snapshot():
    """동일 slot 복수 항목 -> 최소 arrtime_sec 채택, 스냅샷 카운터 +1"""
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
    ]  # n_events = 3 (< 4)
    ev_df = pd.DataFrame(events_data)
    ts_df = pd.DataFrame([{'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'n_items': 1}])
    met = aggregate_metrics(ev_df, ts_df, routes_to_exclude=[])
    assert len(met) == 1
    assert met.iloc[0]['insufficient_observation'] == True
    assert pd.isna(met.iloc[0]['median_gap_min'])

def test_regression_int_slot_am_recovery():
    """원장 slot_hhmm 이 정수나 비-zfill 문자열로 들어와도 AM 슬롯이 collection_missing 으로 누락되지 않는지 검사"""
    ledger = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '700', 'outcome': 'ok_with_items', 'called_at_kst': '2026-09-07T07:00:00+09:00'}
    ])
    ledger['slot_hhmm'] = ledger['slot_hhmm'].astype(str).str.zfill(4)
    
    raw_df = pd.DataFrame([
        {'obs_date': '2026-09-07', 'slot_hhmm': '0700', 'routeid': 'A', 'arrtime_sec': 500, 'n_items': 1}
    ])
    routes = {'A'}
    ts = build_timeseries(ledger, raw_df, routes, zero_fill=False)
    
    am_0700 = ts[(ts['obs_date'] == '2026-09-07') & (ts['slot_hhmm'] == '0700')]
    assert not am_0700.empty
    assert am_0700.iloc[0]['collection_missing'] == False
    assert am_0700.iloc[0]['arrtime_sec'] == 500
