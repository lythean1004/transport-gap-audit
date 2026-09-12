import math
from typing import List, Dict
from src.collectors.api_common import fetch_public_api
from src.config import require_secret

PROXIMITY_URL = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList"
ARRIVAL_URL = "https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    return distance * 1000 # returns meters

def get_proximate_stations(center_lat: float, center_lon: float, grid_size_meters: float = 300) -> List[Dict]:
    """
    Fetches proximate bus stations using a 3x3 grid around the center to cover 800-1000m.
    """
    service_key = require_secret("TAGO_SERVICE_KEY")
    
    # 3x3 grid offsets roughly in degrees (1 deg lat ~ 111km, 1 deg lon ~ 111km * cos(lat))
    lat_offset = grid_size_meters / 111000.0
    lon_offset = grid_size_meters / (111000.0 * math.cos(math.radians(center_lat)))
    
    unique_stations = {}
    
    for i in [-1, 0, 1]:
        for j in [-1, 0, 1]:
            grid_lat = center_lat + (i * lat_offset)
            grid_lon = center_lon + (j * lon_offset)
            
            params = {
                "serviceKey": service_key,
                "pageNo": 1,
                "numOfRows": 100,
                "_type": "json",
                "gpsLati": round(grid_lat, 6),
                "gpsLong": round(grid_lon, 6)
            }
            
            resp = fetch_public_api("tago_proximity", PROXIMITY_URL, params)
            items = resp.get('data', {}).get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            
            for item in items:
                node_id = item.get("nodeid")
                if node_id and node_id not in unique_stations:
                    item_lat = float(item.get("gpslati", 0))
                    item_lon = float(item.get("gpslong", 0))
                    dist = haversine(center_lat, center_lon, item_lat, item_lon)
                    
                    unique_stations[node_id] = {
                        "nodeid": node_id,
                        "nodenm": item.get("nodenm"),
                        "citycode": item.get("citycode"),
                        "gpslati": item_lat,
                        "gpslong": item_lon,
                        "distance_to_center": round(dist, 1)
                    }
                    
    # Return sorted by distance
    return sorted(unique_stations.values(), key=lambda x: x["distance_to_center"])

def get_arrival_info(city_code: str, node_id: str):
    """
    Fetches arrival info for a specific bus station.
    """
    params = {
        "serviceKey": require_secret("TAGO_SERVICE_KEY"),
        "pageNo": 1,
        "numOfRows": 100,
        "_type": "json",
        "cityCode": city_code,
        "nodeId": node_id
    }
    
    resp = fetch_public_api("tago_arrival", ARRIVAL_URL, params)
    
    items = resp.get('data', {}).get('response', {}).get('body', {}).get('items', {}).get('item', [])
    if isinstance(items, dict): items = [items]
    
    extracted = []
    for item in items:
        extracted.append({
            "routeid": item.get("routeid"),
            "routeno": item.get("routeno"),
            "routetp": item.get("routetp"),
            "arrprevstationcnt": item.get("arrprevstationcnt"),
            "arrtime": item.get("arrtime"),
            "vehicletp": item.get("vehicletp"),
        })
        
    return extracted

