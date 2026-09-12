import os
import polars as pl
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import unquote

from src.collectors.api_common import fetch_public_api
from src.config import require_secret
from src.logging_utils import setup_logger

logger = setup_logger("building_title")

URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"

def get_building_title(sigungu_cd: str, bjdong_cd: str, plat_gb_cd: str, bun: str, ji: str, dry_run: bool = False) -> List[Dict]:
    """
    Fetches building title information with pagination until totalCount is reached.
    """
    raw_key = require_secret("TAGO_SERVICE_KEY")
    # Usually keys in .env are encoded. Requests takes care of encoding if we pass the decoded key.
    # We try to use it as is, or unquote if it's explicitly URL encoded.
    decoded_key = unquote(raw_key) if "%" in raw_key else raw_key
    
    extracted = []
    page_no = 1
    num_of_rows = 100
    total_count = None
    
    while True:
        params = {
            "serviceKey": decoded_key,
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "platGbCd": plat_gb_cd,
            "bun": bun,
            "ji": ji,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "_type": "json",
        }
        
        resp = fetch_public_api(source="building_hub", endpoint=URL, params=params, dry_run=dry_run)
        if dry_run:
            return []
            
        body = resp.get('data', {}).get('response', {}).get('body', {})
        if total_count is None:
            total_count = body.get('totalCount', 0)
            
        items = body.get('items', {})
        if not items:
            break
            
        item = items.get('item')
        if item is None:
            break
            
        # Support items.item as missing, object, or list
        if isinstance(item, dict):
            item_list = [item]
        elif isinstance(item, list):
            item_list = item
        else:
            item_list = []
            
        for i in item_list:
            extracted.append({
                "mgmBldrgstPk": i.get("mgmBldrgstPk"),
                "platPlc": i.get("platPlc"),
                "newPlatPlc": i.get("newPlatPlc"),
                "bldNm": i.get("bldNm"),
                "dongNm": i.get("dongNm"),
                "mainPurpsCdNm": i.get("mainPurpsCdNm"),
                "hhldCnt": i.get("hhldCnt"),
                "useAprDay": i.get("useAprDay"),
            })
            
        if len(extracted) >= total_count:
            break
            
        page_no += 1
        
    return extracted

def export_to_parquet(data: List[Dict], out_name: str = "building_title.parquet"):
    if not data:
        logger.info("No data to export.")
        return
        
    out_dir = Path("data/staged")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name
    
    df = pl.DataFrame(data)
    df.write_parquet(out_path)
    logger.info(f"Saved {len(data)} records to {out_path}")

if __name__ == "__main__":
    # Command line args for dry-run
    import sys
    dry_run = "--dry-run" in sys.argv
    get_building_title("41590", "00000", "0", "0000", "0000", dry_run=dry_run)
