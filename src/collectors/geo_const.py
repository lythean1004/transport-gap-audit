import math

LAT_M_PER_DEG = 111200

def LON_M_PER_DEG_AT(lat: float) -> float:
    return 111320 * math.cos(math.radians(lat))

# 500m 반경 원 9개로 1,000m 민감도를 빈틈없이 커버하기 위해 대각선 커버리지를 고려하여 
# 격자 간격을 500m보다 넓은 700m로 설정합니다. (직선거리 기준)
GRID_STEP_M = 700

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # Earth radius in meters
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
