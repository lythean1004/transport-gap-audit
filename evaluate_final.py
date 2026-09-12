import pandas as pd
import json

HISTORICAL_DISTRICTS = ["화성동탄2", "김포한강", "위례", "남양주다산", "하남미사"]
EXPECTED_EVENTS = ["occupancy_first_actual", "promise_date", "actual_operation"]

df = pd.read_csv('data/source_registry_verified_final_resolution.csv')
df['development'] = df['development'].str.replace(' ', '')

results = {}
for dist in HISTORICAL_DISTRICTS:
    dist_df = df[df['development'].str.contains(dist, na=False, regex=False)]
    results[dist] = {}
    if dist_df.empty:
        results[dist]['status'] = 'NO DATA'
        continue
    
    results[dist]['status'] = 'OK'
    for ev in EXPECTED_EVENTS:
        ev_df = dist_df[dist_df['event_type'] == ev]
        if ev_df.empty:
            results[dist][ev] = 'MISSING'
        else:
            row = ev_df.iloc[0]
            results[dist][ev] = {
                'cand': row.get('cand_id_namespaced', 'N/A'),
                'date': str(row.get('event_date', 'N/A')),
                'prec': str(row.get('date_precision', 'N/A')),
                'mode': str(row.get('mode', 'N/A'))
            }

with open('eval_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
