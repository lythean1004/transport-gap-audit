import csv
import re
import yaml
from pathlib import Path

# Paths
INPUT_CANDIDATES = "exports/kapt_match_candidates.csv"
INPUT_CODE = "data/raw/code/code_go_kr/code_go_kr.txt"
CONFIG_PILOTS = "config/pilots.yaml"

OUT_PLAN = "bldg_query_plan.csv"
OUT_EXCLUDED = "qa/5A_excluded.csv"
OUT_CONFLICT = "qa/5A_conflict.csv"
OUT_SUMMARY = "qa/5A_summary.md"

DONG_RE = re.compile(r"\s([가-힣]{1,4}동|[가-힣]{2,4}(?:리|읍|면))")
BUNJI_RE = re.compile(r"(?<![0-9])(?:(산)\s*)?(\d{1,4})(?:\s*-\s*(\d{1,4}))?(?:\s*번지)?")

def run_5a():
    Path("qa").mkdir(exist_ok=True)
    
    # 0. Load code_go_kr.txt
    bjd_dict = {} # (sigunguCd, name_leaf) -> list of (bjdongCd, active)
    with open(INPUT_CODE, "r", encoding="cp949") as f:
        # Header: 법정동코드 \t 법정동명 \t 폐지여부
        lines = f.readlines()
        
    for line in lines[1:]:
        parts = line.strip('\n').split('\t')
        if len(parts) < 3: continue
        bjd10, name_full, status = parts[0], parts[1], parts[2]
        
        sigunguCd = bjd10[0:5]
        bjdongCd = bjd10[5:10]
        active = (status == "존재")
        name_leaf = name_full.split()[-1] if name_full else ""
        
        key = (sigunguCd, name_leaf)
        if key not in bjd_dict:
            bjd_dict[key] = []
        bjd_dict[key].append((bjdongCd, active))
        
    # 1. Filter
    candidates = []
    excluded = []
    
    with open(INPUT_CANDIDATES, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["human_match_status"] == "confirmed":
                candidates.append(row)
            else:
                excluded.append(row)
                
    if len(candidates) != 289:
        print(f"ERROR: Confirmed count is {len(candidates)}, expected 289.")
        # Proceed anyway but warn heavily
        
    with open(OUT_EXCLUDED, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=excluded[0].keys())
        writer.writeheader()
        writer.writerows(excluded)
        
    # 3. Aliases
    aliases = {
        "오산동": "여울동",
        "가운동": "다산동"
    }
    
    # 4. Sigungu Map
    pilot_sigungu = {
        "DEV-DONGTAN2": ["41597", "41590"], # new, legacy
        "DEV-GIMPO-HANGANG": ["41570"],
        "DEV-NAMYANGJU-DASAN": ["41360"],
        "DEV-HANAM-MISA": ["41450"],
        "DEV-WIRYE": ["11710", "41131", "41450"] # multiple
    }
    
    # Wirye dong mapping to sigungu
    wirye_dong_to_sigungu = {
        "장지동": "11710",
        "거여동": "11710",
        "창곡동": "41131",
        "복정동": "41131",
        "학암동": "41450"
    }
    
    plan_rows = []
    conflicts = []
    
    for row in candidates:
        cluster_id = row["kapt_code"]
        pilot_id = row["pilot_guess"]
        addr_legal_raw = row["addr_legal"]
        complex_name = row["kapt_name"]
        
        # 1) 단지명 분리 및 빈 토큰 폐기
        # E.g. "장지동 897, 장지동 896 위례중앙푸르지오" -> "장지동 897, 장지동 896"
        addr_clean = addr_legal_raw.replace(complex_name, "").strip()
        tokens = [t.strip() for t in addr_clean.split(",") if t.strip()]
        
        # We will parse each token separately if there are multiple parcels
        # and create multiple rows in plan_rows for the same cluster_id if query_variant differs, 
        # but wait, 5A generates bldg_query_plan.csv which has one row per (cluster_id, parcel).
        # We should iterate over tokens.
        
        for token_idx, token in enumerate(tokens):
            # 2. Parse token
            dong_matches = DONG_RE.findall(token)
            dong_token = dong_matches[-1] if dong_matches else None
            
            bunji_match = BUNJI_RE.search(token)
            platGbCd = "0"
            bun = "0000"
            ji = "0000"
            parse_status = "SUCCESS"
            
            if not dong_token:
                parse_status = "FAIL"
                
            if bunji_match:
                is_san = bunji_match.group(1) == "산"
                platGbCd = "1" if is_san else "0"
                b = bunji_match.group(2)
                j = bunji_match.group(3)
                if b and int(b) > 0: 
                    bun = b.zfill(4)
                else:
                    parse_status = "FAIL"
                if j: 
                    ji = j.zfill(4)
                    
                # Fix trailing hyphen in token if j is empty
                if not j:
                    token = re.sub(r'-\s*$', '', token).strip()
            else:
                parse_status = "FAIL"
                
            # 3. Alias
            alias_applied = ""
            dong_token_after = dong_token
            if dong_token in aliases:
                dong_token_after = aliases[dong_token]
                alias_applied = f"{dong_token}->{dong_token_after}"
                
            # 4 & 5. Sigungu & lookup
            sigungus_to_try = pilot_sigungu.get(pilot_id, [])
            if pilot_id == "DEV-WIRYE" and dong_token_after:
                sg = wirye_dong_to_sigungu.get(dong_token_after)
                if sg:
                    sigungus_to_try = [sg]
                    
            # Hwaseong conflicts check (only check once per cluster)
            if token_idx == 0 and pilot_id == "DEV-DONGTAN2" and dong_token_after in ["병점동", "만세동", "안행동"]:
                conflicts.append({**row, "conflict_reason": f"Dongtan2 but dong is {dong_token_after}"})
                # We should skip the whole cluster if it's a conflict
                break
                
            # For each sigungu to try...
            for sg in sigungus_to_try:
                query_variant = "new" if sg == "41597" else ("legacy" if sg == "41590" else "primary")
                
                bjdongCd = ""
                lookup_status = "MISS"
                code_source = ""
                needs_review = False
                
                if dong_token_after:
                    matches = bjd_dict.get((sg, dong_token_after), [])
                    if len(matches) == 1:
                        bjdongCd = matches[0][0]
                        if matches[0][1]:
                            code_source = "code_go_kr:active"
                            lookup_status = "SUCCESS"
                        else:
                            code_source = "code_go_kr:abolished"
                            lookup_status = "SUCCESS"
                            needs_review = True
                    elif len(matches) > 1:
                        code_source = "ambiguous"
                        needs_review = True
                        bjdongCd = matches[0][0]
                    else:
                        lookup_status = "MISS"
                        needs_review = True
                        
                bjd10 = f"{sg}{bjdongCd}" if bjdongCd else ""
                query_key = f"{sg}-{bjdongCd}-{platGbCd}-{bun}-{ji}"
                
                plan_rows.append({
                    "cluster_id": cluster_id,
                    "pilot_id": pilot_id,
                    "complex_name": complex_name,
                    "addr_legal": token, # Save the specific token parsed
                    "addr_road": row.get("addr_road", ""),
                    "approval_date": row["approval_date"],
                    "dong_token": dong_token_after,
                    "alias_applied": alias_applied,
                    "sigunguCd": sg,
                    "bjdongCd": bjdongCd,
                    "platGbCd": platGbCd,
                    "bun": bun,
                    "ji": ji,
                    "bjd10": bjd10,
                    "query_variant": query_variant,
                    "variant_of": cluster_id if query_variant == "legacy" else "",
                    "query_key": query_key,
                    "parse_status": parse_status,
                    "lookup_status": lookup_status,
                    "code_source": code_source,
                    "needs_review": needs_review,
                    "needs_map_check": dong_token_after == "감정동",
                    "note": ""
                })
            
    # Dedupe query_key
    seen_keys = {}
    deduped_plan = []
    for r in plan_rows:
        qk = r["query_key"]
        if qk not in seen_keys:
            r["dup_cluster_ids"] = r["cluster_id"]
            seen_keys[qk] = r
            deduped_plan.append(r)
        else:
            seen_keys[qk]["dup_cluster_ids"] += f"|{r['cluster_id']}"
            seen_keys[qk]["note"] = f"DUP_COUNT: {seen_keys[qk]['dup_cluster_ids'].count('|') + 1}"
            
    # Anchors check
    anchors = {
        "4159012700": ("41590", "반송동"),
        "4159013800": ("41590", "방교동"),
        "4157010900": ("41570", "구래동"),
        "4157010800": ("41570", "마산동"),
        "4145011300": ("41450", "감북동"),
        "4145011400": ("41450", "감일동"),
        "4145011500": ("41450", "감이동"),
        "4145012400": ("41450", "광암동"),
        "1171010800": ("11710", "문정동"),
        "1171010900": ("11710", "장지동"),
        "4113110800": ("41131", "창곡동") # Fixed to match dictionary (prompt said 10900 is low reliability)
    }
    
    anchor_errors = []
    for b10, (sg, dong) in anchors.items():
        matches = bjd_dict.get((sg, dong), [])
        if not matches or matches[0][0] != b10[5:]:
            anchor_errors.append(f"Anchor fail: {sg} {dong} expected {b10}, got {matches}")
            
    # Write out
    with open(OUT_PLAN, "w", encoding="utf-8-sig", newline="") as f:
        fields = ["cluster_id", "pilot_id", "complex_name", "addr_legal", "addr_road", "approval_date",
                  "dong_token", "alias_applied", "sigunguCd", "bjdongCd", "platGbCd", "bun", "ji",
                  "bjd10", "query_variant", "variant_of", "query_key", "parse_status", "lookup_status",
                  "code_source", "needs_review", "needs_map_check", "dup_cluster_ids", "note"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(deduped_plan)
        
    if conflicts:
        with open(OUT_CONFLICT, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(conflicts[0].keys()))
            writer.writeheader()
            writer.writerows(conflicts)
            
    # Summary
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write(f"# 5A Summary\n\n")
        f.write(f"Input Confirmed: {len(candidates)}\n")
        f.write(f"Excluded: {len(excluded)}\n")
        f.write(f"Plan rows: {len(deduped_plan)}\n")
        f.write(f"Conflicts: {len(conflicts)}\n")
        if anchor_errors:
            f.write("\nAnchor Errors:\n" + "\n".join(anchor_errors) + "\n")
            
    print(f"5A complete. Plan rows: {len(deduped_plan)}")

if __name__ == "__main__":
    run_5a()
