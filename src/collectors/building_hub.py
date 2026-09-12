import os
import sys
import json
import argparse
import hashlib
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
import requests
import polars as pl

from src.config import require_secret
from src.logging_utils import setup_logger

logger = setup_logger("building_hub")

class BuildingHubAuthError(Exception):
    """Raised for auth errors (20, 30). Should fail fast."""
    pass

class BuildingHubAPIError(Exception):
    """Raised for API errors (22, 23, or non-00). Should retry."""
    pass

def build_fingerprint(params):
    p = {k: v for k, v in params.items() if k != 'serviceKey'}
    return hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()

def fetch_page(url, params):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, params=params, timeout=15)
            
            # Check for API Gateway errors wrapped in JSON (like 403 with returnReasonCode 30)
            try:
                data = resp.json()
            except ValueError:
                data = None
                
            if isinstance(data, dict) and 'OpenAPI_ServiceResponse' in data:
                header = data['OpenAPI_ServiceResponse'].get('cmmMsgHeader', {})
                code = str(header.get('returnReasonCode', ''))
                msg = header.get('errMsg', '')
                if code in ('20', '30'):
                    raise BuildingHubAuthError(f"Auth error (returnReasonCode {code}): Check TAGO_SERVICE_KEY")
                raise BuildingHubAPIError(f"API Error {code}: {msg}")
                
            resp.raise_for_status()
            
            # Normal response structure
            if not data:
                data = resp.json()
                
            header = data.get('response', {}).get('header', {})
            resultCode = str(header.get('resultCode', ''))
            resultMsg = header.get('resultMsg', '')
            
            if resultCode in ('20', '30'):
                raise BuildingHubAuthError(f"Auth error (resultCode {resultCode}): Check TAGO_SERVICE_KEY")
                
            if resultCode != '00':
                raise BuildingHubAPIError(f"API Error {resultCode}: {resultMsg}")
                
            return data
            
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (429, 500, 502, 503, 504):
                if attempt == max_attempts - 1:
                    raise BuildingHubAPIError(f"HTTP Error {e.response.status_code}") from e
                time.sleep(2 ** attempt)
            else:
                raise
        except BuildingHubAPIError as e:
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)
        except requests.RequestException as e:
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)

def extract_items(data):
    body = data.get('response', {}).get('body', {})
    items_block = body.get('items', {})
    if not items_block:
        return []
    
    # Could be missing, dict, or list
    item = items_block.get('item')
    if item is None:
        return []
    if isinstance(item, dict):
        return [item]
    if isinstance(item, list):
        return item
    return []

def parse_useAprDay(val):
    if not val:
        return None
    val = str(val).strip()
    if len(val) == 8 and val.isdigit():
        return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    return None

def collect_bldg_title(sigunguCd, bjdongCd, platGbCd, bun, ji, dry_run=False):
    service_key = require_secret("TAGO_SERVICE_KEY")
    url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
    
    base_params = {
        'sigunguCd': sigunguCd,
        'bjdongCd': bjdongCd,
        'platGbCd': platGbCd,
        'bun': bun,
        'ji': ji,
        '_type': 'json',
        'numOfRows': 100
    }
    
    today = datetime.now().strftime("%Y-%m-%d")
    cache_dir = Path(f"data/raw/building_hub/{today}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    all_items = []
    pageNo = 1
    totalCount = None
    
    while True:
        params = {**base_params, 'pageNo': pageNo, 'serviceKey': service_key}
        
        if dry_run:
            safe_params = {**params, 'serviceKey': 'REDACTED'}
            qs = urlencode(safe_params)
            logger.info(f"DRY RUN: GET {url}?{qs}")
            return []
            
        fingerprint = build_fingerprint(params)
        cache_file = cache_dir / f"{fingerprint}.json"
        
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = fetch_page(url, params)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
                
        items = extract_items(data)
        all_items.extend(items)
        
        body = data.get('response', {}).get('body', {})
        if totalCount is None:
            totalCount = int(body.get('totalCount', 0))
            
        if len(all_items) >= totalCount or not items:
            break
            
        pageNo += 1
        
    return all_items

def save_to_parquet(items, out_path="data/staged/bldg_title.parquet"):
    fields = [
        "mgmBldrgstPk", "mgmUpBldrgstPk", "sigunguCd", "bjdongCd", "platGbCd", "bun", "ji",
        "platPlc", "newPlatPlc", "bldNm", "dongNm", "mainPurpsCdNm", "regstrKindCd",
        "hhldCnt", "fmlyCnt", "pmsDay", "stcnsDay", "useAprDay", "crtnDay"
    ]
    
    rows = []
    for it in items:
        row = {f: it.get(f) for f in fields}
        row["useAprDay_raw"] = row["useAprDay"]
        row["useAprDay"] = parse_useAprDay(row["useAprDay"])
        
        # Cast specific types
        for count_f in ["hhldCnt", "fmlyCnt"]:
            if row[count_f] is not None:
                try:
                    row[count_f] = int(row[count_f])
                except ValueError:
                    row[count_f] = None
        rows.append(row)
        
    if not rows:
        return
        
    df = pl.DataFrame(rows)
    schema = {
        "mgmBldrgstPk": pl.Utf8,
        "mgmUpBldrgstPk": pl.Utf8,
        "sigunguCd": pl.Utf8,
        "bjdongCd": pl.Utf8,
        "platGbCd": pl.Utf8,
        "bun": pl.Utf8,
        "ji": pl.Utf8,
        "platPlc": pl.Utf8,
        "newPlatPlc": pl.Utf8,
        "bldNm": pl.Utf8,
        "dongNm": pl.Utf8,
        "mainPurpsCdNm": pl.Utf8,
        "regstrKindCd": pl.Utf8,
        "hhldCnt": pl.Int64,
        "fmlyCnt": pl.Int64,
        "pmsDay": pl.Utf8,
        "stcnsDay": pl.Utf8,
        "useAprDay_raw": pl.Utf8,
        "useAprDay": pl.Utf8,
        "crtnDay": pl.Utf8
    }
    
    # Cast to ensure schema matches, especially for empty dfs or nulls
    df = df.with_columns([pl.col(c).cast(t) for c, t in schema.items() if c in df.columns])
    
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    if out_file.exists():
        existing = pl.read_parquet(out_file)
        df = pl.concat([existing, df], how="diagonal")
        
    df.write_parquet(out_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sigunguCd", required=True)
    parser.add_argument("--bjdongCd", required=True)
    parser.add_argument("--platGbCd", required=True)
    parser.add_argument("--bun", required=True)
    parser.add_argument("--ji", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    
    args = parser.parse_args()
    
    if args.live:
        if os.environ.get("ALLOW_LIVE_CALL") != "1":
            logger.error("Refusing to run live call without ALLOW_LIVE_CALL=1 environment variable.")
            sys.exit(1)
            
    if not args.live and not args.dry_run:
        logger.info("Neither --live nor --dry-run specified. Defaulting to dry-run behavior for safety.")
        args.dry_run = True
        
    items = collect_bldg_title(
        args.sigunguCd, args.bjdongCd, args.platGbCd, args.bun, args.ji,
        dry_run=args.dry_run
    )
    
    if not args.dry_run and items:
        save_to_parquet(items)
        logger.info(f"Saved {len(items)} items to parquet.")
