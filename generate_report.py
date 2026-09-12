import pandas as pd
import numpy as np

df = pd.read_csv('data/source_registry_verified_final_resolution.csv')
df['development'] = df['development'].str.replace(' ', '')
HISTORICAL_DISTRICTS = ["화성동탄2", "김포한강", "위례", "남양주다산", "하남미사"]

results = []
for dist in HISTORICAL_DISTRICTS:
    dist_df = df[df['development'].str.contains(dist, na=False, regex=False)]
    if dist_df.empty: continue
    
    occ = dist_df[dist_df['event_type'] == 'occupancy_first_actual']
    prom = dist_df[dist_df['event_type'] == 'promise_date']
    act = dist_df[dist_df['event_type'] == 'actual_operation']
    
    occ_date = occ.iloc[0]['event_date'] if not occ.empty else None
    prom_date = prom.iloc[0]['event_date'] if not prom.empty else None
    act_date = act.iloc[0]['event_date'] if not act.empty else None
    
    def parse_dt(d):
        if pd.isna(d): return None
        d = str(d).strip()
        # Handle MMM-YY
        if len(d) == 6 and d[3] == '-':
            # e.g., Jan-15
            try:
                return pd.to_datetime(d, format='%b-%y')
            except:
                pass
        
        d = d.replace('년', '-').replace('월', '').replace(' ', '')
        if 'H1' in d: d = d.replace('-H1', '-03-01')
        if 'H2' in d: d = d.replace('-H2', '-09-01')
        
        # Handle Year only
        if len(d) == 4 and d.isdigit():
            d = d + '-01-01'
            
        try:
            return pd.to_datetime(d)
        except:
            return None
    
    od = parse_dt(occ_date)
    ad = parse_dt(act_date)
    
    if od and ad:
        gap_years = round((ad - od).days / 365.25, 1)
        gap_str = f"{gap_years}년"
    else:
        gap_str = '미개통 (진행중)'
        
    results.append({
        '지구명': dist,
        '최초입주': str(occ_date),
        '교통약속': str(prom_date),
        '실제개통': str(act_date) if pd.notna(act_date) else '미개통',
        '교통소외기간(년)': gap_str
    })

res_df = pd.DataFrame(results)

with open("report_table.md", "w", encoding="utf-8") as f:
    f.write(res_df.to_markdown(index=False))

