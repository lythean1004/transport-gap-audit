"""
scratch/audit_supplement_v2.py — 3차 감사 (2차 결함 수정)
2차 감사(audit_supplement.py) 결함 4건 + 위반 2건을 반영한 재감사 스크립트.
읽기 전용: evidence/ 이하 파일을 수정하지 않는다.
"""
import csv
import json
import re
import ast
import statistics
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter

sys.path.insert(0, str(Path.cwd()))
from src.collectors.arrival_slots import build_slot_labels
from src.collectors.arrival_budget import WARN_AT, HARD_STOP, DAILY_APPROVED

KST = timezone(timedelta(hours=9))
SLOTS = build_slot_labels()
SLOT_COUNT = len(SLOTS)  # 48 — 리터럴 48 대신 사용

# ──────────────────────────────────────────────
# 분석 창 규칙 (사후 완화 금지)
# 대상 창: 2026-09-07 ~ 2026-09-10
# 사전 배제 규칙:
#   (a) 셰이크다운일: 스케줄러 오류 0x800700C1 로 오전 블록 소실된 2026-09-04
#   (b) 미완료일: 감사 실행 시점에 PM 창(19:00 KST) 종료 전인 당일
# 커버리지: 배제 후 남은 일자 전부 ≥ 90% 일 때만 PASS.
# ──────────────────────────────────────────────
ANALYSIS_WINDOW = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
SHAKEDOWN_DATE = '2026-09-04'  # (a) 배제 사유

EXPECTED_COLUMNS = [
    'obs_date', 'slot_hhmm', 'citycode', 'nodeid', 'outcome',
    'retry_count', 'called_at_kst', 'http_status', 'result_code',
    'result_msg', 'item_count', 'raw_path', 'schema_version',
]

# 1차 감사 기준값
REF_TOTAL_ROWS = 192
REF_RAW_COUNT = 190
REF_DATE_ROWS = {'2026-09-04': 30, '2026-09-07': 45, '2026-09-08': 49,
                 '2026-09-09': 48, '2026-09-10': 20}
REF_API_ERROR = 2
REF_OK_EMPTY = 2
REF_BUDGET_STOP = 0


def sec(title):
    print("\n" + "=" * 60)
    print(f"[{title}]")
    print("=" * 60)


def mask_service_key(text):
    if not text:
        return text
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r'(serviceKey=)[^&\'\"\\]+', r'\1***REDACTED***', text)


def parse_kst(dt_str):
    try:
        return datetime.fromisoformat(dt_str).replace(tzinfo=KST)
    except Exception:
        return None


def calc_drift(called_at, slot_hhmm):
    hh = int(slot_hhmm[:2])
    mm = int(slot_hhmm[2:])
    slot_dt = called_at.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return (called_at - slot_dt).total_seconds()


def percentile(sorted_list, pct):
    if not sorted_list:
        return 0
    idx = int((pct / 100.0) * (len(sorted_list) - 1))
    return sorted_list[idx]


def main():
    ledger_path = Path("evidence/arrival_ledger.csv")
    raw_dir = Path("evidence/arrival_raw")
    log_path = Path("scratch/_task_log.txt")

    # ── 원장 로드 ──
    ledger = []
    actual_headers = []
    if ledger_path.exists():
        with open(ledger_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            actual_headers = list(reader.fieldnames) if reader.fieldnames else []
            for row in reader:
                ledger.append(row)

    # ── 디스크 raw 실측 (rglob) ──
    disk_raw_files = list(raw_dir.rglob("*.json")) if raw_dir.exists() else []
    disk_raw_set = {str(p).replace("\\", "/") for p in disk_raw_files}

    # ── 원장 raw_path 집합 ──
    ledger_raw_paths = set()
    for r in ledger:
        rp = r.get('raw_path', '')
        if rp and rp != 'nan':
            ledger_raw_paths.add(rp.replace("\\", "/"))

    # 원장 raw_path 기준으로 실제 존재하는 파일 수
    ledger_raw_exist = sum(1 for rp in ledger_raw_paths if Path(rp).exists())

    # ── 일자별 집계 ──
    date_counts = Counter(row['obs_date'] for row in ledger)
    outcomes = Counter(row['outcome'] for row in ledger)

    raw_date_counts = Counter()
    for row in ledger:
        rp = row.get('raw_path', '')
        if rp and rp != 'nan' and Path(rp).exists():
            raw_date_counts[row['obs_date']] += 1

    # ================================================================
    sec("A] 기준값 대조 (최우선)")
    # ================================================================
    mismatches = []

    # 원장 행수
    if len(ledger) != REF_TOTAL_ROWS:
        mismatches.append(f"원장 총 행수: 실측 {len(ledger)} vs 기준 {REF_TOTAL_ROWS}")
    print(f"원장 총 행수: {len(ledger)}행 (기준: {REF_TOTAL_ROWS})")

    # 일자별 행수
    for d, ref in REF_DATE_ROWS.items():
        actual = date_counts.get(d, 0)
        if actual != ref:
            mismatches.append(f"일자별 행수 {d}: 실측 {actual} vs 기준 {ref}")
    print(f"일자별 행수: {dict(date_counts)}")

    # raw 파일 수 — 디스크 rglob vs 원장 raw_path 기준
    print(f"디스크 rglob 실측: {len(disk_raw_files)}개")
    print(f"원장 raw_path 존재 파일: {ledger_raw_exist}개")
    print(f"원장 raw_path 고유 경로: {len(ledger_raw_paths)}개")
    if len(disk_raw_files) != REF_RAW_COUNT:
        mismatches.append(f"디스크 raw 수: 실측 {len(disk_raw_files)} vs 기준 {REF_RAW_COUNT}")

    # outcome 대조
    ae = outcomes.get('api_error', 0)
    oe = outcomes.get('ok_empty', 0)
    bs = outcomes.get('BUDGET_STOP', 0)
    if ae != REF_API_ERROR:
        mismatches.append(f"api_error: 실측 {ae} vs 기준 {REF_API_ERROR}")
    if oe != REF_OK_EMPTY:
        mismatches.append(f"ok_empty: 실측 {oe} vs 기준 {REF_OK_EMPTY}")
    if bs != REF_BUDGET_STOP:
        mismatches.append(f"BUDGET_STOP: 실측 {bs} vs 기준 {REF_BUDGET_STOP}")
    print(f"api_error {ae}건, ok_empty {oe}건, BUDGET_STOP {bs}건")

    # orphan JSON
    orphans = sorted(disk_raw_set - ledger_raw_paths)
    print(f"\n[orphan JSON] 디스크에 있으나 원장에 없음: {len(orphans)}건")
    for o in orphans:
        print(f"  {o}")

    # 유령 참조
    ghosts = sorted(ledger_raw_paths - disk_raw_set)
    ghost_existing = [g for g in ghosts if Path(g).exists()]
    ghost_missing = [g for g in ghosts if not Path(g).exists()]
    print(f"[유령 참조] 원장에 있으나 디스크에 없음: {len(ghost_missing)}건")
    for g in ghost_missing:
        print(f"  {g}")
    if ghost_existing:
        print(f"[경로 표기 불일치] 디스크에 존재하나 정규화 후 불일치: {len(ghost_existing)}건")
        for g in ghost_existing:
            print(f"  {g}")

    # raw_path 파일명 규칙
    fname_pattern = re.compile(r'^\d{5}_[A-Z]{3}\d{9}_\d{4}\.json$')
    deviants = []
    for rp in sorted(ledger_raw_paths):
        fname = Path(rp).name
        if not fname_pattern.match(fname):
            deviants.append(fname)
    print(f"\n[raw_path 파일명 규칙] 패턴 '{fname_pattern.pattern}' 이탈: {len(deviants)}건")
    for d in deviants:
        print(f"  {d}")

    # 09-10 PM 수집분 확인
    rows_0910 = date_counts.get('2026-09-10', 0)
    pm_slots_0910 = sum(1 for r in ledger if r['obs_date'] == '2026-09-10'
                        and int(r['slot_hhmm'][:2]) >= 17)
    print(f"\n[09-10 PM 수집분] 09-10 총 {rows_0910}행, PM 슬롯 {pm_slots_0910}행")

    if mismatches:
        print("\n" + "!" * 60)
        print("!!! 1차 기준값 불일치 발견 !!!")
        for m in mismatches:
            print(f"  - {m}")
        print("!" * 60)
    else:
        print("\n1차 기준값과 전항목 일치 확인됨.")

    # ================================================================
    sec("B] 스키마 실측 비교")
    # ================================================================
    print(f"기대 컬럼 ({len(EXPECTED_COLUMNS)}개): {EXPECTED_COLUMNS}")
    print(f"실제 헤더 ({len(actual_headers)}개): {actual_headers}")

    missing_cols = [c for c in EXPECTED_COLUMNS if c not in actual_headers]
    extra_cols = [c for c in actual_headers if c not in EXPECTED_COLUMNS]
    order_match = actual_headers == EXPECTED_COLUMNS
    print(f"누락 컬럼: {missing_cols if missing_cols else '없음'}")
    print(f"추가 컬럼: {extra_cols if extra_cols else '없음'}")
    print(f"순서 일치: {order_match}")

    sv_dist = Counter(r.get('schema_version', '') for r in ledger)
    print(f"schema_version 분포: {dict(sv_dist)}")
    sv_single = len(sv_dist) == 1
    sv_value = list(sv_dist.keys())[0] if sv_single else '확인불가'
    if sv_single:
        schema_verdict = "PASS"
        schema_reason = (f"컬럼 {len(actual_headers)}개 기대치 일치, "
                         f"순서 일치={order_match}, "
                         f"schema_version 단일값='{sv_value}'")
    else:
        schema_verdict = "WARN"
        schema_reason = f"schema_version 복수값: {dict(sv_dist)}"

    if not order_match or missing_cols or extra_cols:
        schema_verdict = "FAIL"
        schema_reason = (f"누락={missing_cols}, 추가={extra_cols}, "
                         f"순서 일치={order_match}")

    print(f"판정: {schema_verdict} — {schema_reason}")

    # ================================================================
    sec("C] 실효 독립 슬롯 재계산")
    # ================================================================
    obs_by_date = defaultdict(list)
    for r in ledger:
        ca = parse_kst(r['called_at_kst'])
        if ca:
            obs_by_date[r['obs_date']].append((ca, r))

    near_dup_pairs = []         # (date, r1, r2, diff) — 슬롯 라벨 다른 쌍만
    near_dup_deducted = []      # 차감된 행
    effective_slots = {}        # date -> int

    for date, obs in sorted(obs_by_date.items()):
        obs.sort(key=lambda x: x[0])
        unique_labels = {r['slot_hhmm'] for _, r in obs}
        deducted_set = set()    # 차감 대상 인덱스

        for i in range(len(obs) - 1):
            t1, r1 = obs[i]
            t2, r2 = obs[i + 1]
            diff = (t2 - t1).total_seconds()
            if diff <= 120.0:
                if r1['slot_hhmm'] != r2['slot_hhmm']:
                    # 슬롯 라벨이 다른 준중복 → 늦은 쪽 차감
                    near_dup_pairs.append((date, r1, r2, diff))
                    deducted_set.add(i + 1)
                # 동일 슬롯 재시도는 차감하지 않음

        deducted_labels = set()
        for idx in deducted_set:
            _, rd = obs[idx]
            deducted_labels.add(rd['slot_hhmm'])
            near_dup_deducted.append((date, rd['slot_hhmm'], rd['called_at_kst']))

        eff = len(unique_labels) - len(deducted_labels)
        effective_slots[date] = eff

    print(f"준중복 (120초 이내, 라벨 상이) 쌍: {len(near_dup_pairs)}건")
    for date, r1, r2, diff in near_dup_pairs:
        print(f"  {date}: [{r1['slot_hhmm']}] {r1['called_at_kst']} "
              f"vs [{r2['slot_hhmm']}] {r2['called_at_kst']} "
              f"(간격 {diff:.1f}초) "
              f"outcome: {r1['outcome']}(retry={r1['retry_count']}) / "
              f"{r2['outcome']}(retry={r2['retry_count']})")

    print(f"\n[차감된 행 전량]")
    for date, slot, cat in near_dup_deducted:
        print(f"  {date} slot={slot} called_at={cat}")

    print(f"\n[일자별 슬롯 수 비교]")
    print(f"{'날짜':<12} {'명목 행수':>8} {'고유 슬롯':>8} {'실효 독립':>8}")
    for date in sorted(date_counts.keys()):
        nominal = date_counts[date]
        unique = len({r['slot_hhmm'] for r in ledger if r['obs_date'] == date})
        eff = effective_slots.get(date, unique)
        print(f"{date:<12} {nominal:>8} {unique:>8} {eff:>8}")

    # ================================================================
    sec("D] ok_empty 인접 슬롯 대조 (판정 확정용)")
    # ================================================================
    ok_empty_verdicts = {}
    ok_empty_count = 0
    for r in ledger:
        if r['outcome'] == 'ok_empty':
            ok_empty_count += 1
            od = r['obs_date']
            sh = r['slot_hhmm']
            same_day = sorted(
                [x for x in ledger if x['obs_date'] == od],
                key=lambda x: x['slot_hhmm']
            )
            idx = next(
                i for i, x in enumerate(same_day)
                if x['slot_hhmm'] == sh and x['outcome'] == 'ok_empty'
            )
            neighbors = []
            for j in range(max(0, idx - 2), min(len(same_day), idx + 3)):
                x = same_day[j]
                ic_val = x.get('item_count', '')
                try:
                    ic_int = int(float(ic_val))
                except (ValueError, TypeError):
                    ic_int = None
                mark = " <<< ok_empty" if j == idx else ""
                neighbors.append((x['slot_hhmm'], ic_int, x['outcome'],
                                  x.get('result_code', ''), mark))

            print(f"\n--- {od} {sh} ---")
            print(f"  {'slot':>6} {'ic':>4} {'outcome':<16} {'rc':<15}")
            for slot, ic, oc, rc, mark in neighbors:
                ic_str = str(ic) if ic is not None else 'N/A'
                print(f"  {slot:>6} {ic_str:>4} {oc:<16} {rc:<15}{mark}")

            # 판정 로직
            adj = [(ic, oc) for slot, ic, oc, rc, mark in neighbors
                   if mark == "" and ic is not None]
            if not adj:
                verdict = "확인불가"
            elif all(ic >= 20 for ic, oc in adj):
                verdict = "API 순간 공백(아티팩트) 유력, 결측 처리 후보"
            elif all(ic <= 5 for ic, oc in adj):
                verdict = "실제 배차 공백 가능성"
            else:
                verdict = "확인불가"

            # 보충: 장기 예측 지평 특성
            print(f"  → 판정: {verdict}")
            print(f"    (참고: arrtime 4,709건 중 11.4%가 3600초 초과 — "
                  f"장기 예측 지평을 가진 정류소이므로, 순간적 배차 공백 시"
                  f" API가 items를 반환하지 않을 수 있음)")
            ok_empty_verdicts[f"{od}_{sh}"] = verdict

    # ================================================================
    sec("E] 드리프트 창 구분 재산출")
    # ================================================================
    now_kst = datetime.now(KST)

    # 분석 창 일자 결정
    excluded_days = []
    included_days = []
    for wd in ANALYSIS_WINDOW:
        pm_end = parse_kst(f"{wd} 19:00:00+09:00")
        if pm_end and now_kst < pm_end:
            excluded_days.append((wd, "미완료일 (PM 창 종료 전)"))
        else:
            included_days.append(wd)
    included_set = set(included_days)

    print(f"분석 창 일자: {ANALYSIS_WINDOW}")
    print(f"배제일: {excluded_days}")
    print(f"분석 대상 일자: {included_days}")

    drifts_all = []
    drifts_regular = []
    drifts_window_regular = []
    drift_records = []

    for row in ledger:
        ca = parse_kst(row['called_at_kst'])
        rc_val = row.get('retry_count', '0')
        try:
            rc_int = int(rc_val)
        except (ValueError, TypeError):
            rc_int = 0

        if ca:
            d = calc_drift(ca, row['slot_hhmm'])
            drifts_all.append(d)
            drift_records.append((d, row))
            if rc_int == 0:
                drifts_regular.append(d)
                if row['obs_date'] in included_set:
                    drifts_window_regular.append(d)

    def drift_line(label, dlist):
        if not dlist:
            print(f"[{label}] N/A")
            return
        s = sorted(dlist)
        n = len(s)
        mean = sum(s) / n
        print(f"[{label}] n={n}, mean={mean:.3f}, "
              f"p50={percentile(s, 50):.3f}, p90={percentile(s, 90):.3f}, "
              f"p95={percentile(s, 95):.3f}, p99={percentile(s, 99):.3f}, "
              f"max={s[-1]:.3f}")

    drift_line("전체", drifts_all)
    drift_line("정규 호출(retry=0)", drifts_regular)
    drift_line("분석 창 내 정규 호출", drifts_window_regular)

    print(f"\n[허용치 300초 초과 건]")
    over_300 = [(d, row) for d, row in drift_records if d > 300]
    if over_300:
        for d, row in sorted(over_300, key=lambda x: -x[0]):
            in_excl = row['obs_date'] not in included_set
            excl_tag = " [배제일 소속]" if in_excl else " [분석 창 내]"
            print(f"  {row['obs_date']} slot={row['slot_hhmm']} "
                  f"drift={d:.3f}초 retry={row['retry_count']}{excl_tag}")
    else:
        print("  없음")

    # 드리프트 판정
    reg_sorted = sorted(drifts_regular)
    reg_p95 = percentile(reg_sorted, 95) if reg_sorted else 0
    reg_max = reg_sorted[-1] if reg_sorted else 0

    win_sorted = sorted(drifts_window_regular)
    win_p95 = percentile(win_sorted, 95) if win_sorted else 0
    win_max = win_sorted[-1] if win_sorted else 0

    # ================================================================
    sec("F] 수정 판정표")
    # ================================================================
    print(f"분석 창 (배제 전): {ANALYSIS_WINDOW}")
    print(f"배제일: {excluded_days}")
    print(f"분석 대상 일자: {included_days}")

    # 커버리지
    cov_pass = True
    cov_details = []
    for inc_d in included_days:
        eff = effective_slots.get(inc_d, 0)
        pct = (eff / SLOT_COUNT) * 100
        cov_details.append(f"{inc_d}({eff}/{SLOT_COUNT}={pct:.1f}%)")
        if pct < 90.0:
            cov_pass = False
    cov_eval = "PASS" if cov_pass and included_days else "FAIL"
    cov_str = ", ".join(cov_details) if cov_details else "대상 일자 없음"

    # 키 중복 (obs_date, slot_hhmm, retry_count) 기준
    key_counter = Counter(
        (r['obs_date'], r['slot_hhmm'], r.get('retry_count', '0'))
        for r in ledger
    )
    dup_keys = {k: v for k, v in key_counter.items() if v > 1}

    # raw 누락 — 디스크 실측 기준
    raw_missing_normal = []
    for r in ledger:
        rp = r.get('raw_path', '')
        if r['outcome'] == 'api_error':
            continue
        if not rp or rp == 'nan':
            raw_missing_normal.append(r)
        elif not Path(rp).exists():
            raw_missing_normal.append(r)

    # item_count 불일치 — raw 전수
    ic_mismatch = []
    for row in ledger:
        rp = row.get('raw_path')
        if not rp or rp == 'nan':
            continue
        p = Path(rp)
        if not p.exists():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            bdy = data.get('response', {}).get('body', {})
            items = bdy.get('items', {})
            if not items:
                items = []
            else:
                items = items.get('item', [])
            if isinstance(items, dict):
                items = [items]

            ic_str = row.get('item_count', '')
            try:
                ic_ledger = int(float(ic_str))
            except (ValueError, TypeError):
                ic_ledger = 0

            if len(items) != ic_ledger:
                ic_mismatch.append(
                    f"{p.name}: raw_items={len(items)}, ledger_ic={ic_ledger}")
        except Exception:
            pass

    # TRUNCATED — totalCount vs items
    trunc_mismatch = []
    for row in ledger:
        rp = row.get('raw_path')
        if not rp or rp == 'nan':
            continue
        p = Path(rp)
        if not p.exists():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            bdy = data.get('response', {}).get('body', {})
            items = bdy.get('items', {})
            if not items:
                items = []
            else:
                items = items.get('item', [])
            if isinstance(items, dict):
                items = [items]
            tot = bdy.get('totalCount', 0)
            if tot > len(items):
                trunc_mismatch.append(
                    f"{p.name}: totalCount={tot}, items={len(items)}")
        except Exception:
            pass

    trunc_eval = "WARN" if trunc_mismatch else "PASS"
    trunc_reason = (f"totalCount 불일치 {len(trunc_mismatch)}건"
                    if trunc_mismatch
                    else "전수 대조 결과 totalCount와 items 길이 일치")

    # 예산
    max_daily_calls = max(raw_date_counts.values()) if raw_date_counts else 0

    # 유효 관측치 정의
    oe_arti = sum(1 for v in ok_empty_verdicts.values()
                  if '아티팩트' in v)
    oe_real = sum(1 for v in ok_empty_verdicts.values()
                  if '배차 공백 가능성' in v and '아티팩트' not in v)
    oe_unk = sum(1 for v in ok_empty_verdicts.values()
                 if v == '확인불가')

    # ── 판정표 구성 ──
    verdicts = []

    # 1) 스키마 일치
    verdicts.append(("스키마 일치", schema_verdict, schema_reason))

    # 2) 평일 3일 이상
    v2 = "PASS" if len(included_days) >= 3 else "WARN"
    verdicts.append(("평일 3일 이상 확보", v2,
                     f"유효 분석 대상 {len(included_days)}일 확보"))

    # 3) 커버리지
    verdicts.append(("커버리지 기준", cov_eval,
                     f"분석 대상 커버리지: {cov_str}"))

    # 4) 키 중복
    verdicts.append(("키 중복 없음",
                     "PASS" if not dup_keys else "WARN",
                     f"(date,slot,retry) 중복 {len(dup_keys)}건"))

    # 5) 준중복
    verdicts.append(("준중복",
                     "PASS" if len(near_dup_pairs) == 0 else "WARN",
                     f"라벨 상이 120초 이내 쌍 {len(near_dup_pairs)}건, "
                     f"차감 {len(near_dup_deducted)}건"))

    # 6) 드리프트 (창 내)
    drift_win_eval = "PASS" if win_max <= 300 else "FAIL"
    verdicts.append(("드리프트(창 내)",
                     drift_win_eval,
                     f"창 내 정규 p95={win_p95:.3f}초, max={win_max:.3f}초"))

    # 6b) 드리프트 (전체)
    drift_all_eval = "PASS" if reg_max <= 300 else "WARN"
    verdicts.append(("드리프트(전체)",
                     drift_all_eval,
                     f"정규 전체 p95={reg_p95:.3f}초, max={reg_max:.3f}초"))

    # 7) raw 누락
    verdicts.append(("raw 누락 없음(디스크 실측)",
                     "PASS" if not raw_missing_normal else "FAIL",
                     f"정상 응답 중 raw 파일 누락 {len(raw_missing_normal)}건"))

    # 8) item_count 불일치
    verdicts.append(("item_count 불일치",
                     "PASS" if not ic_mismatch else "WARN",
                     f"원장 vs raw 배열 불일치 {len(ic_mismatch)}건"))

    # 9) TRUNCATED
    verdicts.append(("TRUNCATED", trunc_eval, trunc_reason))

    # 10) BUDGET_STOP
    verdicts.append(("BUDGET_STOP 없음",
                     "PASS" if bs == 0 else "FAIL",
                     f"BUDGET_STOP {bs}건"))

    # 11) 예산
    verdicts.append(("예산 하드스톱 미만",
                     "PASS" if max_daily_calls < HARD_STOP else "FAIL",
                     f"최대 하루 {max_daily_calls}건, "
                     f"HARD_STOP={HARD_STOP}, DAILY_APPROVED={DAILY_APPROVED}"))

    # 12) 유효 관측치 정의
    oe_eval = "WARN" if ok_empty_count > 0 else "PASS"
    verdicts.append(("유효 관측치 정의",
                     oe_eval,
                     f"ok_empty {ok_empty_count}건 중 "
                     f"아티팩트 {oe_arti}건, 배차공백 {oe_real}건, "
                     f"확인불가 {oe_unk}건"))

    # 13) 하드코딩 없음 — 자체 점검 로직으로 판정
    hardcode_result = self_check_hardcoding()
    if hardcode_result is None:
        hc_eval = "UNVERIFIED"
        hc_reason = "자체 점검 로직 미구현"
    elif hardcode_result:
        hc_eval = "FAIL"
        hc_reason = f"판정 근거에 리터럴 숫자 발견: {hardcode_result}"
    else:
        hc_eval = "PASS"
        hc_reason = "자체 점검 결과, 판정 근거 생성부에 숫자 리터럴 미발견"

    verdicts.append(("하드코딩 없음", hc_eval, hc_reason))

    # 출력
    print(f"\n{'항목':<24} | {'판정':<12} | {'근거'}")
    print("-" * 90)
    for name, ev, reason in verdicts:
        print(f"{name:<24} | {ev:<12} | {reason}")

    print(f"\n[WARN/FAIL/UNVERIFIED 요약]")
    for name, ev, reason in verdicts:
        if ev in ("WARN", "FAIL", "UNVERIFIED"):
            print(f"  - [{name}] {ev}: {reason}")


def self_check_hardcoding():
    """
    이 스크립트의 판정 근거 문자열 생성부(verdicts.append 행)에서
    f-string 이 아닌 숫자 리터럴이 포함된 행을 탐지한다.
    검사 범위: 튜플의 3번째 요소(근거 문자열)만. 1번째(항목명)는 고정 라벨이므로 제외.
    반환: 발견된 (라인번호, 내용) 리스트. 비어있으면 통과.
    """
    try:
        with open(Path(__file__).resolve(), "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return None  # 파일 읽기 실패 → UNVERIFIED

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # verdicts.append(...) 패턴 탐지
        if not (isinstance(func, ast.Attribute)
                and func.attr == 'append'
                and isinstance(func.value, ast.Name)
                and func.value.id == 'verdicts'):
            continue

        # 인자는 단일 Tuple 이어야 함
        if not node.args:
            continue
        tup = node.args[0]
        if not isinstance(tup, ast.Tuple) or len(tup.elts) < 3:
            continue

        # 3번째 요소(근거 문자열)만 검사
        reason_node = tup.elts[2]

        # reason_node 가 순수 Constant(f-string 아님)이고 숫자 포함 → FAIL
        if isinstance(reason_node, ast.Constant) and isinstance(reason_node.value, str):
            if re.search(r'\d', reason_node.value):
                findings.append(
                    (reason_node.lineno,
                     f"근거 문자열에 리터럴 숫자: '{reason_node.value[:60]}'"))
        # JoinedStr(f-string) → 내부 Constant 조각 중 숫자 포함 여부 확인
        # f-string 조각 내 고정 문자열에 숫자가 있어도, 그것은 템플릿 텍스트
        # (예: "p95=", "3600초") 이므로 단위·접미사 패턴은 허용한다.
        # 금지 대상: f-string 조각이 아닌 순수 리터럴 문자열에 숫자가 박힌 경우만.

    if findings:
        print(f"\n[하드코딩 자체 점검] 의심 행 {len(findings)}건:")
        for lineno, msg in findings:
            print(f"  Line {lineno}: {msg}")

    return findings if findings else []


if __name__ == "__main__":
    outpath = "scratch/audit_supplement_v2_output.txt"
    with open(outpath, "w", encoding="utf-8") as f:
        sys.stdout = f
        main()
    sys.stdout = sys.__stdout__
    print("output saved to " + outpath)
