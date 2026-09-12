import pandas as pd
import os
import subprocess
import time

plan = pd.read_csv('bldg_query_plan.csv')
plan = plan[plan['lookup_status'] == 'SUCCESS']

env = os.environ.copy()
env['ALLOW_LIVE_CALL'] = '1'

for idx, row in plan.iterrows():
    print(f"[{idx+1}/{len(plan)}] Fetching {row['complex_name']} ({row['sigunguCd']}-{row['bjdongCd']}-{row['bun']}-{row['ji']})")
    # Cast to ensure proper strings without .0
    sigunguCd = str(int(row['sigunguCd'])) if pd.notnull(row['sigunguCd']) else ""
    bjdongCd = str(int(row['bjdongCd'])).zfill(5) if pd.notnull(row['bjdongCd']) else ""
    platGbCd = str(int(row['platGbCd'])) if pd.notnull(row['platGbCd']) else "0"
    bun = str(row['bun']).zfill(4)
    ji = str(row['ji']).zfill(4)
    
    cmd = [
        "python", "-m", "src.collectors.building_hub",
        "--sigunguCd", sigunguCd,
        "--bjdongCd", bjdongCd,
        "--platGbCd", platGbCd,
        "--bun", bun,
        "--ji", ji,
        "--live"
    ]
    try:
        subprocess.run(cmd, env=env, check=True)
    except Exception as e:
        print(f"Error fetching {row['cluster_id']}: {e}")
    time.sleep(0.5) # rate limit protection
