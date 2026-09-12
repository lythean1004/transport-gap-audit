import pandas as pd
from pathlib import Path

ledger = pd.read_csv('evidence/arrival_ledger.csv', dtype=str)
dup_keys = ledger[ledger.duplicated(['obs_date', 'slot_hhmm'], keep=False)]
print(f'Total duplicate rows: {len(dup_keys)}')
for (d, s), g in dup_keys.groupby(['obs_date', 'slot_hhmm']):
    print(f'=== Key: {d} {s} (rows: {len(g)}) ===')
    for idx, r in g.iterrows():
        print(f"  idx={idx} outcome={r['outcome']} retry={r['retry_count']} called={r['called_at_kst']} raw_path={r['raw_path']} items={r['item_count']}")

# Also check api_error rows
print("\n=== api_error rows ===")
api_err = ledger[ledger['outcome'] == 'api_error']
for idx, r in api_err.iterrows():
    d, s = r['obs_date'], r['slot_hhmm']
    p_conv = Path(f"evidence/arrival_raw/{d}/31130_GGB222001318_{s}.json")
    print(f"idx={idx} {d} {s} outcome={r['outcome']} raw_path={r['raw_path']} convention_exists={p_conv.exists()}")
