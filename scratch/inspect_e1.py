import pandas as pd
import json
from pathlib import Path

ledger = pd.read_csv('evidence/arrival_ledger.csv', dtype=str)
non_ok = ledger[ledger['outcome'] != 'ok_with_items']
print(f"Total non-ok rows: {len(non_ok)}")

for idx, r in non_ok.iterrows():
    raw_path_val = r['raw_path']
    if pd.isna(raw_path_val) or not str(raw_path_val).strip():
        p = None
        exists = False
    else:
        p = Path(str(raw_path_val))
        exists = p.exists()
    route_cnt = 0
    item_cnt = 0
    if exists:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
            items = d.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            elif not isinstance(items, list): items = []
            item_cnt = len(items)
            routes = set(it.get('routeid') for it in items if isinstance(it, dict) and it.get('routeid'))
            route_cnt = len(routes)
        except Exception as e:
            item_cnt = -1
    print(f"{r['obs_date']} {r['slot_hhmm']} outcome={r['outcome']} res={r['result_code']} items={r['item_count']} raw_exists={exists} parsed_routes={route_cnt} parsed_items={item_cnt} raw_path={r['raw_path']}")
