import logging
import pytest
from src.collectors.api_common import fetch_public_api

def test_fetch_public_api_dry_run(caplog):
    with caplog.at_level(logging.INFO):
        res = fetch_public_api(
            source="test",
            endpoint="http://example.com",
            params={"serviceKey": "SECRET_KEY", "bjdongCd": "123"},
            dry_run=True
        )
    
    assert res == {}
    log_output = caplog.text
    assert "[DRY-RUN]" in log_output
    assert "SECRET_KEY" not in log_output
    assert "REDACTED" in log_output
