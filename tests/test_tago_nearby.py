import math
import pytest
from src.collectors.geo_const import haversine, LON_M_PER_DEG_AT, LAT_M_PER_DEG
import pandas as pd

def test_haversine_known_values():
    assert haversine(37.5, 127.0, 37.5, 127.0) == 0.0
    dist_lat = haversine(37.0, 127.0, 38.0, 127.0)
    assert 111000 < dist_lat < 111400
    dist_lon = haversine(37.5, 127.0, 37.5, 128.0)
    assert 88000 < dist_lon < 88500

def test_lon_m_per_deg_at():
    assert abs(LON_M_PER_DEG_AT(0) - 111320) < 1
    assert abs(LON_M_PER_DEG_AT(60) - 55660) < 1

def process_mock_items(items, lat_c, lon_c):
    """A helper function mimicking the processing loop in tago_stops_nearby.py 
    to test dedup, empty handling, and bounds rejection."""
    seen_nodes = set()
    cluster_stops = []
    
    for item in items:
        ccode = str(item.get("citycode", "")).strip()
        nodeid = str(item.get("nodeid", "")).strip()
        if not nodeid or not ccode:
            continue
            
        if (ccode, nodeid) in seen_nodes:
            continue
        seen_nodes.add((ccode, nodeid))
        
        item_lat_raw = item.get("gpslati")
        item_lon_raw = item.get("gpslong")
        
        if pd.isna(item_lat_raw) or str(item_lat_raw).strip() == "" or float(item_lat_raw) == 0.0:
            item_lat = None
        else:
            item_lat = float(item_lat_raw)
            
        if pd.isna(item_lon_raw) or str(item_lon_raw).strip() == "" or float(item_lon_raw) == 0.0:
            item_lon = None
        else:
            item_lon = float(item_lon_raw)
            
        if item_lat is None or item_lon is None:
            continue
        if not (33.0 <= item_lat <= 39.0 and 124.0 <= item_lon <= 132.0):
            continue
            
        dist_m = haversine(lat_c, lon_c, item_lat, item_lon)
        cluster_stops.append({
            "citycode": ccode,
            "nodeid": nodeid,
            "gpslati": item_lat,
            "gpslong": item_lon,
            "recomputed_dist_m": dist_m,
        })
    return cluster_stops

def test_dedup_and_empty():
    lat_c, lon_c = 37.5, 127.0
    items = [
        {"citycode": "31020", "nodeid": "NODE1", "gpslati": 37.501, "gpslong": 127.001},
        {"citycode": "31020", "nodeid": "NODE1", "gpslati": 37.501, "gpslong": 127.001}, # duplicate
        {"citycode": "31020", "nodeid": "NODE2", "gpslati": 37.502, "gpslong": 127.002},
        {}, # empty
        {"citycode": "31020", "nodeid": "NODE3"} # missing coordinates
    ]
    stops = process_mock_items(items, lat_c, lon_c)
    assert len(stops) == 2
    assert stops[0]["nodeid"] == "NODE1"
    assert stops[1]["nodeid"] == "NODE2"

def test_korea_bounds_rejection():
    lat_c, lon_c = 37.5, 127.0
    items = [
        {"citycode": "31020", "nodeid": "N_OK", "gpslati": 37.5, "gpslong": 127.0},
        {"citycode": "31020", "nodeid": "N_OUT1", "gpslati": 40.0, "gpslong": 127.0}, # lat out
        {"citycode": "31020", "nodeid": "N_OUT2", "gpslati": 37.5, "gpslong": 133.0}, # lon out
        {"citycode": "31020", "nodeid": "N_NULL", "gpslati": None, "gpslong": None},  # null out
        {"citycode": "31020", "nodeid": "N_ZERO", "gpslati": 0.0, "gpslong": 0.0}     # zero out
    ]
    stops = process_mock_items(items, lat_c, lon_c)
    assert len(stops) == 1
    assert stops[0]["nodeid"] == "N_OK"
