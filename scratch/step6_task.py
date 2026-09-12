import os
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
now_kst = datetime.now(KST).isoformat()
reviewer = "reviewer_park"

# [할 일 1]
rep_p = Path("exports/stop_gate_report.csv")
size_before = rep_p.stat().st_size if rep_p.exists() else None
if rep_p.exists():
    rep_p.unlink()
exists_after = rep_p.exists()
print(f"1. DELETION: size_before={size_before} / exists_after={exists_after}")

# [할 일 2]
reg_p = Path("evidence/stop_registry.csv")
reg_p.parent.mkdir(parents=True, exist_ok=True)
header = "cluster_id,citycode,nodeid,stop_lat,stop_lon,direction_label,coord_verify_method,raw_citycode_response_path,review_status,verified_by,verified_at,notes\n"
row = f"A10022364,31130,GGB222001318,37.605152,127.155684,도농역.동화중고교.다산플루리움,map_read,evidence/citycode/getCtyCodeList_raw.json,pending,{reviewer},{now_kst},\"pilot smoke 2026-09-03 12:30 KST / evidence expires ~2026-10-03\"\n"

with open(reg_p, "w", encoding="utf-8", newline="\n") as f:
    f.write(header)
    f.write(row)

print("\n2. REGISTRY_CONTENT:")
with open(reg_p, "r", encoding="utf-8") as f:
    print(f.read().strip())

# [할 일 3-1]
print("\n3. WHITELIST_CHECK:")
gate_code = Path("src/verify/stop_gate.py").read_text(encoding="utf-8")
whitelist_lines = []
capture = False
for line in gate_code.splitlines():
    if "ALLOWED_VERIFY_METHODS" in line or "VERIFY_METHODS" in line or "WHITELIST" in line:
        capture = True
    if capture:
        whitelist_lines.append(line)
        if ")" in line or "}" in line or "]" in line:
            if len(whitelist_lines) > 1:
                break
print("\n".join(whitelist_lines))

# [할 일 3-2]
print("\n4. CITYCODE_COUNT:")
cc_path = Path("evidence/citycode/getCtyCodeList_raw.json")
if cc_path.exists():
    cc_text = cc_path.read_text(encoding="utf-8")
    print(f"getCtyCodeList_raw.json exists: True, count of '31130': {cc_text.count('31130')}")
else:
    print("getCtyCodeList_raw.json exists: False")

# [할 일 3-3]
mr_dir = Path("evidence/map_read")
print(f"evidence/map_read/ exists: {mr_dir.exists()}")
if mr_dir.exists():
    print(f"files: {[str(p) for p in mr_dir.glob('*')]}")
else:
    print("files: []")

# [할 일 3-4]
print("\n5. DIRECTION_LABEL_GREP:")
schema_path = Path("docs/stop_registry_schema.md")
if schema_path.exists():
    for i, line in enumerate(schema_path.read_text(encoding="utf-8").splitlines(), 1):
        if "direction_label" in line:
            print(f"{i}: {line}")