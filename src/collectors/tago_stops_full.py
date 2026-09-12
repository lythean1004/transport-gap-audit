import os
import json
import time
import requests
import hashlib
import pandas as pd
import polars as pl
from datetime import datetime, timezone
from pathlib import Path
import sys

# Ensure src module is reachable
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import require_secret

TAGO_BASE = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService"
OP_STOPS = "getSttnNoList"

class TAGOAPIError(Exception): pass

def get_total_count(city_code, service_key):
    params = {
        "serviceKey": service_key,
        "cityCode": city_code,
        "numOfRows": 1,
        "pageNo": 1,
        "_type": "json"
    }
    r = requests.get(f"{TAGO_BASE}/{OP_STOPS}", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    head = data.get("response", {}).get("header", {})
    if head.get("resultCode") != "00":
        raise TAGOAPIError(f"API Error {head.get('resultCode')}: {head.get('resultMsg')}")
    body = data.get("response", {}).get("body", {})
    return body.get("totalCount", 0)

def fetch_page(city_code, service_key, page_no, num_of_rows, raw_dir):
    params = {
        "serviceKey": service_key,
        "cityCode": city_code,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
        "_type": "json"
    }
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            r = requests.get(f"{TAGO_BASE}/{OP_STOPS}", params=params, timeout=20)
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
            safe_params = params.copy()
            del safe_params['serviceKey']
            fingerprint = hashlib.sha256(json.dumps(safe_params, sort_keys=True).encode()).hexdigest()
            raw_file = raw_dir / f"{city_code}_{page_no}_{fingerprint}.json"
            
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
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
    
    # Read confirmed city codes
    df_map = pd.read_csv('exports/pilot_citycode_map.csv', dtype={'candidate_citycode': str})
    valid = df_map[df_map['citycode_confirmed_by'].str.startswith('getCtyCodeList', na=False)]
    citycodes = valid['candidate_citycode'].dropna().unique().tolist()
    # Remove decimal .0 if any
    citycodes = [c.replace('.0', '') for c in citycodes]
    
    today = datetime.now().strftime('%Y-%m-%d')
    raw_dir = Path(f"data/raw/tago_stops_full/{today}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    all_stops = []
    
    for ccode in citycodes:
        print(f"\n[{ccode}] 정류소 총계 확인 중...")
        try:
            total = get_total_count(ccode, service_key)
        except Exception as e:
            print(f"오류: {e}")
            sys.exit(1)
            
        print(f"[{ccode}] 총 {total}개의 정류소가 확인되었습니다.")
        if total == 0:
            continue
            
        retrieved_items = []
        if total > 3000:
            print(f"[{ccode}] 3000개가 넘어 1000개씩 나누어 페이지네이션 조회합니다...")
            page = 1
            chunk_size = 1000
            while True:
                items = fetch_page(ccode, service_key, page, chunk_size, raw_dir)
                retrieved_items.extend(items)
                if len(items) < chunk_size:
                    break
                page += 1
        else:
            print(f"[{ccode}] 1회 호출로 모두 조회합니다.")
            retrieved_items = fetch_page(ccode, service_key, 1, total, raw_dir)
            
        # check diff
        actual_retrieved = len(retrieved_items)
        if actual_retrieved != total:
            # 1~2개 차이는 간혹 API 싱크 문제로 생길 수 있지만 Fail 요구사항임.
            print(f"[오류] {ccode}에서 totalCount({total})와 수신건수({actual_retrieved}) 불일치!")
            sys.exit(1)
            
        # Process items
        # required columns: citycode, nodeid, nodenm, nodeno, gpslati, gpslong, retrieved_at
        retrieved_at = datetime.now(timezone.utc).isoformat()
        
        valid_items_for_city = []
        null_coord_count = 0
        out_of_bounds_count = 0
        duplicates = 0
        seen = set()
        
        for item in retrieved_items:
            nodeid = str(item.get("nodeid", "")).strip()
            if not nodeid:
                continue
                
            if nodeid in seen:
                duplicates += 1
                continue
            seen.add(nodeid)
            
            nodenm = item.get("nodenm", "")
            nodeno = item.get("nodeno", "")
            lat_raw = item.get("gpslati")
            lon_raw = item.get("gpslong")
            
            # Treat missing as NULL, never 0
            if pd.isna(lat_raw) or str(lat_raw).strip() == "" or float(lat_raw) == 0.0:
                lat = None
            else:
                lat = float(lat_raw)
                
            if pd.isna(lon_raw) or str(lon_raw).strip() == "" or float(lon_raw) == 0.0:
                lon = None
            else:
                lon = float(lon_raw)
                
            if lat is None or lon is None:
                null_coord_count += 1
            else:
                # Korea bounds check: Lat 33~39, Lon 124~132
                if not (33.0 <= lat <= 39.0 and 124.0 <= lon <= 132.0):
                    print(f"[{ccode}] 경고: 범위를 벗어난 좌표 발생. 정류소: {nodenm}({nodeid}), {lat}, {lon}")
                    out_of_bounds_count += 1
                    continue
                    
            valid_items_for_city.append({
                "citycode": ccode,
                "nodeid": nodeid,
                "nodenm": nodenm,
                "nodeno": nodeno,
                "gpslati": lat,
                "gpslong": lon,
                "retrieved_at": retrieved_at
            })
            
        all_stops.extend(valid_items_for_city)
        print(f"[{ccode}] Report:")
        print(f"  - totalCount      : {total}")
        print(f"  - rows retrieved  : {actual_retrieved}")
        print(f"  - rows stored     : {len(valid_items_for_city)}")
        print(f"  - duplicates      : {duplicates}")
        print(f"  - null coordinates: {null_coord_count}")
        print(f"  - out of bounds   : {out_of_bounds_count}")
        
    if all_stops:
        df = pl.DataFrame(all_stops)
        out_dir = Path("data/staged")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "tago_stops_full.parquet"
        df.write_parquet(out_path)
        print(f"\n[완료] 총 {len(all_stops)}개의 정류소 데이터가 {out_path} 에 저장되었습니다.")
    else:
        print("\n[완료] 수집된 정류소가 없습니다.")

if __name__ == "__main__":
    main()
