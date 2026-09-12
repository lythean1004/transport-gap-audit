import pandas as pd
from pathlib import Path

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 300)
pd.set_option("display.max_rows", 300)

df = pd.read_csv("exports/complex_geocode.csv", dtype=str)
raw = df["addr_legal_raw"].fillna("")
q = df["addr_query"].fillna("")

print("=== [1] 행 단위 하이픈 갭 (raw에만 하이픈) ===")
gap = df[raw.str.contains("-", regex=False) & ~q.str.contains("-", regex=False)]
print("count:", len(gap))
print(gap[["cluster_id","addr_legal_raw","addr_query","addr_variant_used",
           "vw_level5_raw","status","representative_method"]].to_string(index=False))

print("\n=== [2] 반대 방향 (query에만 하이픈) ===")
rev = df[~raw.str.contains("-", regex=False) & q.str.contains("-", regex=False)]
print("count:", len(rev))
print(rev[["cluster_id","addr_legal_raw","addr_query","addr_variant_used"]].to_string(index=False))

print("\n=== [3] addr_variant_used 분포 ===")
print("--- 전체 274행 ---")
print(df["addr_variant_used"].fillna("<NA>").value_counts(dropna=False).to_string())
print("--- 갭 행만 ---")
print(gap["addr_variant_used"].fillna("<NA>").value_counts(dropna=False).to_string())

print("\n=== [4] 갭 행의 vw_level5_raw 대조 ===")
for _, r in gap.iterrows():
    print(f"  {r['cluster_id']} | raw={r['addr_legal_raw']!r} | "
          f"query={r['addr_query']!r} | level5={r['vw_level5_raw']!r} | "
          f"detail={r['vw_detail_raw']!r}")

print("\n=== [5] 시군구 조립 결함 ===")
bad = df[raw.str.contains(r"(?:성남|수원|고양|용인|안양|부천|안산)(?!시)", regex=True)]
print("count:", len(bad))
print(bad[["cluster_id","addr_legal_raw","addr_query"]].to_string(index=False))

print("\n=== [6] coord_uncertainty_m vs centroid_spread_m ===")
sp = pd.to_numeric(df["centroid_spread_m"], errors="coerce")
un = pd.to_numeric(df["coord_uncertainty_m"], errors="coerce")
print("coord_uncertainty_m 분포:")
print(un.value_counts(dropna=False).to_string())
print("spread>0 이면서 uncertainty==0 인 행 수:", int(((sp > 0) & (un == 0)).sum()))
print(df.loc[(sp > 0) & (un == 0),
      ["cluster_id","centroid_spread_m","coord_uncertainty_m","representative_method"]].to_string(index=False))

print("\n=== [7] 오버라이드 6건 원문 + A10027692 ===")
ov = df[df["override_decision"].notna()]
print("override_rows:", len(ov))
print(ov[["cluster_id","override_decision","representative_method",
          "centroid_spread_m","parcel_count","addr_query"]].to_string(index=False))
print("A10027692_present:", bool((df["cluster_id"] == "A10027692").any()))
print(df.loc[df["cluster_id"] == "A10027692",
      ["cluster_id","centroid_spread_m","representative_method",
       "override_decision","needs_review","status","addr_query"]].to_string(index=False))

print("\n=== [8] 게이트 산출물 실태 ===")
for name in ["stop_gate_report.csv", "stop_gate_report.meta.json"]:
    p = Path("exports") / name
    print(f"{name}: exists={p.exists()} size={p.stat().st_size if p.exists() else None}")
meta = Path("exports/stop_gate_report.meta.json")
if meta.exists() and meta.stat().st_size > 0:
    print("--- meta.json 원문 ---")
    print(meta.read_text(encoding="utf-8"))

print("\n=== [9] geocoding_plan 파일 위치 탐색 ===")
hits = [p for p in Path(".").rglob("*geocoding_plan*") if ".git" not in p.parts]
print("hits:", len(hits))
for p in hits:
    print(" ", p, p.stat().st_size)