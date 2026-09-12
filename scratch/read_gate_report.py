from pathlib import Path
import json, pandas as pd

R = Path("exports/stop_gate_report.csv")
M = Path("exports/stop_gate_report.meta.json")

print("report exists:", R.exists(), "size:", R.stat().st_size if R.exists() else None)
print("meta   exists:", M.exists(), "size:", M.stat().st_size if M.exists() else None)

if R.exists() and R.stat().st_size > 2:
    print("\n---- report raw ----")
    print(R.read_text(encoding="utf-8"))
    d = pd.read_csv(R)
    print("\nrows:", len(d), "cols:", list(d.columns))
    for _, r in d.iterrows():
        print("  ---- row ----")
        for c in d.columns:
            print(f"    {c} = {r[c]!r}")

if M.exists():
    print("\n---- meta raw ----")
    print(M.read_text(encoding="utf-8"))