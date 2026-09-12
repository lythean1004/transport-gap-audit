import pandas as pd
from datetime import datetime

df = pd.read_csv("evidence/arrival_ledger.csv")
df["called_dt"] = pd.to_datetime(df["called_at_kst"])
df = df.sort_values("called_dt").reset_index(drop=True)

df["diff_min"] = df["called_dt"].diff().dt.total_seconds() / 60.0

print("=== INTERVAL SUMMARY (minutes) ===")
print(df["diff_min"].describe())

print("\n=== INTERVAL DISTRIBUTION (Histogram bins) ===")
bins = [0, 6, 15, 60, 480, 1440, 10000]
labels = ["0~6분 (정규 5분대)", "6~15분 (단기 누락)", "15~60분 (중기 누락)", "1~8시간 (주간 비수집)", "8~24시간 (야간 비수집)", ">24시간 (주말 공백)"]
cuts = pd.cut(df["diff_min"].dropna(), bins=bins, labels=labels)
print(cuts.value_counts().sort_index())

print("\n=== GAPS > 6 minutes (누락/휴지 구간 시작~종료) ===")
large_gaps = df[df["diff_min"] > 6.0]
for idx, r in large_gaps.iterrows():
    prev_r = df.iloc[idx - 1]
    gap_dur = r["diff_min"]
    p_dt = prev_r["called_at_kst"][:19]
    c_dt = r["called_at_kst"][:19]
    print(f"- 누락 {gap_dur:>6.1f}분: {p_dt} ~ {c_dt} (슬롯: {prev_r['obs_date']} {prev_r['slot_hhmm']} -> {r['obs_date']} {r['slot_hhmm']})")