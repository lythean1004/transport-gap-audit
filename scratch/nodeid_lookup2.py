from pathlib import Path
import pandas as pd

TARGET = "GGB222001318"
PQ = Path("data/staged/tago_stops_full.parquet")

print("path:", PQ, "exists:", PQ.exists(), "size:", PQ.stat().st_size if PQ.exists() else None)
if not PQ.exists():
    raise SystemExit("파일 없음. 이 줄까지 그대로 보고하세요.")

try:
    df = pd.read_parquet(PQ)
except Exception as e:
    raise SystemExit(f"READ_FAIL {type(e).__name__}: {e}")

print("rows:", len(df))
print("columns:", list(df.columns))

if "nodeid" not in df.columns:
    raise SystemExit("nodeid 컬럼 없음. 위 columns 목록을 그대로 보고하세요.")

hit = df[df["nodeid"].astype(str).str.strip() == TARGET]
print("matched_rows:", len(hit))

if len(hit) == 0:
    print("대상 없음. GGB2220013 접두어 목록:")
    near = df[df["nodeid"].astype(str).str.startswith("GGB2220013")]
    show = [c for c in ["nodeid", "nodenm", "gpslati", "gpslong", "citycode"] if c in df.columns]
    print(near[show].to_string(index=False))
    raise SystemExit(0)

r = hit.iloc[0]
print("\n--- 핵심 3개 ---")
print("nodenm  =", repr(r["nodenm"]))
print("gpslati =", repr(r["gpslati"]))
print("gpslong =", repr(r["gpslong"]))

print("\n--- 이 행 전체 컬럼 원문 ---")
for c in df.columns:
    print(f"  {c} = {r[c]!r}")