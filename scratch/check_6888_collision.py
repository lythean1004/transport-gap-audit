"""6888 계열 3개 클러스터의 PARCEL/ROAD 좌표 비교 및 충돌 검증"""
import sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from tools import __path__ as _  # dummy
# 직접 probe의 vworld_getcoord를 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from importlib import import_module

# vworld_getcoord를 직접 정의
import requests, math
from src.config import require_secret

def vworld_getcoord(address, typ):
    params = {
        "service": "address", "version": "2.0", "request": "GetCoord",
        "key": require_secret("VWORLD_API_KEY"),
        "format": "json", "errorFormat": "json",
        "type": typ, "address": address,
        "refine": "true", "simple": "false", "crs": "EPSG:4326",
    }
    r = requests.get("https://api.vworld.kr/req/address", params=params, timeout=10).json()
    status = r.get("response", {}).get("status")
    if status != "OK":
        return {"status": status, "lat": None, "lon": None, "refined_text": ""}
    pt = r["response"]["result"]["point"]
    ref = r["response"].get("refined", {})
    return {"status": "OK", "lat": float(pt["y"]), "lon": float(pt["x"]),
            "refined_text": ref.get("text", "")}

import re
GU_FIX_RE = re.compile(r"(화성|성남|수원|고양|용인|안양|안산|부천|청주|천안|전주|포항|창원|안동)(\w+구)")
def normalize_addr(s):
    return GU_FIX_RE.sub(r"\1시 \2", s)

cases = [
    ("A10027957", "경기도 김포시 구래동 6888",   "경기도 김포시 한강8로 365"),
    ("A41576913", "경기도 김포시 구래동 6888-2", "경기도 김포시 한강8로 377"),
    ("A10026654", "경기도 김포시 구래동 6888-6", "경기도 김포시 한강9로12길 50"),
]

print("=== 6888 계열 좌표 충돌 검증 ===\n")
parcel_coords = []
road_coords = []

for cid, parcel_addr, road_addr in cases:
    rp = vworld_getcoord(normalize_addr(parcel_addr), "PARCEL"); time.sleep(0.15)
    rr = vworld_getcoord(normalize_addr(road_addr), "ROAD"); time.sleep(0.15)
    
    print(f"[{cid}]")
    print(f"  PARCEL: ({rp.get('lat','N/A')}, {rp.get('lon','N/A')}) -> {rp.get('refined_text','')}")
    print(f"  ROAD  : ({rr.get('lat','N/A')}, {rr.get('lon','N/A')}) -> {rr.get('refined_text','')}")
    
    if rp["lat"]:
        parcel_coords.append((cid, rp["lat"], rp["lon"]))
    if rr["lat"]:
        road_coords.append((cid, rr["lat"], rr["lon"]))

print("\n=== PARCEL 좌표 비교 ===")
for i in range(len(parcel_coords)):
    for j in range(i+1, len(parcel_coords)):
        a, b = parcel_coords[i], parcel_coords[j]
        R = 6371008.8
        dlat = math.radians(b[1]-a[1])
        dlon = math.radians(b[2]-a[2])
        h = math.sin(dlat/2)**2 + math.cos(math.radians(a[1]))*math.cos(math.radians(b[1]))*math.sin(dlon/2)**2
        d = 2*R*math.asin(math.sqrt(h))
        print(f"  {a[0]} vs {b[0]}: {d:.1f}m")
        if d < 1.0:
            print(f"  *** 좌표 충돌! 거리 {d:.1f}m ***")

print("\n=== ROAD 좌표 비교 ===")
for i in range(len(road_coords)):
    for j in range(i+1, len(road_coords)):
        a, b = road_coords[i], road_coords[j]
        dlat = math.radians(b[1]-a[1])
        dlon = math.radians(b[2]-a[2])
        h = math.sin(dlat/2)**2 + math.cos(math.radians(a[1]))*math.cos(math.radians(b[1]))*math.sin(dlon/2)**2
        d = 2*R*math.asin(math.sqrt(h))
        print(f"  {a[0]} vs {b[0]}: {d:.1f}m")
        if d < 1.0:
            print(f"  *** 좌표 충돌! 거리 {d:.1f}m ***")
