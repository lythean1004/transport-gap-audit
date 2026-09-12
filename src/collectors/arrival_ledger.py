"""Arrival ledger management and resume decision logic for 7D collection."""

import csv
from pathlib import Path
from typing import Any

LEDGER_COLUMNS = (
    "obs_date",
    "slot_hhmm",
    "citycode",
    "nodeid",
    "outcome",
    "retry_count",
    "called_at_kst",
    "http_status",
    "result_code",
    "result_msg",
    "item_count",
    "raw_path",
    "schema_version",
)

ALLOWED_OUTCOMES = frozenset({"ok_with_items", "ok_empty", "api_error", "BUDGET_STOP"})
SCHEMA_VERSION = "v1"


def load_ledger(path: str | Path) -> dict[tuple[str, str, str, str], dict[str, str]]:
    """
    수집 원장 CSV를 로드하여 (obs_date, slot_hhmm, citycode, nodeid) -> 행 매핑 dict를 반환한다.
    파일이 없으면 빈 dict를 반환한다.
    outcome == 'BUDGET_STOP' 인 행은 매핑에서 제외한다.
    동일 키에 대해 복수 행이 존재할 경우 retry_count가 큰 것, 동률이면 called_at_kst가 늦은 것을 채택한다.
    """
    p = Path(path)
    if not p.exists():
        return {}

    ledger: dict[tuple[str, str, str, str], dict[str, str]] = {}

    with open(p, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            outcome = str(row.get("outcome", "")).strip()
            if outcome == "BUDGET_STOP":
                continue

            key = (
                str(row.get("obs_date", "")).strip(),
                str(row.get("slot_hhmm", "")).strip(),
                str(row.get("citycode", "")).strip(),
                str(row.get("nodeid", "")).strip(),
            )

            if key not in ledger:
                ledger[key] = row
            else:
                existing = ledger[key]
                try:
                    ex_retry = int(existing.get("retry_count", 0))
                except (ValueError, TypeError):
                    ex_retry = 0
                try:
                    new_retry = int(row.get("retry_count", 0))
                except (ValueError, TypeError):
                    new_retry = 0

                if new_retry > ex_retry:
                    ledger[key] = row
                elif new_retry == ex_retry:
                    ex_called = str(existing.get("called_at_kst", ""))
                    new_called = str(row.get("called_at_kst", ""))
                    if new_called >= ex_called:
                        ledger[key] = row

    return ledger


def should_call(
    ledger: dict[tuple[str, str, str, str], dict[str, str]],
    key: tuple[str, str, str, str]
) -> tuple[bool, str]:
    """
    원장 상태를 기반으로 특정 슬롯/정류소 호출 여부 및 사유를 판정한다.
    반환값: (호출 여부, 사유 문자열)
    """
    if key not in ledger:
        return (True, "NEW")

    row = ledger[key]
    outcome = str(row.get("outcome", "")).strip()

    if outcome in ("ok_with_items", "ok_empty"):
        return (False, "DONE")

    if outcome == "api_error":
        try:
            retry_count = int(row.get("retry_count", 0))
        except (ValueError, TypeError):
            retry_count = 0

        if retry_count < 2:
            return (True, f"RETRY_{retry_count + 1}")
        else:
            return (False, "RETRY_EXHAUSTED")

    return (False, "UNKNOWN_OUTCOME")


def append_row(path: str | Path, row: dict[str, Any]) -> None:
    """
    원장 CSV 파일에 1행을 추가(append-only)한다.
    파일이 없거나 비어 있으면 정의된 LEDGER_COLUMNS 순서대로 헤더를 먼저 기록한다.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = (not p.exists()) or (p.stat().st_size == 0)

    with open(p, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        if write_header:
            writer.writeheader()
        clean_row = {col: str(row.get(col, "") if row.get(col) is not None else "") for col in LEDGER_COLUMNS}
        writer.writerow(clean_row)


def make_budget_stop_row(obs_date: str, slot_hhmm: str, called_at_kst: str, note: str) -> dict[str, str]:
    """
    예산 소진(BUDGET_STOP) 마커 행을 생성한다.
    """
    return {
        "obs_date": str(obs_date).strip(),
        "slot_hhmm": str(slot_hhmm).strip(),
        "citycode": "",
        "nodeid": "",
        "outcome": "BUDGET_STOP",
        "retry_count": "0",
        "called_at_kst": str(called_at_kst).strip(),
        "http_status": "",
        "result_code": "",
        "result_msg": str(note).strip(),
        "item_count": "",
        "raw_path": "",
        "schema_version": SCHEMA_VERSION,
    }


if __name__ == "__main__":
    test_path = Path("scratch/_ledger_test.csv")
    if test_path.exists():
        test_path.unlink()

    # 1) 빈 상태에서 load_ledger -> 길이 0 확인
    ledger = load_ledger(test_path)
    print(f"1. empty load_ledger len: {len(ledger)}")

    # 2) 없는 키에 should_call -> (True, 'NEW') 확인
    k1 = ("2026-09-10", "0700", "31130", "GGB222001318")
    call_1, reason_1 = should_call(ledger, k1)
    print(f"2. missing key should_call: ({call_1}, {reason_1!r})")

    # 3) ok_with_items 행 append 후 재로드 -> should_call = (False, 'DONE')
    r1 = {
        "obs_date": "2026-09-10",
        "slot_hhmm": "0700",
        "citycode": "31130",
        "nodeid": "GGB222001318",
        "outcome": "ok_with_items",
        "retry_count": "0",
        "called_at_kst": "2026-09-10T07:01:00+09:00",
        "http_status": "200",
        "result_code": "0",
        "result_msg": "NORMAL SERVICE.",
        "item_count": "15",
        "raw_path": "evidence/raw/31130_0700.json",
        "schema_version": "v1",
    }
    append_row(test_path, r1)
    ledger = load_ledger(test_path)
    call_2, reason_2 = should_call(ledger, k1)
    print(f"3. ok_with_items should_call: ({call_2}, {reason_2!r})")

    # 4) ok_empty 행 append (다른 키) -> should_call = (False, 'DONE')
    k2 = ("2026-09-10", "0705", "31130", "GGB222001318")
    r2 = {
        "obs_date": "2026-09-10",
        "slot_hhmm": "0705",
        "citycode": "31130",
        "nodeid": "GGB222001318",
        "outcome": "ok_empty",
        "retry_count": "0",
        "called_at_kst": "2026-09-10T07:06:00+09:00",
        "http_status": "200",
        "result_code": "0",
        "result_msg": "NORMAL SERVICE.",
        "item_count": "0",
        "raw_path": "evidence/raw/31130_0705.json",
        "schema_version": "v1",
    }
    append_row(test_path, r2)
    ledger = load_ledger(test_path)
    call_3, reason_3 = should_call(ledger, k2)
    print(f"4. ok_empty should_call: ({call_3}, {reason_3!r})")

    # 5) api_error retry_count=0 행 append (다른 키) -> (True, 'RETRY_1')
    k3 = ("2026-09-10", "0710", "31130", "GGB222001318")
    r3_0 = {
        "obs_date": "2026-09-10",
        "slot_hhmm": "0710",
        "citycode": "31130",
        "nodeid": "GGB222001318",
        "outcome": "api_error",
        "retry_count": "0",
        "called_at_kst": "2026-09-10T07:11:00+09:00",
        "http_status": "500",
        "result_code": "99",
        "result_msg": "TIMEOUT",
        "item_count": "",
        "raw_path": "",
        "schema_version": "v1",
    }
    append_row(test_path, r3_0)
    ledger = load_ledger(test_path)
    call_4, reason_4 = should_call(ledger, k3)
    print(f"5. api_error retry 0 should_call: ({call_4}, {reason_4!r})")

    # 6) 같은 키에 api_error retry_count=1 행 append -> (True, 'RETRY_2')
    r3_1 = dict(r3_0, retry_count="1", called_at_kst="2026-09-10T07:12:00+09:00")
    append_row(test_path, r3_1)
    ledger = load_ledger(test_path)
    call_5, reason_5 = should_call(ledger, k3)
    print(f"6. api_error retry 1 should_call: ({call_5}, {reason_5!r})")

    # 7) 같은 키에 api_error retry_count=2 행 append -> (False, 'RETRY_EXHAUSTED')
    r3_2 = dict(r3_0, retry_count="2", called_at_kst="2026-09-10T07:13:00+09:00")
    append_row(test_path, r3_2)
    ledger = load_ledger(test_path)
    call_6, reason_6 = should_call(ledger, k3)
    print(f"7. api_error retry 2 should_call: ({call_6}, {reason_6!r})")

    # 8) BUDGET_STOP 행 append 후 load_ledger 길이가 변하지 않는지 확인
    prev_len = len(ledger)
    b_row = make_budget_stop_row("2026-09-10", "0715", "2026-09-10T07:15:00+09:00", "daily budget limit reached")
    append_row(test_path, b_row)
    ledger = load_ledger(test_path)
    print(f"8. after BUDGET_STOP len check: prev={prev_len}, new={len(ledger)} (changed: {prev_len != len(ledger)})")

    # 9) 최종 파일 전체 원문 출력 (헤더 포함)
    print("\n9. final test file raw content:")
    print(test_path.read_text(encoding="utf-8").strip())

    # 10) 마지막에 scratch/_ledger_test.csv 삭제하고 존재 여부 출력
    test_path.unlink()
    print(f"\n10. test file cleanup exists: {test_path.exists()}")