import os
import json
import time
import requests
import hashlib
import pandas as pd
import polars as pl
import yaml
from pathlib import Path
import sys

# Ensure src module is reachable
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import require_secret
from src.collectors.geo_const import LAT_M_PER_DEG, LON_M_PER_DEG_AT, GRID_STEP_M, haversine

TAGO_BASE = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService"
OP_NEARBY = "getCrdntPrxmtSttnList"

class TAGOAPIError(Exception): pass

def fetch_nearby(lat: float, lon: float, service_key: str, raw_dir: Path):
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 1000,
        "_type": "json",
        "gpsLati": round(lat, 6),
        "gpsLong": round(lon, 6)
    }
    
    # check raw cache first
    safe_params = params.copy()
    del safe_params['serviceKey']
    fingerprint = hashlib.sha256(json.dumps(safe_params, sort_keys=True).encode()).hexdigest()
    raw_file = raw_dir / f"grid_{fingerprint}.json"
    
    if raw_file.exists():
        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            body = data.get("response", {}).get("body", {})
            total_count = body.get("totalCount", 0)
            if total_count == 0:
                return []
            items = body.get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            return items
        except Exception:
            pass

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            r = requests.get(f"{TAGO_BASE}/{OP_NEARBY}", params=params, timeout=20)
            r.raise_for_status()
            
            try:
                data = r.json()
            except ValueError:
                data = None
                
            if not data:
                raise TAGOAPIError("Empty JSON")
                
            head = data.get("response", {}).get("header", {})
            if head.get("resultCode") != "00":
                if attempt == max_attempts - 1:
                    raise TAGOAPIError(f"API Error {head.get('resultCode')}: {head.get('resultMsg')}")
                time.sleep(2 ** attempt)
                continue
                
            # save raw
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            body = data.get("response", {}).get("body", {})
            total_count = body.get("totalCount", 0)
            if total_count == 0:
                # 빈 결과는 정상이므로 바로 빈 리스트 반환
                return []
                
            items = body.get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            return items
            
        except requests.RequestException as e:
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)
            
    return []

def main():
    service_key = require_secret("TAGO_SERVICE_KEY")
    
    today = datetime.now().strftime('%Y-%m-%d')
    raw_dir = Path(f"data/raw/tago_stops_nearby/{today}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Load complexes from complex_geocode.csv
    complex_path = Path("exports/complex_geocode.csv")
    if not complex_path.exists():
        print("[오류] exports/complex_geocode.csv 가 존재하지 않습니다. (지오코딩 선행 필요)")
        sys.exit(1)
        
    df_complex = pd.read_csv(complex_path)
    # We also need the pilot_id for each cluster, which is in bldg_query_plan.csv
    plan_path = Path("bldg_query_plan.csv")
    df_plan = pd.read_csv(plan_path)[['cluster_id', 'pilot_id']].drop_duplicates()
    df_complex = df_complex.merge(df_plan, on='cluster_id', how='left')
    
    # Load full stops to join against
    full_stops_path = Path("data/staged/tago_stops_full.parquet")
    if full_stops_path.exists():
        df_full = pl.read_parquet(full_stops_path)
    else:
        print("[오류] 6B tago_stops_full.parquet 파일이 존재하지 않습니다.")
        sys.exit(1)
        
    full_dict = {}
    for row in df_full.to_dicts():
        key = (str(row['citycode']).strip(), str(row['nodeid']).strip())
        full_dict[key] = {
            "gpslati": row["gpslati"],
            "gpslong": row["gpslong"]
        }
        
    all_results = []
    
    for _, row in df_complex.iterrows():
        dev_id = row['pilot_id']
        cluster_id = row['cluster_id']
        lat_c = float(row['lat'])
        lon_c = float(row['lon'])
        
        # x/y swap check
        if not (33.0 <= lat_c <= 39.0 and 124.0 <= lon_c <= 132.0):
            print(f"[오류] {cluster_id} 좌표가 범위를 벗어남(x/y 반전 의심). lat={lat_c}, lon={lon_c}")
            continue
            
        # Derive grid steps
        grid_step_lat = GRID_STEP_M / LAT_M_PER_DEG
        grid_step_lon = GRID_STEP_M / LON_M_PER_DEG_AT(lat_c)
        
        seen_nodes = set()
        cluster_stops = []
        calls_made = 0
        
        print(f"[{cluster_id}] 3x3 격자 조회 시작... (중심: {lat_c}, {lon_c})")
        
        for i in [-1, 0, 1]:
            for j in [-1, 0, 1]:
                grid_lat = lat_c + (i * grid_step_lat)
                grid_lon = lon_c + (j * grid_step_lon)
                
                items = fetch_nearby(grid_lat, grid_lon, service_key, raw_dir)
                calls_made += 1
                
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
                        
                    # Korea bounds rejection
                    if item_lat is None or item_lon is None:
                        continue
                    if not (33.0 <= item_lat <= 39.0 and 124.0 <= item_lon <= 132.0):
                        continue
                        
                    dist_m = haversine(lat_c, lon_c, item_lat, item_lon)
                    
                    coord_delta_m = None
                    key = (ccode, nodeid)
                    if key in full_dict:
                        full_lat = full_dict[key]['gpslati']
                        full_lon = full_dict[key]['gpslong']
                        if full_lat is not None and full_lon is not None:
                            coord_delta_m = haversine(item_lat, item_lon, full_lat, full_lon)
                            
                    cluster_stops.append({
                        "development_id": dev_id,
                        "cluster_id": cluster_id,
                        "citycode": ccode,
                        "nodeid": nodeid,
                        "nodenm": item.get("nodenm", ""),
                        "gpslati": item_lat,
                        "gpslong": item_lon,
                        "api_radius_claim_m": 500,
                        "recomputed_dist_m": dist_m,
                        "coord_delta_m": coord_delta_m
                    })
        
        # Report per cluster
        # Unique stops, stops within 500/800/1000m, max coord_delta_m
        all_results.extend(cluster_stops)
        
        within_500 = sum(1 for s in cluster_stops if s["recomputed_dist_m"] <= 500)
        within_800 = sum(1 for s in cluster_stops if s["recomputed_dist_m"] <= 800)
        within_1000 = sum(1 for s in cluster_stops if s["recomputed_dist_m"] <= 1000)
        deltas = [s["coord_delta_m"] for s in cluster_stops if s["coord_delta_m"] is not None]
        max_delta = max(deltas) if deltas else 0.0
        
        print(f"  - calls made: {calls_made}")
        print(f"  - unique stops: {len(cluster_stops)}")
        print(f"  - within 500m (직선거리): {within_500}")
        print(f"  - within 800m (직선거리): {within_800}")
        print(f"  - within 1000m (직선거리): {within_1000}")
        print(f"  - max coord_delta_m: {max_delta:.1f}")
        
    if all_results:
        df_out = pl.DataFrame(all_results)
        out_dir = Path("data/staged")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "tago_stops_nearby.parquet"
        df_out.write_parquet(out_path)
        print(f"\n[완료] 총 {len(all_results)}개의 매핑 레코드가 {out_path} 에 저장되었습니다.")
    else:
        print("\n[완료] 클러스터 좌표가 입력되지 않아 조회된 정류소가 없습니다.")

if __name__ == "__main__":
    from datetime import datetime
    main()
