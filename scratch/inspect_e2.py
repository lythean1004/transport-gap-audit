import pandas as pd
from datetime import datetime

ledger = pd.read_csv('evidence/arrival_ledger.csv', dtype=str)
ledger['called_at_dt'] = pd.to_datetime(ledger['called_at_kst'])
ledger = ledger.sort_values('called_at_dt')

print("Checking duplicate or near-duplicate calls:")
for d, group in ledger.groupby('obs_date'):
    group = group.sort_values('called_at_dt').reset_index()
    for i in range(len(group) - 1):
        r1 = group.iloc[i]
        r2 = group.iloc[i+1]
        diff = (r2['called_at_dt'] - r1['called_at_dt']).total_seconds()
        if diff <= 120 or r1['slot_hhmm'] == r2['slot_hhmm']:
            print(f"Date: {d} | Row1: idx={r1['index']}, slot={r1['slot_hhmm']}, called={r1['called_at_kst']}, outcome={r1['outcome']} | Row2: idx={r2['index']}, slot={r2['slot_hhmm']}, called={r2['called_at_kst']}, outcome={r2['outcome']} | diff={diff:.2f}s")
