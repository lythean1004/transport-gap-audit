from pathlib import Path
import pandas as pd

R = Path("evidence/stop_registry.csv")
L = Path("evidence/promotion_log.csv")
B = Path("scratch/stop_registry.pre_promote.bak")

print("---- registry raw ----")
print(R.read_text(encoding="utf-8"))

d = pd.read_csv(R)
b = pd.read_csv(B)
print("rows:", len(d), "cols:", len(d.columns))
r, br = d.iloc[0], b.iloc[0]

print("\n---- 변경 컬럼 대조 (백업 대비) ----")
for c in d.columns:
    if str(r[c]) != str(br[c]):
        print(f"  CHANGED {c}: {br[c]!r} -> {r[c]!r}")
print("  (위에 review_status 외 항목이 있으면 문제)")

for c in ["review_status", "stop_lat", "stop_lon", "direction_label",
          "coord_verify_method", "verified_by", "verified_at", "notes"]:
    print(f"{c} = {r[c]!r}")

print("\n---- promotion_log ----")
print("exists:", L.exists())
if L.exists():
    print(L.read_text(encoding="utf-8"))