"""제출 분석의 날짜 불확실성과 비밀정보 차단 회귀검사."""
from datetime import date
import logging
import pytest
from scripts.submission.audit import date_bounds, gap_bounds, secret_findings
from src.collectors.arrival_snapshot import parse_response
from src.logging_utils import RedactingFormatter


def test_partial_dates_preserve_interval():
    assert date_bounds('Jan-15') == (date(2015, 1, 1), date(2015, 1, 31))
    assert date_bounds('2024-H1') == (date(2024, 1, 1), date(2024, 6, 30))
    assert date_bounds('2018') == (date(2018, 1, 1), date(2018, 12, 31))
    assert date_bounds('미정') is None


def test_interval_gap_and_missing_operation():
    assert gap_bounds('Jan-15', '2024-03-30') == (3346, 3376)
    assert gap_bounds('Jan-15', '') is None


def test_secret_scan_does_not_disclose_value():
    secret = 'synthetic-secret-for-test-only'
    found = secret_findings('TAGO_SERVICE_KEY=' + secret, [secret])
    assert found and secret not in str(found)
    assert not secret_findings('sha256=' + 'a' * 64, [])


@pytest.mark.parametrize('code,expected', [('00','ok_empty'),('0','api_error'),('03','api_error')])
def test_arrival_exact_result_code(code, expected):
    import json
    raw = json.dumps({'response': {'header': {'resultCode': code}, 'body': {'items': ''}}})
    assert parse_response(raw, 200)[0] == expected


@pytest.mark.parametrize('message', [
    'TAGO_SERVICE_KEY = "SYNTHETIC_TEST_SECRET"',
    'https://openapi.seoul.go.kr:8088/SYNTHETIC_TEST_SECRET/json/example/1/5/',
    '{"api_key": "SYNTHETIC_TEST_SECRET"}',
])
def test_extended_log_redaction(message):
    record = logging.LogRecord('test', 20, '', 0, message, (), None)
    assert 'SYNTHETIC_TEST_SECRET' not in RedactingFormatter('%(message)s').format(record)


def test_mock_generator_cannot_overwrite_staged():
    from pathlib import Path
    source = Path('create_mock.py').read_text(encoding='utf-8-sig')
    assert "df.write_parquet('data/staged/bldg_title.parquet')" not in source
    assert 'submission_v1' in source and 'mock_bldg_title.parquet' in source


def test_release_redacts_without_changing_source():
    from scripts.submission.package_release import sanitize_bytes
    original = b'url?serviceKey=synthetic-sensitive-value&cityCode=1'
    clean, changed = sanitize_bytes(original, '.csv', ['synthetic-sensitive-value'], relative_paths=False)
    assert changed and b'synthetic-sensitive-value' not in clean
    assert b'cityCode=1' in clean
    assert original.endswith(b'synthetic-sensitive-value&cityCode=1')


def test_release_raw_without_secrets_is_byte_identical():
    from scripts.submission.package_release import sanitize_bytes
    raw = b'\xef\xbb\xbfcol\r\nvalue\r\n'
    clean, changed = sanitize_bytes(raw, '.csv', [], relative_paths=False)
    assert clean == raw and not changed


def test_tago_arrival_uses_required_environment_name(monkeypatch):
    from src.collectors import tago_bus
    names=[]
    monkeypatch.setattr(tago_bus,'require_secret',lambda name:names.append(name) or 'test-only')
    monkeypatch.setattr(tago_bus,'fetch_public_api',lambda *a,**kw:{})
    tago_bus.get_arrival_info('1','stop')
    assert names==['TAGO_SERVICE_KEY']
