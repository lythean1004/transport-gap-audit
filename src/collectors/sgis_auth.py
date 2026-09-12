import requests
from datetime import datetime, timezone
from src.config import require_secret

# Simple in-memory cache for token (since this runs per script execution, 
# for a long running daemon, this would need to cache to disk or keep state).
_TOKEN_CACHE = {
    "token": None,
    "expires_at": 0 # Unix timestamp
}

AUTH_URL = "https://sgisapi.mods.go.kr/OpenAPI3/auth/authentication.json"

def get_sgis_token(force_refresh=False) -> str:
    """
    Fetches and caches SGIS access token.
    Refresh token 5 mins before expiry.
    """
    now = datetime.now(timezone.utc).timestamp()
    
    if not force_refresh and _TOKEN_CACHE["token"] and _TOKEN_CACHE["expires_at"] > (now + 300):
        return _TOKEN_CACHE["token"]
        
    consumer_key = require_secret("SGIS_CONSUMER_KEY")
    consumer_secret = require_secret("SGIS_CONSUMER_SECRET")
    
    payload = requests.get(AUTH_URL, params={
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
    }, timeout=30).json()
    
    if payload.get("errCd") != 0:
        raise RuntimeError(f"SGIS Auth Failed: {payload.get('errMsg')}")
        
    result = payload.get("result", {})
    token = result.get("accessToken")
    timeout_str = result.get("accessTimeout") # format e.g. "1710000000000" (milliseconds)
    
    if not token or not timeout_str:
        raise RuntimeError("Invalid SGIS Auth response format")
        
    expires_at = int(timeout_str) / 1000.0
    
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = expires_at
    
    return token
