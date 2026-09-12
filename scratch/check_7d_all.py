from pathlib import Path
from datetime import datetime, timedelta, timezone
import re, importlib, inspect, traceback

KST = timezone(timedelta(hours=9))
def sec(t): print("\n" + "=" * 60 + f"\n{t}\n" + "=" * 60)
def ok(c): return "OK" if c else "FAIL"

FILES = {
    "7D-1": "src/collectors/arrival_slots.py",
    "7D-2": "src/collectors/arrival_ledger.py",
    "7D-3": "src/collectors/arrival_budget.py",
    "7D-4": "src/collectors/arrival_snapshot.py",
}
sec("[0] 파일 존재")
present = {}
for k, v in FILES.items():
    p = Path(v)
    present[k] = p.exists()
    print(f"{k} {v} exists={p.exists()} size={p.stat().st_size if p.exists() else None}")

# ---------------- 7D-1 ----------------
sec("[1] arrival_slots")
try:
    S = importlib.import_module("src.collectors.arrival_slots")
    L = S.build_slot_labels()
    print("labels:", len(L), ok(len(L) == 48))
    print("no_end_labels:", ok("0900" not in L and "1900" not in L))
    cases = [("07:00:00", "0700"), ("07:03:59", "0700"), ("08:59:59", "0855"),
             ("09:00:00", None), ("12:00:00", None), ("18:59:59", "1855"),
             ("19:00:00", None)]
    bad = 0
    for t, exp in cases:
        got = S.snap_to_slot(datetime.fromisoformat(f"2026-09-10T{t}+09:00"))
        if got != exp:
            bad += 1
            print(f"  MISMATCH {t}: got={got} expected={exp}")
    print("snap_cases:", ok(bad == 0))
    try:
        S.snap_to_slot(datetime(2026, 9, 10, 7, 0))
        print("naive_raises: FAIL")
    except ValueError:
        print("naive_raises: OK")
    # UTC 입력도 KST로 환산되는지
    u = datetime(2026, 9, 9, 22, 0, tzinfo=timezone.utc)  # = 07:00 KST
    print("utc_input ->", S.snap_to_slot(u), ok(S.snap_to_slot(u) == "0700"))
except Exception:
    traceback.print_exc()

# ---------------- 7D-2 ----------------
sec("[2] arrival_ledger")
try:
    G = importlib.import_module("src.collectors.arrival_ledger")
    src2 = Path(FILES["7D-2"]).read_text(encoding="utf-8")
    body = inspect.getsource(G.load_ledger)
    silent = re.search(r"except\s+Exception\s*:\s*\n\s*return\s*\{\s*\}", body)
    print("load_ledger 조용한 except 제거:", ok(silent is None))
    if silent:
        print("  >>> 아직 남아 있음. 원장 손상 시 전량 재호출 위험")
    print("컬럼 순서:", list(G.LEDGER_COLUMNS))
    exp_cols = ["obs_date","slot_hhmm","citycode","nodeid","outcome","retry_count",
                "called_at_kst","http_status","result_code","result_msg",
                "item_count","raw_path","schema_version"]
    print("컬럼 일치:", ok(list(G.LEDGER_COLUMNS) == exp_cols))
    k = ("2026-09-10", "0700", "31130", "GGB222001318")
    def row(o, r): return {"obs_date":k[0],"slot_hhmm":k[1],"citycode":k[2],
                           "nodeid":k[3],"outcome":o,"retry_count":str(r),
                           "called_at_kst":"2026-09-10T07:01:00+09:00"}
    checks = [({}, k, (True,"NEW")),
              ({k: row("ok_with_items",0)}, k, (False,"DONE")),
              ({k: row("ok_empty",0)}, k, (False,"DONE")),
              ({k: row("api_error",0)}, k, (True,"RETRY_1")),
              ({k: row("api_error",1)}, k, (True,"RETRY_2")),
              ({k: row("api_error",2)}, k, (False,"RETRY_EXHAUSTED")),
              ({k: row("weird",0)}, k, (False,"UNKNOWN_OUTCOME"))]
    bad = 0
    for led, key, exp in checks:
        got = G.should_call(led, key)
        if got != exp:
            bad += 1
            print(f"  MISMATCH {led[key]['outcome'] if led else 'empty'}: {got} != {exp}")
    print("should_call 전이:", ok(bad == 0))
    b = G.make_budget_stop_row("2026-09-10","0715","2026-09-10T07:15:00+09:00","x")
    print("BUDGET_STOP citycode/nodeid 공란:", ok(b["citycode"]=="" and b["nodeid"]==""))
except Exception:
    traceback.print_exc()

# ---------------- 7D-3 ----------------
sec("[3] arrival_budget")
try:
    B = importlib.import_module("src.collectors.arrival_budget")
    print("DAILY_APPROVED/WARN/STOP:", B.DAILY_APPROVED, B.WARN_AT, B.HARD_STOP,
          ok((B.DAILY_APPROVED, B.WARN_AT, B.HARD_STOP) == (10000, 4000, 5000)))
    p1 = B.preflight(stops=1)
    print("stops=1:", p1["calls_per_day"], p1["total"], p1["allowed"],
          ok((p1["calls_per_day"], p1["total"], p1["allowed"]) == (48, 144, True)))
    print("stops=104 allowed:", B.preflight(stops=104)["allowed"], ok(B.preflight(stops=104)["allowed"]))
    print("stops=105 allowed:", B.preflight(stops=105)["allowed"], ok(not B.preflight(stops=105)["allowed"]))
    g = B.BudgetGuard()
    for _ in range(3999): g.record_attempt()
    r = [g.check()]
    g.record_attempt(); r.append(g.check())
    for _ in range(999): g.record_attempt()
    r.append(g.check()); r.append(g.should_stop())
    g.record_attempt(); r.append(g.check()); r.append(g.should_stop())
    print("전이 3999/4000/4999/5000:", r,
          ok(r == ["OK","WARN","WARN",False,"STOP",True]))
except Exception:
    traceback.print_exc()

# ---------------- 7D-4 ----------------
sec("[4] arrival_snapshot (정적 검사)")
p4 = Path(FILES["7D-4"])
if not p4.exists():
    print("MISSING - 아직 미작성")
else:
    t = p4.read_text(encoding="utf-8")
    def has(pat, flags=0): return re.search(pat, t, flags) is not None
    print("모듈 재사용 import:")
    for mod in ["arrival_slots", "arrival_ledger", "arrival_budget"]:
        print(f"  {mod}:", ok(has(mod)))
    print("오퍼레이션명 getSttnAcctoArvlPrearngeInfoList:",
          ok(has("getSttnAcctoArvlPrearngeInfoList")))
    print("서비스키 env 사용:", ok(has(r"TAGO_SERVICE_KEY")))
    keyish = re.findall(r"['\"][0-9a-zA-Z%+/=]{40,}['\"]", t)
    print("하드코딩 키 의심 문자열:", len(keyish), ok(len(keyish) == 0))
    print("arrtime_sec 명명:", ok(has(r"arrtime_sec")))
    conv = re.findall(r"arrtime[^\n]*(?:/\s*60|//\s*60|round\(|minute)", t, re.I)
    print("분 변환 흔적:", conv if conv else "없음", ok(not conv))
    ded = re.findall(r"drop_duplicates|set\(\s*[^)]*routeid|unique\(\)", t, re.I)
    print("중복제거 흔적:", ded if ded else "없음", ok(not ded))
    print("item_seq 부여:", ok(has(r"item_seq")))
    print("예산 복원 로직:", ok(has(r"restored from ledger")))
    print("BUDGET_STOP 기록:", ok(has(r"make_budget_stop_row")))
    print("dry-run 인자:", ok(has(r"dry[-_]run")))

sec("[5] 산출물 미생성 확인 (dry-run 후에도 없어야 함)")
for q in ["evidence/arrival_ledger.csv", "evidence/arrival_raw"]:
    print(f"{q} exists:", Path(q).exists(), ok(not Path(q).exists()))
print("\nscratch 잔여물:", [str(x) for x in Path("scratch").glob("_ledger_test*")] or "없음")