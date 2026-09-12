import pandas as pd

ledger = pd.read_csv('evidence/arrival_ledger.csv', dtype=str)
l_0911 = ledger[ledger['obs_date'] == '2026-09-11']
print(f'09-11 rows: {len(l_0911)}')
print('09-11 min slot:', l_0911['slot_hhmm'].min(), 'max slot:', l_0911['slot_hhmm'].max())
print('09-11 max called_at:', l_0911['called_at_kst'].max())
print('09-11 slots:', sorted(l_0911['slot_hhmm'].tolist()))
