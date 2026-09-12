import pandas as pd
from pathlib import Path

csv_path = Path("evidence/stop_registry.csv")

# 1. 기존 파일 읽기
df = pd.read_csv(csv_path, dtype=str)
print("=== [1] 변경 전 파일 내용 ===")
with open(csv_path, "r", encoding="utf-8") as f:
    print(f.read().strip())

old_notes = df.at[0, "notes"]
new_notes = "pilot smoke 2026-09-03 12:30 KST / evidence expires ~2026-10-03 / coord from OSM node ref=23927 (ODbL) + kakao ID crosscheck"

# 2. notes 값만 교체
df.at[0, "notes"] = new_notes

# 3. 저장 (UTF-8, BOM 없음)
df.to_csv(csv_path, index=False, encoding="utf-8")

# 4. 저장 후 파일 내용 확인
print("\n=== [2] 변경 후 파일 내용 전문 ===")
with open(csv_path, "r", encoding="utf-8") as f:
    print(f.read().strip())

# 5. 각 컬럼별 변경 전후 비교
print("\n=== [3] 컬럼별 Before / After 검증 ===")
df_after = pd.read_csv(csv_path, dtype=str)
for col in df_after.columns:
    if col == "notes":
        print(f"  {col:25s} : CHANGED\n    before = {old_notes!r}\n    after  = {df_after.at[0, col]!r}")
    else:
        print(f"  {col:25s} : UNCHANGED (value = {df_after.at[0, col]!r})")