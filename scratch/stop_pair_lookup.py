import math
import pandas as pd

pd.set_option("display.width", 300)
pd.set_option("display.max_rows", 200)

# 기준: nodeid GGB222001318 의 TAGO 좌표 (참고 계산용, 게이트 판정 아님)
REF_LAT, REF_LON = 37.6051167, 127.15575
R_REF = 6371000.0  # 참고용 상수. 게이트는 src/collectors/geo_const.py 를 사용

def hv(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2)
    return 2 * R_REF * math.asin(math.sqrt(a))

df = pd.read_parquet("data/staged/tago_stops_full.parquet")
df["nodeno"] = df["nodeno"].astype(str)
show = ["nodeid", "nodenm", "nodeno", "citycode", "gpslati", "gpslong"]

print("=== [1] nodeno == 23931 조회 ===")
a = df[df["nodeno"].str.strip() == "23931"]
print("matched:", len(a))
print(a[show].to_string(index=False) if len(a) else "(없음)")

print("\n=== [2] nodeno 23920~23940 구간 ===")
b = df[df["nodeno"].str.strip().str.isdigit()].copy()
b["n"] = b["nodeno"].astype(int)
rng = b[(b["n"] >= 23920) & (b["n"] <= 23940)].sort_values("n")
print("rows:", len(rng))
print(rng[show].to_string(index=False))

print("\n=== [3] 이름에 '해링턴' 또는 '가운휴먼시아' 포함 정류소 전수 ===")
m = df[df["nodenm"].astype(str).str.contains("해링턴|가운휴먼시아", regex=True, na=False)].copy()
m["dist_from_ref_m"] = [round(hv(REF_LAT, REF_LON, float(x), float(y)), 1)
                        for x, y in zip(m["gpslati"], m["gpslong"])]
m = m.sort_values("dist_from_ref_m")
print("rows:", len(m))
print(m[show + ["dist_from_ref_m"]].to_string(index=False))

print("\n=== [4] 기준점 300m 이내 정류소 전수 ===")
c = df.copy()
c["la"] = pd.to_numeric(c["gpslati"], errors="coerce")
c["lo"] = pd.to_numeric(c["gpslong"], errors="coerce")
c = c[c["la"].between(REF_LAT - 0.003, REF_LAT + 0.003)
      & c["lo"].between(REF_LON - 0.004, REF_LON + 0.004)]
c["dist_m"] = [round(hv(REF_LAT, REF_LON, la, lo), 1) for la, lo in zip(c["la"], c["lo"])]
c = c[c["dist_m"] <= 300].sort_values("dist_m")
print("rows(<=300m):", len(c))
print(c[show + ["dist_m"]].to_string(index=False))