import os
import re
from typing import Optional
from dotenv import load_dotenv

# Optional .env loading
load_dotenv(override=False)

def require_secret(secret_name: str) -> str:
    """
    Requires a named environment variable.
    Returns the secret value.
    Never prints or exposes the secret in exceptions.
    """
    value = os.getenv(secret_name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {secret_name}")
    return value

def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves an optional environment variable or secret."""
    return os.getenv(secret_name, default)

def redact_sensitive_url(url: str) -> str:
    """Redacts sensitive query parameters (serviceKey, keys, secrets) from URL strings."""
    pattern = re.compile(r'((?:serviceKey|consumer_key|consumer_secret)=)([^&]+)', re.IGNORECASE)
    return pattern.sub(r'\1REDACTED', url)

def sanitize_log(msg: str) -> str:
    """Sanitizes log messages by masking sensitive parameters."""
    pattern = re.compile(r'((?:serviceKey|consumer_key|consumer_secret)=)([^&\s]+)', re.IGNORECASE)
    return pattern.sub(r'\1REDACTED', msg)
