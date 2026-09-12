import pandas as pd

df = pd.read_csv('exports/complex_geocode.csv')
target_ids = ['A10022364', 'A10024817', 'A10025828', 'A10027369']
m = df[df['cluster_id'].isin(target_ids)]
print('=== 4 target clusters in complex_geocode.csv ===')
for _, r in m.iterrows():
    print(f"id={r['cluster_id']}, name={r['complex_name']}, addr_raw={r['addr_legal_raw']}, addr_q={r['addr_query']}, status={r['status']}, lat={r['lat']}, lon={r['lon']}")

has_trailing_hyphen = int(df['addr_query'].astype(str).str.endswith('-').sum())
print(f'Total trailing hyphen in addr_query: {has_trailing_hyphen}')
