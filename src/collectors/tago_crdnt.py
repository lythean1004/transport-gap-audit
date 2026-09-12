import os
import json
import time
import requests
import hashlib
import argparse
import pandas as pd
import polars as pl
import yaml
from pathlib import Path
import sys

# Ensure src module is reachable
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import require_secret

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
            safe_params = params.copy()
            del safe_params['serviceKey']
            fingerprint = hashlib.sha256(json.dumps(safe_params, sort_keys=True).encode()).hexdigest()
            raw_file = raw_dir / f"grid_{fingerprint}.json"
            
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            body = data.get("response", {}).get("body", {})
            total_count = body.get("totalCount", 0)
            if total_count == 0:
                # 0건 반환은 coverage_status로 기록해야 함
                return {"status": "zero_stops", "items": []}
                
            items = body.get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            return {"status": "ok", "items": items}
            
        except requests.RequestException as e:
            if attempt == max_attempts - 1:
                return {"status": "api_error", "items": []}
            time.sleep(2 ** attempt)
            
    return {"status": "api_error", "items": []}

def run_anchor_mode(service_key):
    today = datetime.now().strftime('%Y-%m-%d')
    raw_dir = Path(f"data/raw/tago_anchor/{today}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    with open('config/pilots.yaml', 'r', encoding='utf-8') as f:
        pilots_config = yaml.safe_load(f)
        
    results = []
    
    for p in pilots_config.get('pilots', []):
        dev_id = p['development_id']
        lat = p.get('anchor_lat')
        lon = p.get('anchor_lon')
        
        if not lat or not lon:
            print(f"[경고] {dev_id} 앵커 좌표 없음. 건너뜁니다.")
            continue
            
        print(f"[{dev_id}] 앵커 조회 중... (lat={lat}, lon={lon})")
        res = fetch_nearby(float(lat), float(lon), service_key, raw_dir)
        status = res["status"]
        items = res["items"]
        
        expected_citycode = p.get('citycode', '')
        
        if status == "ok" and items:
            # Check citycode from the first item
            actual_citycode = str(items[0].get('citycode', '')).strip()
            
            # If pilot uses multi-citycode (like WIRYE), we check if it matches any
            citycode_multi = p.get('citycode_multi')
            is_match = False
            
            if citycode_multi:
                for c in citycode_multi:
                    if str(c.get('citycode')) == actual_citycode:
                        is_match = True
                        break
            else:
                is_match = (actual_citycode == str(expected_citycode))
                
            citycode_confirmed_by = 'live_ok' if is_match else 'live_mismatch'
            
            results.append({
                "development_id": dev_id,
                "anchor_lat": lat,
                "anchor_lon": lon,
                "coverage_status": status,
                "stop_count": len(items),
                "expected_citycode": expected_citycode,
                "actual_citycode": actual_citycode,
                "citycode_confirmed_by": citycode_confirmed_by
            })
            if not is_match:
                print(f"  [불일치] 예상: {expected_citycode}, 실제: {actual_citycode}")
        else:
            results.append({
                "development_id": dev_id,
                "anchor_lat": lat,
                "anchor_lon": lon,
                "coverage_status": status,
                "stop_count": 0,
                "expected_citycode": expected_citycode,
                "actual_citycode": "",
                "citycode_confirmed_by": "failed"
            })
            
    qa_dir = Path("qa")
    qa_dir.mkdir(parents=True, exist_ok=True)
    df_out = pd.DataFrame(results)
    df_out.to_csv(qa_dir / "6A_anchor_smoke.csv", index=False, encoding='utf-8-sig')
    print(f"\n[완료] 앵커 모드 결과가 qa/6A_anchor_smoke.csv 에 저장되었습니다.")

def run_complex_mode(service_key):
    # bldg_query_plan.csv 에 단지 좌표가 있어야 함 (아직 지오코딩 전일 수 있음)
    plan_path = Path("exports/bldg_query_plan.csv")
    if not plan_path.exists():
        print("[오류] exports/bldg_query_plan.csv 가 존재하지 않습니다.")
        sys.exit(1)
        
    df_plan = pd.read_csv(plan_path)
    
    if 'lat' not in df_plan.columns or 'lon' not in df_plan.columns:
        print("[중단] 지오코딩 미완료 (lat, lon 컬럼 없음). 지표가 비는 것을 방지하기 위해 중단합니다.")
        sys.exit(1)
        
    missing_coords = df_plan['lat'].isna().sum()
    if missing_coords > 0:
        print(f"[중단] 지오코딩 미완료 {missing_coords}건. 단지 좌표를 모두 채운 뒤 실행하세요.")
        sys.exit(1)
        
    # TODO: Implement complex-level metric calculation once geocoding is complete.
    print("[진행 중] 단지 좌표가 모두 존재합니다. 단지별 접근성 지표 산출 시작...")
    # ... (Actual metric logic will be added here later) ...

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["anchor", "complex"], required=True)
    args = parser.parse_args()
    
    # "serviceKey 는 Decoding 키를 params= 로 전달."
    # require_secret retrieves TAGO_SERVICE_KEY from .env which is the decoded key.
    service_key = require_secret("TAGO_SERVICE_KEY")
    
    if args.mode == "anchor":
        run_anchor_mode(service_key)
    elif args.mode == "complex":
        run_complex_mode(service_key)

if __name__ == "__main__":
    from datetime import datetime
    main()
