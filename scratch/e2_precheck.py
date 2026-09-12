from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, pandas as pd

KST = timezone(timedelta(hours=9))
CITY, NODE, CID = "31130", "GGB222001318", "A10022364"
now = datetime.now(KST)
print("[0] now_kst:", now.isoformat())

def head(p):
    q = Path(p)
    print(f"\n=== {p} exists={q.exists()} size={q.stat().st_size if q.exists() else None}")
    return q

# [1] G1: citycodes parquet
q = head("data/staged/tago_citycodes.parquet")
if q.exists():
    d = pd.read_parquet(q)
    print("rows:", len(d), "cols:", list(d.columns))
    if "citycode" in d.columns:
        m = d[d["citycode"].astype(str).str.strip() == CITY]
        print("citycode_31130_rows:", len(m))
        print(m.to_string(index=False))

# [2] G1: raw json 파싱 (게이트와 동일 경로)
q = head("evidence/citycode/getCtyCodeList_raw.json")
if q.exists():
    try:
        raw = json.load(open(q, encoding="utf-8"))
        it = raw.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(it, dict):
            it = [it]
        print("items_type:", type(it).__name__, "len:", len(it))
        print("found_31130:", any(str(x.get("citycode","")).strip() == CITY for x in it))
    except Exception as e:
        print("JSON_FAIL", type(e).__name__, e)

# [3] G4: smoke_log
q = head("evidence/smoke_log.csv")
if q.exists():
    d = pd.read_csv(q)
    print("rows:", len(d), "cols:", list(d.columns))
    if {"citycode","nodeid"} <= set(d.columns):
        m = d[(d["citycode"].astype(str).str.strip() == CITY) &
              (d["nodeid"].astype(str).str.strip() == NODE)]
        print("matched_smoke_rows:", len(m))
        for _, r in m.iterrows():
            print("  ---- row ----")
            for c in d.columns:
                print(f"    {c} = {r[c]!r}")
            t = str(r.get("smoke_test_at_kst", "")).strip()
            try:
                dt = datetime.fromisoformat(t)
                dt = dt.replace(tzinfo=KST) if dt.tzinfo is None else dt.astimezone(KST)
                print("    weekday(0=월):", dt.weekday(), "time:", dt.time(),
                      "age_days:", (now - dt).days)
            except Exception as e:
                print("    TIME_FAIL", type(e).__name__, e)

# [4] G3: complex_geocode 대상 행
q = head("exports/complex_geocode.csv")
if q.exists():
    d = pd.read_csv(q)
    m = d[d["cluster_id"].astype(str).str.strip() == CID]
    print("cluster_match_count:", len(m))
    for c in ["cluster_id", "lat", "lon", "crs"]:
        if c in d.columns and len(m):
            print(f"  {c} =", repr(m.iloc[0][c]))

# [5] G5: verified_at 미래 여부
q = head("evidence/stop_registry.csv")
if q.exists():
    d = pd.read_csv(q)
    r = d.iloc[0]
    va = str(r["verified_at"]).strip()
    v = datetime.fromisoformat(va)
    print("verified_at:", va, "tzinfo:", v.tzinfo)
    print("is_future(5min margin):", v > now + timedelta(minutes=5))
    print("coord_verify_method:", repr(r["coord_verify_method"]))
    print("direction_label:", repr(r["direction_label"]))
    print("review_status:", repr(r["review_status"]))

# [6] 출력 대상 상태
for p in ["exports/stop_gate_report.csv", "exports/stop_gate_report.meta.json"]:
    print(f"\n{p} exists:", Path(p).exists())