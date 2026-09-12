import pandas as pd
from pathlib import Path

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)

TARGETS = ["A10022364", "A10024817", "A10025828", "A10027369"]

CG = Path("exports/complex_geocode.csv")
df = pd.read_csv(CG, dtype=str)

print("=== [1] 대상 4건 전체 컬럼 원문 ===")
sub = df[df["cluster_id"].isin(TARGETS)]
print("matched_rows:", len(sub), "/ expected 4")
for _, r in sub.iterrows():
    print("-" * 70)
    for c in df.columns:
        print(f"  {c} = {r[c]!r}")

print("\n=== [2] 하이픈 실측 (전체 274행) ===")
for col in ["addr_legal_raw", "addr_query", "refined_text"]:
    if col in df.columns:
        s = df[col].fillna("")
        print(f"{col}: endswith_hyphen={int(s.str.endswith('-').sum())}, "
              f"contains_hyphen={int(s.str.contains('-', regex=False).sum())}")

print("\n=== [3] 상태 컬럼 분포 (전체) ===")
for col in ["crs", "status", "qa_flag", "error_code", "needs_review",
            "override_decision", "representative_method", "coord_source"]:
    if col in df.columns:
        print(f"--- {col} ---")
        print(df[col].fillna("<NA>").value_counts(dropna=False).to_string())

print("\n=== [4] centroid_spread_m 300m 초과 건수 ===")
sp = pd.to_numeric(df["centroid_spread_m"], errors="coerce")
print("notna:", int(sp.notna().sum()), "| over_300m:", int((sp > 300).sum()))
print(df.loc[sp > 300, ["cluster_id", "centroid_spread_m"]].to_string(index=False))

print("\n=== [5] 5A 산출물에서 본번/부번 원본 찾기 ===")
for p in sorted(Path("exports").glob("*.csv")):
    try:
        cols = list(pd.read_csv(p, dtype=str, nrows=0).columns)
    except Exception as e:
        print(f"{p.name}: READ_FAIL {type(e).__name__}: {e}")
        continue
    hit = [c for c in cols
           if any(k in c for k in ("본번", "부번", "지번", "bonbun", "bubun", "jibun", "san"))]
    print(f"{p.name}: rows_cols={len(cols)} jibun_cols={hit}")

PLAN = Path("exports/complex_geocoding_plan.csv")
print("\n=== [6] complex_geocoding_plan.csv 대상 4건 ===")
print("exists:", PLAN.exists())
if PLAN.exists():
    pdf = pd.read_csv(PLAN, dtype=str)
    print("all_columns:", list(pdf.columns))
    psub = pdf[pdf["cluster_id"].isin(TARGETS)] if "cluster_id" in pdf.columns else pdf.head(0)
    print("matched_rows:", len(psub))
    for _, r in psub.iterrows():
        print("-" * 70)
        for c in pdf.columns:
            print(f"  {c} = {r[c]!r}")