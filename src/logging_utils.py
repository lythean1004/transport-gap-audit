"""공공 API 인증정보를 가리는 공통 로깅 도구."""
import logging
import re

SENSITIVE_KEYS = ['TAGO_SERVICE_KEY', 'DATA_GO_KR_SERVICE_KEY', 'SEOUL_API_KEY',
                  'serviceKey', 'consumer_key', 'consumer_secret', 'accessToken',
                  'access_token', 'api_key', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'x-goog-api-key']

class RedactingFormatter(logging.Formatter):
    """URL 쿼리·JSON·환경변수 표기와 서울 API 경로를 마스킹한다."""
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        names = '|'.join(map(re.escape, SENSITIVE_KEYS))
        self.pattern = re.compile(rf'((?:{names})[\"\x27]?\s*[:=]\s*[\"\x27]?)([^&\s\x27\"}},]+)', re.I)

    def format(self, record):
        value = self.pattern.sub(r'\1REDACTED', super().format(record))
        return re.sub(r'(https?://(?:openapi|swopenapi)\.seoul\.go\.kr(?::\d+)?/)[^/\s]+/', r'\1REDACTED/', value, flags=re.I)

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    return logger
