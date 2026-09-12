import pytest
import yaml
import math
from pathlib import Path

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def test_pilots_config():
    config_path = Path('config/pilots.yaml')
    if not config_path.exists():
        pytest.skip("config/pilots.yaml not found")
        
    with open(config_path, 'r', encoding='utf-8') as f:
        # Load as a string to check decimal places easily if needed, but safe_load is better
        data = yaml.safe_load(f)
        
    errors = []
    
    # 1. meta.coord_crs == 'EPSG:4326'
    meta = data.get('meta', {})
    if meta.get('coord_crs') != 'EPSG:4326':
        errors.append(f"meta.coord_crs is '{meta.get('coord_crs')}', expected 'EPSG:4326'")
        
    pilots = data.get('pilots', [])
    for p in pilots:
        pid = p.get('development_id', 'UNKNOWN')
        clusters = p.get('clusters', [])
        
        # If no clusters, maybe it's not a historical pilot or not filled yet
        if not clusters:
            continue
            
        valid_clusters = [c for c in clusters if c.get('cluster_status') != 'surplus']
        if not (3 <= len(valid_clusters) <= 5):
            errors.append(f"Pilot {pid}: cluster count (excluding surplus) is {len(valid_clusters)}, must be between 3 and 5")
            
        prev_date = None
        
        for i, c in enumerate(clusters):
            cid = c.get('cluster_id', 'UNKNOWN')
            
            # Check cluster_id matches pilot prefix
            # Example: DEV-DONGTAN2 prefix could be DEV-DONGTAN2 or DONGTAN2
            prefix_full = pid
            prefix_short = pid.replace('DEV-', '')
            if not (cid.startswith(prefix_full) or cid.startswith(prefix_short)):
                errors.append(f"Cluster {cid}: does not match pilot prefix {pid}")
                
            # lat/lon bounds
            lat = c.get('lat')
            lon = c.get('lon')
            if lat is None or lon is None:
                errors.append(f"Cluster {cid}: missing lat or lon")
            else:
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                    if not (33.0 <= lat_f <= 39.0):
                        errors.append(f"Cluster {cid}: lat {lat_f} out of bounds (33-39). Did you swap x and y?")
                    if not (124.0 <= lon_f <= 132.0):
                        errors.append(f"Cluster {cid}: lon {lon_f} out of bounds (124-132). Did you swap x and y?")
                    if lat_f == 0.0 and lon_f == 0.0:
                        errors.append(f"Cluster {cid}: lat and lon cannot both be zero")
                        
                    # 5 decimal places check
                    # Convert to string without scientific notation
                    lat_str = format(lat_f, '.10g')
                    lon_str = format(lon_f, '.10g')
                    lat_dec = len(lat_str.split('.')[-1]) if '.' in lat_str else 0
                    lon_dec = len(lon_str.split('.')[-1]) if '.' in lon_str else 0
                    
                    if lat_dec < 5 or lon_dec < 5:
                        errors.append(f"Cluster {cid}: lat/lon must have at least 5 decimal places (got lat:{lat_dec}, lon:{lon_dec})")
                except ValueError:
                    errors.append(f"Cluster {cid}: lat or lon is not numeric")
                    
            # households_at_start
            hh = c.get('households_at_start')
            if not isinstance(hh, int) or hh <= 0:
                errors.append(f"Cluster {cid}: households_at_start must be a positive integer, got {hh}")
                
            # metadata fields non-empty
            for field in ['coord_source', 'coord_verified_by', 'coord_retrieved_at', 'coord_verify_method']:
                val = c.get(field)
                if not val or str(val).strip() == "":
                    errors.append(f"Cluster {cid}: {field} is empty or missing")
                    
            # human_match_status
            if c.get('human_match_status') != 'confirmed':
                errors.append(f"Cluster {cid}: human_match_status must be 'confirmed'")
                
            # approval_date_earliest ordering
            date_val = c.get('approval_date_earliest')
            if date_val:
                if prev_date and date_val < prev_date:
                    errors.append(f"Cluster {cid}: approval_date_earliest ({date_val}) is earlier than previous cluster ({prev_date})")
                prev_date = date_val
                
        # Haversine pairwise distance >= 400m
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                c1 = clusters[i]
                c2 = clusters[j]
                lat1, lon1 = c1.get('lat'), c1.get('lon')
                lat2, lon2 = c2.get('lat'), c2.get('lon')
                if lat1 and lon1 and lat2 and lon2:
                    try:
                        dist = haversine(float(lat1), float(lon1), float(lat2), float(lon2))
                        if dist < 400.0:
                            errors.append(f"Pilot {pid}: distance between {c1.get('cluster_id')} and {c2.get('cluster_id')} is {dist:.1f}m (< 400m)")
                    except ValueError:
                        pass # handled above
                        
    if errors:
        pytest.fail("Validation errors in config/pilots.yaml:\\n" + "\\n".join(errors))
