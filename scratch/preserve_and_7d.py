from pathlib import Path
import shutil, importlib

D = Path("evidence/gate_pass/20260903_A10022364")
D.mkdir(parents=True, exist_ok=True)
for s in ["exports/stop_gate_report.csv", "exports/stop_gate_report.meta.json"]:
    t = D / Path(s).name
    shutil.copy2(s, t)
    print("copied:", t, "size:", t.stat().st_size)

print("\n---- 7D 전제조건 ----")
m = importlib.import_module("src.verify.stop_gate")
rc = m.check_7d_preconditions()
print("check_7d_preconditions return:", rc)

print("\n---- evidence 산출물 목록 ----")
for p in sorted(Path("evidence").rglob("*")):
    if p.is_file():
        print(f"  {p} ({p.stat().st_size} bytes)")