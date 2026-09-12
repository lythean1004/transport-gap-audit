import pandas as pd

df = pd.read_csv('bldg_query_plan.csv')
targets = ['A10026126', 'A10026206', 'A10025583', 'A10026990', 'A10027957', 'A10027692']
for t in targets:
    rows = df[df['cluster_id'] == t]
    if rows.empty:
        print(f'{t}: NOT FOUND')
        continue
    for i, (_, r) in enumerate(rows.iterrows()):
        print(f"{t} [{i}] | {r.get('complex_name','')} | legal={r.get('addr_legal','')} | road={r.get('addr_road','')} | platGbCd={r.get('platGbCd','')} | bun={r.get('bun','')} | ji={r.get('ji','')} | dong_token={r.get('dong_token','')}")
    print()
