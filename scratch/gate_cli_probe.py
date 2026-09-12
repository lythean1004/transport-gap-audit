from pathlib import Path
import re, inspect

SRC = Path("src/verify/stop_gate.py")
text = SRC.read_text(encoding="utf-8")
lines = text.splitlines()
print("[0] path:", SRC, "lines:", len(lines))

print("\n[1] ---- add_argument / default ----")
for i, l in enumerate(lines, 1):
    if "add_argument" in l or re.search(r"\bdefault\s*=", l):
        print(f"{i:5d}: {l}")

print("\n[2] ---- 경로/데이터 관련 라인 ----")
pat = re.compile(r"complex|cluster|parquet|tago|stops|read_csv|read_parquet"
                 r"|Path\(|\.csv|\.json|gpslati|gpslong", re.I)
for i, l in enumerate(lines, 1):
    if pat.search(l):
        print(f"{i:5d}: {l}")

print("\n[3] ---- 대문자 상수 정의 ----")
for i, l in enumerate(lines, 1):
    if re.match(r"^[A-Z][A-Z0-9_]{2,}\s*=", l):
        print(f"{i:5d}: {l}")

print("\n[4] ---- def 목록 ----")
for i, l in enumerate(lines, 1):
    if re.match(r"^\s*def\s", l):
        print(f"{i:5d}: {l.strip()}")

print("\n[5] ---- evaluate 관련 함수 원문 ----")
import importlib
m = importlib.import_module("src.verify.stop_gate")
for name in dir(m):
    obj = getattr(m, name)
    if inspect.isfunction(obj) and getattr(obj, "__module__", "") == m.__name__:
        if re.search(r"evaluate|main|cli|parser|cmd", name, re.I):
            print(f"\n===== def {name} =====")
            try:
                print(inspect.getsource(obj))
            except Exception as e:
                print("SOURCE_FAIL", type(e).__name__, e)

print("\n[6] GATE_CODE_VERSION =", getattr(m, "GATE_CODE_VERSION", "없음"))