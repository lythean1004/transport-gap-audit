"""
7A′ — 노선정보 검증 및 서비스 시간 추출
7C 스모크 결과에서 나온 distinct routeid를 대상으로 getRouteInfoIem을 호출하고
data/staged/route_service_hours.parquet 를 빌드한다.
"""
import os
import sys
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

ENDPOINT = "https://apis.data.go.kr/1613000/BusRouteInfoInqireService/getRouteInfoIem"

def get_service_key():
    key = os.getenv("TAGO_SERVICE_KEY")
    if not key:
        print("[오류] 환경변수 TAGO_SERVICE_KEY가 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)
    return key

def load_distinct_routes_from_smoke():
    log_path = Path("evidence/smoke_log.csv")
    if not log_path.exists():
        raise FileNotFoundError("evidence/smoke_log.csv 파일이 없습니다. 7C 스모크 선행 필요.")
    
    df_log = pd.read_csv(log_path)
    latest = df_log.iloc[-1]
    citycode = str(latest["citycode"]).strip()
    raw_path = Path(str(latest["raw_path"]))
    
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
        
    route_map = {}
    for it in items:
        rid = str(it.get("routeid", "")).strip()
        rno = str(it.get("routeno", "")).strip()
        rtp = str(it.get("routetp", "")).strip()
        if rid and rid not in route_map:
            route_map[rid] = {"routeno": rno, "routetp": rtp}
            
    return citycode, route_map

def format_hhmm(val):
    if val is None or pd.isna(val) or str(val).strip() == "":
        return None
    val_str = str(val).strip()
    # 숫자 문자열인 경우 4자리 zero-padding
    if val_str.isdigit():
        return val_str.zfill(4)
    return val_str

def main():
    service_key = get_service_key()
    citycode, route_map = load_distinct_routes_from_smoke()
    
    route_ids = list(route_map.keys())
    print(f"[{citycode}] 7C 스모크에서 {len(route_ids)}개의 고유 노선 ID 발견.")
    
    # Cap 20 calls
    if len(route_ids) > 20:
        print(f"[경고] 노선 수가 20개를 초과하여 20개로 제한합니다.")
        route_ids = route_ids[:20]

    out_raw_dir = Path("evidence/route_info")
    out_raw_dir.mkdir(parents=True, exist_ok=True)
    
    records = []
    
    now_kst = datetime.now(KST)
    now_utc = datetime.now(UTC)
    time_str = now_kst.strftime("%Y%m%d-%H%M")
    
    print("\ngetRouteInfoIem 호출 시작...")
    
    for rid in route_ids:
        meta = route_map[rid]
        routeno_hint = meta["routeno"]
        
        params = {
            "serviceKey": service_key,
            "cityCode": citycode,
            "routeId": rid,
            "_type": "json"
        }
        
        try:
            r = requests.get(ENDPOINT, params=params, timeout=10)
            status_code = r.status_code
            try:
                body_dict = r.json()
            except Exception:
                body_dict = {"raw": r.text, "error": "json_decode_error"}
        except Exception as e:
            status_code = 0
            body_dict = {"error": str(e)}
            
        # Save raw body
        raw_file = out_raw_dir / f"{citycode}_{rid}_{time_str}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(body_dict, f, ensure_ascii=False, indent=2)
            
        # Parse item
        item = {}
        header = body_dict.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        
        if result_code == "00":
            body = body_dict.get("response", {}).get("body", {})
            raw_items = body.get("items")
            if isinstance(raw_items, dict):
                it_data = raw_items.get("item")
                if isinstance(it_data, dict):
                    item = it_data
                elif isinstance(it_data, list) and len(it_data) > 0:
                    item = it_data[0]

        # Extract fields
        routeno = item.get("routeno") or routeno_hint
        routetp = item.get("routetp") or meta["routetp"]
        startnodenm = item.get("startnodenm") or None
        endnodenm = item.get("endnodenm") or None
        
        raw_start = item.get("startvehicletime")
        raw_end = item.get("endvehicletime")
        
        start_hhmm = format_hhmm(raw_start)
        end_hhmm = format_hhmm(raw_end)
        
        interval = item.get("intervaltime")
        interval_sat = item.get("intervalsattime")
        interval_sun = item.get("intervalsuntime")
        
        # Boolean derivation
        first_bus_ok = None
        if start_hhmm is not None:
            first_bus_ok = (start_hhmm <= "0630")
            
        last_bus_ok = None
        if end_hhmm is not None:
            last_bus_ok = (end_hhmm >= "2200")
            
        records.append({
            "citycode": citycode,
            "routeid": rid,
            "routeno": str(routeno) if routeno is not None else None,
            "routetp": str(routetp) if routetp is not None else None,
            "startnodenm": str(startnodenm) if startnodenm is not None else None,
            "endnodenm": str(endnodenm) if endnodenm is not None else None,
            "startvehicletime": start_hhmm,
            "endvehicletime": end_hhmm,
            "intervaltime": float(interval) if interval is not None and str(interval).isdigit() else None,
            "intervalsattime": float(interval_sat) if interval_sat is not None and str(interval_sat).isdigit() else None,
            "intervalsuntime": float(interval_sun) if interval_sun is not None and str(interval_sun).isdigit() else None,
            "fetched_at_kst": now_kst.isoformat(),
            "fetched_at_utc": now_utc.isoformat(),
            "raw_path": str(raw_file).replace("\\", "/"),
            "first_bus_ok": first_bus_ok,
            "last_bus_ok": last_bus_ok
        })
        
        print(f"  [{rid}] {routeno:<8} | 첫차: {str(start_hhmm):<6} | 막차: {str(end_hhmm):<6} | 평일배차: {str(interval):<4} | first_ok={first_bus_ok} | last_ok={last_bus_ok}")

    df = pd.DataFrame(records)
    
    # 타입 명시적 지정 (pandas NA 지원)
    df["startvehicletime"] = df["startvehicletime"].astype("string")
    df["endvehicletime"] = df["endvehicletime"].astype("string")
    df["first_bus_ok"] = df["first_bus_ok"].astype("boolean")
    df["last_bus_ok"] = df["last_bus_ok"].astype("boolean")
    
    out_staged = Path("data/staged/route_service_hours.parquet")
    out_staged.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_staged, index=False)
    print(f"\n[완료] Staged Parquet 저장: {out_staged} ({len(df)}행)")
    
    # Coverage Report
    print("\n" + "=" * 90)
    print("노선별 첫차·막차 커버리지 보고 (Coverage Table)")
    print("=" * 90)
    print(f"{'routeid':<14} | {'routeno':<8} | {'start_time':<10} | {'status_start':<12} | {'end_time':<10} | {'status_end':<12}")
    print("-" * 90)
    for _, r in df.iterrows():
        s_val = r["startvehicletime"]
        e_val = r["endvehicletime"]
        st_s = "present" if pd.notna(s_val) else "missing"
        st_e = "present" if pd.notna(e_val) else "missing"
        print(f"{r['routeid']:<14} | {str(r['routeno']):<8} | {str(s_val):<10} | {st_s:<12} | {str(e_val):<10} | {st_e:<12}")
    print("=" * 90)

if __name__ == "__main__":
    main()
