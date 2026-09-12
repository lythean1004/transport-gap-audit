import os
import json
import yaml
import hashlib
import time
import requests
import pandas as pd
import polars as pl
from datetime import datetime
from pathlib import Path
import sys

# Ensure src module is reachable
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import require_secret

class TAGOAuthError(Exception): pass
class TAGOAPIError(Exception): pass

def fetch_tago_citycodes():
    url = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCtyCodeList"
    key = require_secret("TAGO_SERVICE_KEY")
    
    params = {
        "serviceKey": key,
        "pageNo": 1,
        "numOfRows": 1000,
        "_type": "json"
    }
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, params=params, timeout=15)
            
            try:
                data = resp.json()
            except ValueError:
                data = None
                
            if data and 'OpenAPI_ServiceResponse' in data:
                header = data['OpenAPI_ServiceResponse'].get('cmmMsgHeader', {})
                code = str(header.get('returnReasonCode', ''))
                msg = header.get('errMsg', '')
                if code in ('20', '30'):
                    raise TAGOAuthError(f"Auth error (returnReasonCode {code}): 15098534(버스정류소정보) 활용신청 상태를 확인하세요.")
                raise TAGOAPIError(f"API Error {code}: {msg}")
                
            resp.raise_for_status()
            
            if not data:
                data = resp.json()
                
            header = data.get('response', {}).get('header', {})
            resultCode = str(header.get('resultCode', ''))
            resultMsg = header.get('resultMsg', '')
            
            if resultCode in ('20', '30'):
                raise TAGOAuthError(f"Auth error (resultCode {resultCode}): 15098534(버스정류소정보) 활용신청 상태를 확인하세요.")
                
            if resultCode != '00':
                raise TAGOAPIError(f"API Error {resultCode}: {resultMsg}")
                
            # Save raw response
            today = datetime.now().strftime('%Y-%m-%d')
            raw_dir = Path(f"data/raw/tago_citycode/{today}")
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            # Use deterministic hash of params excluding key
            safe_params = params.copy()
            del safe_params['serviceKey']
            fingerprint = hashlib.sha256(json.dumps(safe_params, sort_keys=True).encode()).hexdigest()
            raw_file = raw_dir / f"{fingerprint}.json"
            
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict):
                items = [items]
                
            return items
            
        except requests.HTTPError as e:
            if attempt == max_attempts - 1:
                raise TAGOAPIError(f"HTTP Error {e.response.status_code}")
            time.sleep(2 ** attempt)
        except TAGOAPIError:
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)

def run():
    print("[1/3] 도시코드(TAGO) 목록을 조회합니다...")
    try:
        items = fetch_tago_citycodes()
    except TAGOAuthError as e:
        print(f"\n[오류] {e}")
        print("Tip: 건축HUB(15134735) 키가 있더라도 TAGO 버스정류소정보(15098534) 활용신청을 별도로 해야 합니다.")
        sys.exit(1)
        
    print(f"총 {len(items)}개의 도시코드를 수집했습니다.")
    
    # Write tago_citycodes.parquet
    df_cities = pl.DataFrame(items)
    # Ensure correct types
    df_cities = df_cities.with_columns([
        pl.col('citycode').cast(pl.Utf8),
        pl.col('cityname').cast(pl.Utf8)
    ])
    
    out_dir = Path("data/staged")
    out_dir.mkdir(parents=True, exist_ok=True)
    df_cities.write_parquet(out_dir / "tago_citycodes.parquet")
    
    # Load pilots to map sigungu
    with open('config/pilots.yaml', 'r', encoding='utf-8') as f:
        pilots_config = yaml.safe_load(f)
        
    records = []
    matched_pilots = set()
    unmatched_pilots = set()
    
    cities_list = df_cities.to_dicts()
    
    print("[2/3] 파일럿 단지와 도시코드를 매핑합니다...")
    for p in pilots_config.get('pilots', []):
        dev_id = p['development_id']
        sigungu_list = p.get('match_hints', {}).get('sigungu', [])
        
        pilot_matched = False
        for s in sigungu_list:
            # We want to match `s` with `cityname`.
            # For example "성남시 수정구" vs "성남시" -> partial match?
            # Or exact match? Let's check if `s` starts with `cityname` or vice versa.
            # Usually cityname in TAGO is "서울특별시", "수원시", "창원시".
            # If `s` is "성남시 수정구", cityname is likely "성남시"
            # If `s` is "송파구", cityname is likely "서울특별시" (or TAGO might not have Seoul).
            
            candidates = []
            for c in cities_list:
                cname = c['cityname']
                # Substring match either way
                # However, to be safe, "하남시" in "하남시", "성남시" in "성남시 수정구"
                if cname in s or s in cname:
                    # Filter out False Positives (e.g. "남원시" matching "남원")
                    # Let's just do a simple inclusion
                    candidates.append(c)
                    
            if len(candidates) == 1:
                records.append({
                    "development_id": dev_id,
                    "sigungu": s,
                    "candidate_cityname": candidates[0]['cityname'],
                    "candidate_citycode": candidates[0]['citycode'],
                    "match_flag": "OK",
                    "citycode_confirmed_by": ""
                })
                pilot_matched = True
            elif len(candidates) > 1:
                c_names = [c['cityname'] for c in candidates]
                records.append({
                    "development_id": dev_id,
                    "sigungu": s,
                    "candidate_cityname": f"MULTIPLE: {', '.join(c_names)}",
                    "candidate_citycode": "",
                    "match_flag": "MULTIPLE_MATCH",
                    "citycode_confirmed_by": ""
                })
                # Not counting as strictly matched if multiple, human needs to resolve
            else:
                records.append({
                    "development_id": dev_id,
                    "sigungu": s,
                    "candidate_cityname": "",
                    "candidate_citycode": "",
                    "match_flag": "NO_MATCH",
                    "citycode_confirmed_by": ""
                })
                
        if pilot_matched:
            matched_pilots.add(dev_id)
        else:
            unmatched_pilots.add(dev_id)
            
    df_map = pd.DataFrame(records)
    exports_dir = Path("exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    df_map.to_csv(exports_dir / "pilot_citycode_map.csv", index=False, encoding='utf-8-sig')
    
    print("[3/3] 매핑 결과 요약:")
    print(f" - 전체 조회된 TAGO 도시 개수: {len(items)}")
    print(f" - 최소 1개 이상 매칭 성공한 파일럿 수: {len(matched_pilots)}")
    print(f" - 매칭 실패(미연계 또는 다중매칭) 파일럿 수: {len(unmatched_pilots)}")
    
    if unmatched_pilots:
        print(f"\n[주의] 매칭 실패 파일럿 목록 (exports/pilot_citycode_map.csv에서 수기 확인 필요):")
        for p in unmatched_pilots:
            print(f"   - {p}")
            
    print("\n[완료] TAGO 6A 도시코드 수집 완료.")

if __name__ == "__main__":
    run()
