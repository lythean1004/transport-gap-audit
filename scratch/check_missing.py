import pandas as pd

df = pd.read_csv('bldg_query_plan.csv')
for cid in ['A10025583', 'A10026990']:
    rows = df[df['cluster_id'] == cid]
    nr = rows.iloc[0]['needs_review']
    ps = rows.iloc[0]['parse_status']
    print(f"{cid}: needs_review={nr}, parse_status={ps}")

df_geo = pd.read_csv('exports/complex_geocode.csv')
for cid in ['A10025583', 'A10026990']:
    hit = df_geo[df_geo['cluster_id'] == cid]
    if hit.empty:
        print(f"{cid}: NOT in geocode CSV")
    else:
        r = hit.iloc[0]
        print(f"{cid}: variant={r.addr_variant_used}, type={r.type}, review={r.needs_review}")

import os
if os.path.exists('qa/6B_geocode_fail.csv'):
    df_fail = pd.read_csv('qa/6B_geocode_fail.csv')
    print("\nFAIL:")
    print(df_fail.to_string())
