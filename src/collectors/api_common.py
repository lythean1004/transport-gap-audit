import os
import json
import time
import hashlib
import logging
from datetime import datetime, timezone
import requests
from pathlib import Path
from src.config import require_secret

logger = logging.getLogger(__name__)

class APIError(Exception):
    pass

def redact_params(params: dict) -> dict:
    """Removes sensitive keys from parameters for logging."""
    redacted = params.copy()
    for key in ['serviceKey', 'consumer_key', 'consumer_secret', 'key']:
        if key in redacted:
            redacted[key] = 'REDACTED'
    return redacted

def _get_result_code(data: dict) -> str:
    """Extracts resultCode from typical public API JSON responses."""
    try:
        return data.get('response', {}).get('header', {}).get('resultCode', 'UNKNOWN')
    except AttributeError:
        return 'UNKNOWN'

def fetch_public_api(source: str, endpoint: str, params: dict, max_retries: int = 3, dry_run: bool = False) -> dict:
    """
    Fetches public API with retries, caching, and raw saving.
    """
    safe_params = redact_params(params)
    
    if dry_run:
        logger.info(f"[DRY-RUN] Request to {endpoint}")
        logger.info(f"[DRY-RUN] Params: {json.dumps(safe_params)}")
        return {}

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw_dir = Path(f"data/raw/{source}/{today_str}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    param_str = json.dumps(safe_params, sort_keys=True)
    cache_hash = hashlib.sha256(f"{endpoint}|{param_str}".encode()).hexdigest()[:12]
    raw_path = raw_dir / f"{cache_hash}.json"
    
    if raw_path.exists():
        logger.info(f"Cache hit for {source}: {raw_path}")
        with open(raw_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    retry_count = 0
    backoff = 2
    
    while retry_count <= max_retries:
        try:
            resp = requests.get(endpoint, params=params, timeout=30)
            status_code = resp.status_code
            
            if status_code == 429:
                logger.warning(f"Rate limited (429). Retrying in {backoff}s...")
                time.sleep(backoff)
                retry_count += 1
                backoff *= 2
                continue
                
            resp.raise_for_status()
            data = resp.json()
            
            result_code = _get_result_code(data)
            
            # Auth errors -> Do not retry
            if result_code in ['20', '30']:
                raise APIError(f"Auth error ({result_code}). Will not retry.")
            
            # Rate limit errors -> retry
            if result_code in ['22', '23']:
                logger.warning(f"API Limit Exceeded ({result_code}). Retrying in {backoff}s...")
                time.sleep(backoff)
                retry_count += 1
                backoff *= 2
                continue
                
            if result_code not in ['00', 'UNKNOWN']:
                raise APIError(f"API Error. resultCode: {result_code}")
                
            meta = {
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint,
                "params": safe_params,
                "http_status": status_code,
                "resultCode": result_code,
                "raw_path": str(raw_path)
            }
            
            saved_data = {"_meta": meta, "data": data}
            
            with open(raw_path, 'w', encoding='utf-8') as f:
                json.dump(saved_data, f, ensure_ascii=False, indent=2)
                
            return saved_data
            
        except requests.RequestException as e:
            logger.error(f"HTTP request failed for {source}. (URL hidden for security)")
            time.sleep(backoff)
            retry_count += 1
            backoff *= 2
            
    raise APIError(f"Max retries ({max_retries}) exceeded for {source}.")
