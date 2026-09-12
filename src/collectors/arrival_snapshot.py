"""7D Arrival snapshot collector with budget guard, ledger tracking, nominal slot mapping, and sweep retry."""

import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

from src.collectors.arrival_slots import build_slot_labels, snap_to_slot, TZ
from src.collectors.arrival_ledger import (
    load_ledger,
    should_call,
    append_row,
    make_budget_stop_row,
)
from src.collectors.arrival_budget import BudgetGuard, preflight, format_preflight

BASE_URL = "https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList"
DEFAULT_REGISTRY = "evidence/stop_registry.csv"
DEFAULT_LEDGER = "evidence/arrival_ledger.csv"
RAW_BASE_DIR = "evidence/arrival_raw"
MAX_SWEEP_ATTEMPTS = 10


def load_target_stops(registry_path: str | Path = DEFAULT_REGISTRY) -> list[dict[str, str]]:
    """evidence/stop_registry.csv 에서 review_status == 'human_verified' 상태인 대상 정류소를 로드한다."""
    p = Path(registry_path)
    if not p.exists():
        raise RuntimeError(f"정류소 레지스트리({registry_path})가 존재하지 않습니다.")

    stops: list[dict[str, str]] = []
    with open(p, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if str(r.get("review_status", "")).strip() == "human_verified":
                citycode = str(r.get("citycode", "")).strip()
                nodeid = str(r.get("nodeid", "")).strip()
                if citycode and nodeid:
                    stops.append({"citycode": citycode, "nodeid": nodeid})

    if not stops:
        raise RuntimeError("review_status == 'human_verified' 상태인 대상 정류소가 0건입니다.")
    return stops


def restore_budget_guard(ledger_path: str | Path, obs_date: str) -> BudgetGuard:
    """원장 파일에서 오늘 obs_date에 해당하는 시도 횟수를 전수 복원한다."""
    guard = BudgetGuard()
    p = Path(ledger_path)
    count = 0
    if p.exists():
        with open(p, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if str(r.get("obs_date", "")).strip() == obs_date:
                    if str(r.get("outcome", "")).strip() != "BUDGET_STOP":
                        count += 1
                        guard.record_attempt()
    print(f"[budget] restored from ledger: {count} attempts today (obs_date={obs_date})")
    return guard


def parse_response(text: str, http_status: int) -> tuple[str, str, str, int, list[dict]]:
    """TAGO 도착정보 API 응답 파싱 (arrtime_sec 보존, routeid 중복 제거 금지, totalCount 절단 경고)."""
    if http_status != 200:
        return ("api_error", str(http_status), f"HTTP status {http_status}", 0, [])

    try:
        data = json.loads(text)
    except Exception as e:
        return ("api_error", "JSON_PARSE_ERROR", str(e), 0, [])

    header = data.get("response", {}).get("header", {})
    result_code = str(header.get("resultCode", "")).strip()
    result_msg = str(header.get("resultMsg", "")).strip()

    body = data.get("response", {}).get("body", {})
    items_container = body.get("items", {})
    raw_items = []
    if isinstance(items_container, dict):
        raw_items = items_container.get("item", [])
    elif isinstance(items_container, list):
        raw_items = items_container

    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    elif not isinstance(raw_items, list):
        raw_items = []

    item_count = len(raw_items)

    try:
        total_count = int(body.get("totalCount", item_count))
    except (ValueError, TypeError):
        total_count = item_count

    if total_count > item_count:
        result_msg = f"{result_msg} [TRUNCATED total={total_count} got={item_count}]".strip()

    # 순서대로 item_seq 부여 및 arrtime 초 단위 보존
    structured_items = []
    for seq, item in enumerate(raw_items):
        item_copy = dict(item)
        item_copy["item_seq"] = seq
        if "arrtime" in item_copy:
            item_copy["arrtime_sec"] = item_copy["arrtime"]
        structured_items.append(item_copy)

    if result_code == "00":
        outcome = "ok_with_items" if item_count > 0 else "ok_empty"
    else:
        outcome = "api_error"

    return (outcome, result_code, result_msg, item_count, structured_items)


def run_collection(
    dry_run: bool = False,
    obs_date: str | None = None,
    slot: str | None = None,
    no_sweep: bool = False,
    registry_path: str = DEFAULT_REGISTRY,
    ledger_path: str = DEFAULT_LEDGER,
    raw_dir: str = RAW_BASE_DIR,
) -> int:
    """수집기 실행 루틴."""
    now_kst = datetime.now(TZ)
    if not obs_date:
        obs_date = now_kst.strftime("%Y-%m-%d")

    # 1) --slot 검증
    if slot:
        valid_slots = build_slot_labels()
        if slot not in valid_slots:
            print(f"[ERROR] 유효하지 않은 슬롯 라벨: {slot}", file=sys.stderr)
            return 1

    # 대상 정류소 로드
    try:
        stops = load_target_stops(registry_path)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    # 3-a) Preflight 계산 및 출력
    pf = preflight(stops=len(stops))
    print("=== PREFLIGHT CHECK ===")
    print(format_preflight(pf))
    if not pf["allowed"]:
        print("[ABORT] Preflight check failed: calls_per_day exceeds limit.", file=sys.stderr)
        return 1

    # 8, 9) BudgetGuard 복원
    guard = restore_budget_guard(ledger_path, obs_date)
    if guard.should_stop():
        print("[ABORT] Budget guard already stopped today.", file=sys.stderr)
        return 1

    # 3-b) 슬롯 라벨 결정
    nominal_slot = slot
    if not nominal_slot:
        nominal_slot = snap_to_slot(now_kst)
        if nominal_slot is None:
            if not dry_run:
                print(f"[INFO] 현재 시각({now_kst.isoformat()})은 수집 창 밖입니다. 정상 종료합니다.")
                return 0
            else:
                available = build_slot_labels()
                nominal_slot = available[0]
                print(f"[dry-run] 현재 시각({now_kst.isoformat()})은 수집 창 밖이지만 dry-run 모드이므로 첫 슬롯({nominal_slot})으로 가상 진행합니다.")

    print(f"\n[START] obs_date={obs_date} slot_hhmm={nominal_slot} stops={len(stops)} dry_run={dry_run}")

    # 원장 로드
    ledger = load_ledger(ledger_path)

    # 3-c, d, e) 현재 슬롯 정류소 순회
    for stop in stops:
        citycode = stop["citycode"]
        nodeid = stop["nodeid"]
        key = (obs_date, nominal_slot, citycode, nodeid)
        call_needed, reason = should_call(ledger, key)

        raw_rel_path = f"{raw_dir}/{obs_date}/{citycode}_{nodeid}_{nominal_slot}.json"
        masked_params = {
            "serviceKey": "****",
            "cityCode": citycode,
            "nodeId": nodeid,
            "numOfRows": 100,
            "pageNo": 1,
            "_type": "json",
        }
        masked_url = f"{BASE_URL}?{urlencode(masked_params)}"

        if dry_run:
            print(f"\n[DRY-RUN STOP] key={key}")
            print(f"  should_call: ({call_needed}, {reason!r})")
            print(f"  planned_url: {masked_url}")
            print(f"  planned_raw_path: {raw_rel_path}")
            continue

        if not call_needed:
            print(f"[SKIP] key={key} reason={reason}")
            continue

        # 예산 가드 체크
        guard.record_attempt()
        if guard.should_stop():
            print(f"[STOP] Budget hard stop reached at count={guard.count}", file=sys.stderr)
            has_budget_stop = False
            lp = Path(ledger_path)
            if lp.exists():
                with open(lp, mode="r", encoding="utf-8", newline="") as f:
                    rdr = csv.DictReader(f)
                    for row_check in rdr:
                        if str(row_check.get("obs_date", "")).strip() == obs_date and str(row_check.get("outcome", "")).strip() == "BUDGET_STOP":
                            has_budget_stop = True
                            break
            if not has_budget_stop:
                b_row = make_budget_stop_row(
                    obs_date=obs_date,
                    slot_hhmm=nominal_slot,
                    called_at_kst=datetime.now(TZ).isoformat(),
                    note="daily budget limit reached",
                )
                append_row(ledger_path, b_row)
            return 1

        service_key = os.environ.get("TAGO_SERVICE_KEY", "").strip()
        if not service_key:
            print("[ERROR] TAGO_SERVICE_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
            return 1

        called_at = datetime.now(TZ).isoformat()
        real_params = dict(masked_params, serviceKey=service_key)

        retry_attempt = 0
        if reason.startswith("RETRY_"):
            try:
                retry_attempt = int(reason.split("_")[1])
            except Exception:
                retry_attempt = 1

        try:
            resp = requests.get(BASE_URL, params=real_params, timeout=10)
            resp.encoding = "utf-8"
            status_code = resp.status_code
            text = resp.text
        except Exception as e:
            status_code = 0
            text = ""
            outcome, res_code, res_msg, it_count, _ = ("api_error", "REQ_EXCEPTION", str(e), 0, [])
        else:
            outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)

        if text:
            out_file = Path(raw_rel_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(text, encoding="utf-8")

        row = {
            "obs_date": obs_date,
            "slot_hhmm": nominal_slot,
            "citycode": citycode,
            "nodeid": nodeid,
            "outcome": outcome,
            "retry_count": retry_attempt,
            "called_at_kst": called_at,
            "http_status": status_code,
            "result_code": res_code,
            "result_msg": res_msg,
            "item_count": it_count,
            "raw_path": raw_rel_path if text else "",
            "schema_version": "v1",
        }
        append_row(ledger_path, row)
        ledger[key] = row
        print(f"[CALLED] key={key} outcome={outcome} items={it_count}")

    # 사양 10: 슬롯 처리 후 sweep
    if not no_sweep:
        sweep_candidates = []
        for k, r in ledger.items():
            k_obs, k_slot, k_city, k_node = k
            if k_obs == obs_date:
                need, reas = should_call(ledger, k)
                if need and reas.startswith("RETRY_"):
                    sweep_candidates.append((k_slot, k, reas))

        sweep_candidates.sort(key=lambda x: x[0])
        total_pending = len(sweep_candidates)
        print(f"\n[sweep] pending_retry={total_pending}")

        sweep_batch = sweep_candidates[:MAX_SWEEP_ATTEMPTS]
        for sw_slot, sw_key, sw_reason in sweep_batch:
            _, _, sw_city, sw_node = sw_key
            sw_raw_rel_path = f"{raw_dir}/{obs_date}/{sw_city}_{sw_node}_{sw_slot}.json"
            sw_masked_params = {
                "serviceKey": "****",
                "cityCode": sw_city,
                "nodeId": sw_node,
                "numOfRows": 100,
                "pageNo": 1,
                "_type": "json",
            }
            sw_masked_url = f"{BASE_URL}?{urlencode(sw_masked_params)}"

            if dry_run:
                print(f"[DRY-RUN SWEEP] key={sw_key} reason={sw_reason}")
                print(f"  planned_url: {sw_masked_url}")
                print(f"  planned_raw_path: {sw_raw_rel_path}")
                continue

            guard.record_attempt()
            if guard.should_stop():
                print(f"[STOP] Budget hard stop reached during sweep at count={guard.count}", file=sys.stderr)
                has_budget_stop = False
                lp = Path(ledger_path)
                if lp.exists():
                    with open(lp, mode="r", encoding="utf-8", newline="") as f:
                        rdr = csv.DictReader(f)
                        for row_check in rdr:
                            if str(row_check.get("obs_date", "")).strip() == obs_date and str(row_check.get("outcome", "")).strip() == "BUDGET_STOP":
                                has_budget_stop = True
                                break
                if not has_budget_stop:
                    b_row = make_budget_stop_row(
                        obs_date=obs_date,
                        slot_hhmm=sw_slot,
                        called_at_kst=datetime.now(TZ).isoformat(),
                        note="daily budget limit reached during sweep",
                    )
                    append_row(ledger_path, b_row)
                return 1

            service_key = os.environ.get("TAGO_SERVICE_KEY", "").strip()
            if not service_key:
                print("[ERROR] TAGO_SERVICE_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
                return 1

            called_at = datetime.now(TZ).isoformat()
            real_params = dict(sw_masked_params, serviceKey=service_key)
            try:
                sw_attempt = int(sw_reason.split("_")[1])
            except Exception:
                sw_attempt = 1

            try:
                resp = requests.get(BASE_URL, params=real_params, timeout=10)
                resp.encoding = "utf-8"
                status_code = resp.status_code
                text = resp.text
            except Exception as e:
                status_code = 0
                text = ""
                outcome, res_code, res_msg, it_count, _ = ("api_error", "REQ_EXCEPTION", str(e), 0, [])
            else:
                outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)

            if text:
                out_file = Path(sw_raw_rel_path)
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(text, encoding="utf-8")

            sw_row = {
                "obs_date": obs_date,
                "slot_hhmm": sw_slot,
                "citycode": sw_city,
                "nodeid": sw_node,
                "outcome": outcome,
                "retry_count": sw_attempt,
                "called_at_kst": called_at,
                "http_status": status_code,
                "result_code": res_code,
                "result_msg": res_msg,
                "item_count": it_count,
                "raw_path": sw_raw_rel_path if text else "",
                "schema_version": "v1",
            }
            append_row(ledger_path, sw_row)
            ledger[sw_key] = sw_row
            print(f"[SWEEP CALLED] key={sw_key} outcome={outcome} items={it_count}")

    # 슬롯 처리 종료 후 예산 로그
    print(f"\n{guard.slot_log(nominal_slot)}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="7D Arrival Snapshot Collector")
    parser.add_argument("--dry-run", action="store_true", help="가상 실행 모드 (HTTP 호출 및 파일 쓰기 없음)")
    parser.add_argument("--obs-date", type=str, default=None, help="관측 일자 (YYYY-MM-DD, 기본값: 오늘 KST)")
    parser.add_argument("--slot", type=str, default=None, help="명목 슬롯 라벨 (HHMM, 기본값: 현재시각 스냅)")
    parser.add_argument("--no-sweep", action="store_true", help="슬롯 종료 후 api_error 재시도(sweep) 비활성화")
    parser.add_argument("--registry", type=str, default=DEFAULT_REGISTRY, help="정류소 레지스트리 경로")
    parser.add_argument("--ledger", type=str, default=DEFAULT_LEDGER, help="수집 원장 CSV 경로")
    parser.add_argument("--raw-dir", type=str, default=RAW_BASE_DIR, help="원본 JSON 저장 디렉터리")
    args = parser.parse_args()

    exit_code = run_collection(
        dry_run=args.dry_run,
        obs_date=args.obs_date,
        slot=args.slot,
        no_sweep=args.no_sweep,
        registry_path=args.registry,
        ledger_path=args.ledger,
        raw_dir=args.raw_dir,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
