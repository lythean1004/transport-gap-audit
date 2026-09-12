import math
from pathlib import Path
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 300)
pd.set_option("display.max_rows", 100)

TARGET_NODEID = "GGB222001318"
CLUSTER_ID = "A10022364"
CLUSTER_LAT = 37.6054452938772
CLUSTER_LON = 127.15415038050315

print("=== [0] 지구 반지름 상수 출처 ===")
try:
    from src.collectors.geo_const import R as EARTH_R
    print("import: src.collectors.geo_const.R =", EARTH_R)
except ImportError as e:
    EARTH_R = None
    print("IMPORT_FAIL:", e)
    print("-> geo_const 위치가 다르므로 거리 계산은 건너뜁니다. 이 사실을 보고할 것.")

def haversine_m(lat1, lon1, lat2, lon2, R):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

print("\n=== [1] parquet 파일 탐색 ===")
hits = [p for p in Path(".").rglob("*tago_stops*") if ".git" not in p.parts]
print("hits:", len(hits))
for p in hits:
    print(" ", p, p.stat().st_size)
if not hits:
    raise SystemExit("tago_stops 파일을 찾지 못했습니다. 이 출력을 그대로 보고하세요.")

PQ = hits[0]
print("using:", PQ)

df = pd.read_parquet(PQ)
print("\n=== [2] 전체 컬럼 / 행 수 ===")
print("rows:", len(df))
for i, c in enumerate(df.columns, 1):
    print(f"{i:02d}. {c} ({df[c].dtype})")

print("\n=== [3] 대상 nodeid 행 원문 ===")
sub = df[df["nodeid"].astype(str) == TARGET_NODEID]
print("matched_rows:", len(sub), "/ expected 1")
for _, r in sub.iterrows():
    print("-" * 70)
    for c in df.columns:
        print(f"  {c} = {r[c]!r}")

if len(sub) == 0:
    raise SystemExit("대상 nodeid가 없습니다. 이 출력을 그대로 보고하세요.")

row = sub.iloc[0]
t_lat = float(row["gpslati"])
t_lon = float(row["gpslong"])
t_nm = str(row["nodenm"])
print("\n=== [4] 핵심 3개 값 ===")
print("nodenm :", t_nm)
print("gpslati:", repr(row["gpslati"]), "-> float:", t_lat)
print("gpslong:", repr(row["gpslong"]), "-> float:", t_lon)

if EARTH_R is not None:
    d = haversine_m(CLUSTER_LAT, CLUSTER_LON, t_lat, t_lon, EARTH_R)
    print("\n=== [5] 클러스터 <-> TAGO 거리 (G3 참고) ===")
    print(f"cluster {CLUSTER_ID} = ({CLUSTER_LAT}, {CLUSTER_LON})")
    print(f"tago    {TARGET_NODEID} = ({t_lat}, {t_lon})")
    print(f"distance_m = {d:.2f}  (G3 한계 800m -> {'이내' if d <= 800 else '초과'})")

print("\n=== [6] 같은 이름 정류소 전수 (건너편 후보) ===")
same = df[df["nodenm"].astype(str).str.strip() == t_nm.strip()]
print("same_name_rows:", len(same))
cols = [c for c in ["nodeid", "nodenm", "citycode", "gpslati", "gpslong"] if c in df.columns]
print(same[cols].to_string(index=False))

print("\n=== [7] TAGO 좌표 기준 200m 이내 정류소 전수 ===")
if EARTH_R is not None:
    lat_w = 0.0020
    lon_w = 0.0025
    box = df[
        (pd.to_numeric(df["gpslati"], errors="coerce").between(t_lat - lat_w, t_lat + lat_w)) &
        (pd.to_numeric(df["gpslong"], errors="coerce").between(t_lon - lon_w, t_lon + lon_w))
    ].copy()
    box["dist_m"] = [
        round(haversine_m(t_lat, t_lon, float(a), float(b), EARTH_R), 1)
        for a, b in zip(box["gpslati"], box["gpslong"])
    ]
    box = box[box["dist_m"] <= 200].sort_values("dist_m")
    print("nearby_rows(<=200m):", len(box))
    print(box[cols + ["dist_m"]].to_string(index=False))

print("\n=== [8] citycode 확인 ===")
print("target_citycode:", repr(row["citycode"]))
print("expected_in_registry: 31130")