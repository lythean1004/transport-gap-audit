import logging
import io
import pytest
from src.logging_utils import RedactingFormatter

def test_secret_redaction():
    formatter = RedactingFormatter('%(message)s')
    
    # URL encoded parameters
    record1 = logging.LogRecord('test', logging.INFO, '', 0, 'Fetching URL: https://api.example.com?serviceKey=SECRET123&page=1', (), None)
    assert formatter.format(record1) == 'Fetching URL: https://api.example.com?serviceKey=REDACTED&page=1'
    
    # JSON payload
    record2 = logging.LogRecord('test', logging.INFO, '', 0, 'Payload: {"consumer_secret": "MY_SECRET_KEY"}', (), None)
    assert formatter.format(record2) == 'Payload: {"consumer_secret": "REDACTED"}'
    
    # Dict string
    record3 = logging.LogRecord('test', logging.INFO, '', 0, "Headers: {'x-goog-api-key': 'abcde12345'}", (), None)
    assert formatter.format(record3) == "Headers: {'x-goog-api-key': 'REDACTED'}"
    
    # Normal message
    record4 = logging.LogRecord('test', logging.INFO, '', 0, 'System started normally.', (), None)
    assert formatter.format(record4) == 'System started normally.'
