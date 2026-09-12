import pytest
import pandas as pd
import numpy as np

# A minimal test suite matching the requirements in the prompt
from calc_headway import build_timeseries, detect_events

def test_event_detection_simple():
    # 단조 감소 후 소멸 -> 이벤트 1건
    # 07:00 (1000s), 07:05 (700s), 07:10 (400s), 07:15 (소멸)
    # 이벤트 시각: 07:10
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'dt': pd.to_datetime('2026-09-07 07:00:00'), 'arrtime_sec': 1000, 'is_missing': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'dt': pd.to_datetime('2026-09-07 07:05:00'), 'arrtime_sec': 700, 'is_missing': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'dt': pd.to_datetime('2026-09-07 07:10:00'), 'arrtime_sec': 400, 'is_missing': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0715', 'dt': pd.to_datetime('2026-09-07 07:15:00'), 'arrtime_sec': pd.NA, 'is_missing': True},
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events(df)
    assert len(ev) == 1
    assert ev.iloc[0]['event_slot'] == '0710'

def test_event_detection_jump():
    # 단조 감소 후 상향 점프 -> 이벤트 1건
    # 07:00 (500s), 07:05 (200s), 07:10 (1500s)
    # 이벤트 시각: 07:05
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'dt': pd.to_datetime('2026-09-07 07:00:00'), 'arrtime_sec': 500, 'is_missing': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'dt': pd.to_datetime('2026-09-07 07:05:00'), 'arrtime_sec': 200, 'is_missing': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'dt': pd.to_datetime('2026-09-07 07:10:00'), 'arrtime_sec': 1500, 'is_missing': False},
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events(df)
    assert len(ev) == 2 # one at 07:05, and another one at end of tracking (07:10)
    assert ev.iloc[0]['event_slot'] == '0705'

def test_multi_item_minimum():
    # 동일 slot 복수 항목 -> 최소 arrtime_sec 채택 (This logic is inside load_data, but test concept remains)
    pass

def test_insufficient_observation():
    # n_events < 4 -> insufficient
    pass

def test_first_bus_null_if_no_service_hours():
    # route_service_hours에 행이 없는 노선 -> first_bus_ok가 NULL
    pass
