"""Tests for configuration and secret handling."""

import pytest
from src.config import require_secret, redact_sensitive_url, sanitize_log, get_secret


def test_require_secret(monkeypatch):
    # 로컬 비밀정보 없이도 같은 동작을 검증한다.
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "synthetic-test-value")
    val = require_secret("DATA_GO_KR_SERVICE_KEY")
    assert val is not None and len(val) > 0

    # Test missing key
    with pytest.raises(RuntimeError) as exc_info:
        require_secret("NON_EXISTENT_SECRET_VARIABLE_FOR_TEST")
    assert "Missing required environment variable" in str(exc_info.value)


def test_redact_sensitive_url():
    url = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getSttnNoSearch?serviceKey=mySecretKey123&cityCode=22"
    redacted = redact_sensitive_url(url)
    assert "serviceKey=REDACTED" in redacted
    assert "mySecretKey123" not in redacted
    assert "cityCode=22" in redacted


def test_sanitize_log():
    log_msg = "Request failed for url https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json?consumer_key=abc&consumer_secret=xyz123"
    sanitized = sanitize_log(log_msg)
    assert "consumer_secret=REDACTED" in sanitized
    assert "consumer_key=REDACTED" in sanitized
    assert "xyz123" not in sanitized


def test_redact_sensitive_url_equivalence_with_logging_formatter():
    import logging
    from src.logging_utils import RedactingFormatter
    
    url = "https://apis.data.go.kr/1613000/BusRouteInfoInqireService?serviceKey=SECRET_KEY_123&routeId=GGB222000009"
    direct_redacted = redact_sensitive_url(url)
    
    formatter = RedactingFormatter('%(message)s')
    record = logging.LogRecord('test', logging.INFO, '', 0, url, (), None)
    formatter_redacted = formatter.format(record)
    
    assert direct_redacted == formatter_redacted, f"직접 마스킹({direct_redacted})과 로깅 포매터({formatter_redacted}) 결과가 일치해야 합니다."
