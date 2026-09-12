import pytest
import pandas as pd
import numpy as np

from calc_headway_v2 import detect_events_v2

def test_jump_up():
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

def test_collection_missing_and_right_censored():
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'arrtime_sec': 1000, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'arrtime_sec': pd.NA, 'collection_missing': True, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'arrtime_sec': 1500, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0715', 'arrtime_sec': 1200, 'collection_missing': False, 'route_absent': False},
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events_v2(df)
    # 0700 is cut off by missing at 0705 -> no event.
    # 0715 is right censored -> no event.
    assert len(ev) == 0

def test_gap_adjacent():
    ts_data = [
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0700', 'arrtime_sec': 1000, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0705', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True}, # event at 0700
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0710', 'arrtime_sec': pd.NA, 'collection_missing': True, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0715', 'arrtime_sec': 500, 'collection_missing': False, 'route_absent': False},
        {'routeid': 'A', 'obs_date': '2026-09-07', 'window': 'AM', 'slot_hhmm': '0720', 'arrtime_sec': pd.NA, 'collection_missing': False, 'route_absent': True}, # event at 0715
    ]
    df = pd.DataFrame(ts_data)
    ev, _ = detect_events_v2(df)
    assert len(ev) == 2
    assert ev.iloc[0]['event_slot'] == '0700'
    assert ev.iloc[1]['event_slot'] == '0715'
    assert ev.iloc[1]['gap_adjacent'] == True
