"""
7C′ — 단일 수동 스모크 (도착정보 조회)
Endpoint: https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList
"""
import os
import sys
import json
import argparse
import requests
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

ENDPOINT = "https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList"

def get_service_key():
    key = os.getenv("TAGO_SERVICE_KEY")
    if not key:
        print("[오류] 환경변수 TAGO_SERVICE_KEY가 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)
    return key

def call_arrival_api(citycode: str, nodeid: str, service_key: str):
    """
    URL-encoded 형태와 decoded 형태를 실측 테스트하여 성공한 형태를 확정한다.
    """
    decoded_key = urllib.parse.unquote(service_key)
    
    # 1. decoded key via requests params (requests will URL-encode it)
    params = {
        "serviceKey": decoded_key,
        "cityCode": citycode,
        "nodeId": nodeid,
        "_type": "json",
        "numOfRows": 100,
        "pageNo": 1
    }
    
    key_form_used = "decoded_in_params(url_encoded_by_client)"
    try:
        r = requests.get(ENDPOINT, params=params, timeout=15)
        if r.status_code == 200:
            return r, key_form_used
    except Exception:
        pass

    # 2. fallback: raw string URL concatenation
    raw_url = f"{ENDPOINT}?serviceKey={service_key}&cityCode={citycode}&nodeId={nodeid}&_type=json&numOfRows=100&pageNo=1"
    key_form_used = "raw_verbatim_in_url"
    r = requests.get(raw_url, timeout=15)
    return r, key_form_used

def parse_items(body_dict):
    items = body_dict.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return []
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list

def classify_outcome(result_code, item_count):
    if result_code == "00":
        return "ok_with_items" if item_count > 0 else "ok_empty"
    return "api_error"

def main():
    parser = argparse.ArgumentParser(description="TAGO 도착정보 단일 스모크 호출")
    parser.add_argument("--citycode", required=True, help="도시코드 (예: 31130)")
    parser.add_argument("--nodeid", required=True, help="정류소 Node ID (예: GGB222001318)")
    args = parser.parse_args()

    citycode = str(args.citycode).strip()
    nodeid = str(args.nodeid).strip()

    now_kst = datetime.now(KST)
    now_utc = datetime.now(UTC)

    time_str_kst = now_kst.strftime("%Y%m%d-%H%M")
    smoke_test_at_kst = now_kst.isoformat()
    smoke_test_at_utc = now_utc.isoformat()

    service_key = get_service_key()

    print(f"[{citycode} / {nodeid}] 도착정보 스모크 호출 시작 (KST {time_str_kst})...")
    
    response, key_form_used = call_arrival_api(citycode, nodeid, service_key)
    http_status = response.status_code
    raw_text = response.text

    # 1. Raw body verbatim 저장
    evidence_dir = Path("evidence/smoke")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    raw_filename = f"{citycode}_{nodeid}_{time_str_kst}.json"
    raw_path = evidence_dir / raw_filename

    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_text)
    print(f"  -> Raw 응답 저장 완료: {raw_path}")

    # JSON 파싱
    result_code = ""
    result_msg = ""
    items = []
    try:
        body_dict = response.json()
        header = body_dict.get("response", {}).get("header", {})
        result_code = str(header.get("resultCode", ""))
        result_msg = str(header.get("resultMsg", ""))
        items = parse_items(body_dict)
    except Exception as e:
        result_msg = f"JSON parse error: {e}"

    item_count = len(items)
    outcome = classify_outcome(result_code, item_count)

    # 2. 항목 테이블 출력
    print("\n" + "=" * 80)
    print(f"{'routeid':<16} | {'routeno':<10} | {'routetp':<12} | {'arrprev':<8} | {'vehicletp':<10} | {'arrtime(sec)':<12}")
    print("-" * 80)
    
    # routeid와 arrtime이 모두 비어있지 않고 arrtime이 초 단위 정수로 파싱되는 item 수
    items_with_valid_info = 0
    distinct_routeids = []
    for it in items:
        rid = str(it.get("routeid", "")).strip()
        rno = str(it.get("routeno", "")).strip()
        rtp = str(it.get("routetp", "")).strip()
        prev = str(it.get("arrprevstationcnt", "")).strip()
        vtp = str(it.get("vehicletp", "")).strip()
        arrt = str(it.get("arrtime", "")).strip()
        print(f"{rid:<16} | {rno:<10} | {rtp:<12} | {prev:<8} | {vtp:<10} | {arrt:<12}")
        if rid and rid not in distinct_routeids:
            distinct_routeids.append(rid)
        if rid and arrt:
            try:
                int(arrt)
                items_with_valid_info += 1
            except ValueError:
                pass
            
    print("=" * 80)
    print(f"총 항목 수: {item_count}건 (routeid+arrtime 유효: {items_with_valid_info}건) | 결과 분류: {outcome}")
    print(f"고유 노선 ID (distinct routeid): {distinct_routeids}")
    print(f"사용된 serviceKey 형태: {key_form_used}")

    # 3. evidence/smoke_log.csv에 1행 추가
    log_file = Path("evidence/smoke_log.csv")
    write_header = not log_file.exists()
    
    log_row = {
        "citycode": citycode,
        "nodeid": nodeid,
        "smoke_test_at_kst": smoke_test_at_kst,
        "smoke_test_at_utc": smoke_test_at_utc,
        "http_status": http_status,
        "resultCode": result_code,
        "resultMsg": result_msg,
        "item_count": item_count,
        "items_with_routeid_and_arrtime": items_with_valid_info,
        "schema_version": "v2",
        "outcome": outcome,
        "raw_path": str(raw_path).replace("\\", "/"),
        "key_form_used": key_form_used
    }

    import csv
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(log_row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(log_row)
    print(f"  -> smoke_log.csv 기록 완료: {log_file}")

    if outcome == "ok_empty":
        print("\n[알림] outcome이 ok_empty 입니다. 정류소 무효 판정이 아니며, 평일 주간 운영 시간대에 재실행이 필요합니다.")

if __name__ == "__main__":
    main()
