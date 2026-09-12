"""
TAGO 버스노선정보 서비스 (15098529) 4개 오퍼레이션 실측 스모크 테스트.
결과를 data/raw/tago_route_smoke/ 에 저장하고 호출 결과를 반환/로깅한다.
"""
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# AGENTS.md 규칙: 반드시 환경변수 TAGO_SERVICE_KEY (하드코딩 금지)
SERVICE_KEY = os.getenv("TAGO_SERVICE_KEY")
if not SERVICE_KEY:
    raise RuntimeError("환경변수 TAGO_SERVICE_KEY가 설정되지 않았습니다.")

BASE_URL = "https://apis.data.go.kr/1613000/BusRouteInfoInqireService"
CITY_CODE = "31240"  # 화성시 (확인된 도시코드)
SAMPLE_ROUTE_ID = "GGB200000008"  # 화성시 400번 버스 (확인된 유효 routeId)

OPERATIONS = [
    {
        "name": "getCtyCodeList",
        "params": {"_type": "json", "numOfRows": 1, "pageNo": 1}
    },
    {
        "name": "getRouteNoList",
        "params": {"_type": "json", "cityCode": CITY_CODE, "numOfRows": 1, "pageNo": 1}
    },
    {
        "name": "getRouteAcctoThrghSttnList",
        "params": {"_type": "json", "cityCode": CITY_CODE, "routeId": SAMPLE_ROUTE_ID, "numOfRows": 1, "pageNo": 1}
    },
    {
        "name": "getRouteInfoIem",
        "params": {"_type": "json", "cityCode": CITY_CODE, "routeId": SAMPLE_ROUTE_ID, "numOfRows": 1, "pageNo": 1}
    }
]

def parse_result_code(data):
    """AGENTS.md 규칙에 따른 resultCode 해석"""
    if not isinstance(data, dict):
        return "api_error"
    header = data.get("response", {}).get("header", {})
    code = header.get("resultCode")
    if code == "00":
        items = data.get("response", {}).get("body", {}).get("items")
        if not items or (isinstance(items, dict) and not items.get("item")) or (isinstance(items, list) and len(items) == 0):
            return "ok_empty"
        return "ok_with_items"
    return "api_error"

def run_smoke():
    out_dir = Path("data/raw/tago_route_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    for op in OPERATIONS:
        op_name = op["name"]
        url = f"{BASE_URL}/{op_name}"
        params = {"serviceKey": SERVICE_KEY, **op["params"]}
        
        print(f"[{op_name}] 스모크 호출 중...")
        try:
            r = requests.get(url, params=params, timeout=10)
            status_code = r.status_code
            try:
                data = r.json()
            except Exception:
                data = {"raw_text": r.text, "http_status": status_code}
        except Exception as e:
            status_code = 0
            data = {"error": str(e)}
            
        classification = parse_result_code(data)
        
        out_file = out_dir / f"{op_name}_smoke.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({
                "operation": op_name,
                "url": url,
                "http_status": status_code,
                "classification": classification,
                "response": data
            }, f, ensure_ascii=False, indent=2)
            
        results[op_name] = {
            "http_status": status_code,
            "classification": classification,
            "file": str(out_file)
        }
        print(f"  -> HTTP {status_code} | 결과 분류: {classification} | 파일: {out_file.name}")
        
    return results

if __name__ == "__main__":
    run_smoke()
