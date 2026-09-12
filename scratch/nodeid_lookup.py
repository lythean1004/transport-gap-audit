from pathlib import Path
import pandas as pd

TARGET = "GGB222001318"

# 1) 파일 찾기
cands = [p for p in Path(".").rglob("*tago_stops*") if ".git" not in p.parts]
print("found_files:", [str(p) for p in cands])
if not cands:
    raise SystemExit("tago_stops 파일 없음. 이 줄까지 그대로 보고하세요.")

pq = cands[0]
print("using:", pq)

# 2) 읽기
try:
    df = pd.read_parquet(pq)
except Exception as e:
    raise SystemExit(f"READ_FAIL {type(e).__name__}: {e}")

print("rows:", len(df))
print("columns:", list(df.columns))

# 3) 대상 행
hit = df[df["nodeid"].astype(str).str.strip() == TARGET]
print("matched_rows:", len(hit))

if len(hit) == 0:
    print("대상 nodeid 없음. 아래는 GGB2220013 으로 시작하는 행 목록:")
    near = df[df["nodeid"].astype(str).str.startswith("GGB2220013")]
    print(near[["nodeid", "nodenm", "gpslati", "gpslong"]].to_string(index=False))
    raise SystemExit(0)

# 4) 세 값 + 전체 컬럼 원문
r = hit.iloc[0]
print("\n--- 핵심 3개 ---")
print("nodenm  =", repr(r["nodenm"]))
print("gpslati =", repr(r["gpslati"]))
print("gpslong =", repr(r["gpslong"]))

print("\n--- 이 행 전체 컬럼 원문 ---")
for c in df.columns:
    print(f"  {c} = {r[c]!r}")