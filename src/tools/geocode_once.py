"""
VWORLD 지오코딩 1회성 헬퍼 도구 (One-shot Geocoding Helper)

주의: 브이월드 API 이용약관에 따라 "API 요청은 실시간으로 사용해야 하며 
별도의 저장장치나 데이터베이스에 저장할 수 없습니다."
따라서 본 스크립트는 결과를 화면(stdout)에만 출력하며, 
CSV, Parquet, DB 등 어떠한 디스크 저장장치에도 결과를 기록하지 않습니다.
(결과는 사람이 확인하고 pilots.yaml 등에 수기 입력하는 용도로만 사용)
"""
import sys
import json
import argparse
from urllib.parse import urlencode
import requests
from pathlib import Path

# Add project root to sys.path if needed
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import require_secret

ERROR_MESSAGES = {
    "INVALID_KEY": "등록되지 않은 인증키입니다.",
    "INCORRECT_KEY": "인증키 정보 불일치 (발급 시 입력한 도메인과 로컬/요청 환경이 다를 수 있습니다).",
    "UNAVAILABLE_KEY": "사용할 수 없는 인증키입니다.",
    "OVER_REQUEST_LIMIT": "일일 요청 한도(40,000건)를 초과했습니다.",
    "SYSTEM_ERROR": "브이월드 시스템 에러.",
    "UNKNOWN_ERROR": "알 수 없는 에러가 발생했습니다."
}

def geocode_address(address: str, addr_type: str):
    """지오코딩을 수행하고 결과를 출력합니다."""
    key = require_secret("VWORLD_API_KEY")
    
    url = "https://api.vworld.kr/req/address"
    params = {
        "service": "address",
        "request": "getCoord",
        "version": "2.0",
        "crs": "EPSG:4326",
        "type": addr_type,
        "address": address,
        "refine": "true",
        "simple": "false",
        "format": "json",
        "key": key
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[HTTP Error] {e}")
        sys.exit(1)
        
    try:
        data = resp.json()
    except ValueError:
        print("[JSON Parse Error] 브이월드 응답이 올바른 JSON이 아닙니다.")
        sys.exit(1)
        
    response_block = data.get("response", {})
    status = response_block.get("status")
    
    if status == "ERROR":
        error_code = response_block.get("error", {}).get("text", "UNKNOWN_ERROR")
        msg = ERROR_MESSAGES.get(error_code, error_code)
        print(f"[API ERROR] 상태: ERROR, 코드: {error_code} - {msg}")
        sys.exit(1)
        
    if status == "NOT_FOUND":
        print(f"[NOT FOUND] 주소를 찾을 수 없습니다: {address}")
        sys.exit(2)
        
    if status == "OK":
        result = response_block.get("result", {})
        point = result.get("point", {})
        x = point.get("x") # 경도 (Longitude)
        y = point.get("y") # 위도 (Latitude)
        
        # refine=true 일 때 정제된 주소
        items = result.get("items", [])
        refined_addr = address
        if items and isinstance(items, list):
            refined_addr = items[0].get("text", address)
            
        print(f"상태: {status}")
        print(f"원 주소: {address}")
        print(f"정제된 주소: {refined_addr}")
        print(f"X (경도/Longitude): {x}")
        print(f"Y (위도/Latitude) : {y}")
        print("\n--- YAML Snippet (ready to paste) ---")
        print(f"  lat: {y}    # Y (위도)")
        print(f"  lon: {x}    # X (경도)")
        print("-------------------------------------")
        sys.exit(0)
        
    print(f"[UNKNOWN STATUS] 알 수 없는 상태 코드: {status}")
    sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="브이월드 지오코딩 1회성 헬퍼")
    parser.add_argument("address", help="지오코딩할 단일 주소 (예: '경기도 성남시 분당구 판교로 242')")
    parser.add_argument("--type", choices=["ROAD", "PARCEL"], default="ROAD", 
                        help="주소 타입 (ROAD: 도로명, PARCEL: 지번). 기본값: ROAD")
    
    args = parser.parse_args()
    
    # Refuse batch processing (just an explicit safety check although argparse handles single arg)
    if "," in args.address or "\n" in args.address:
        print("[BATCH INPUT REFUSED] 여러 개의 주소나 배치 파일 입력은 지원하지 않습니다. 1회 1건만 실행하세요.")
        sys.exit(1)
        
    geocode_address(args.address, args.type)
