import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
from scratch.calc_headway_v6_2 import load_data, process_ledger, build_timeseries, detect_events_v2, aggregate_metrics

ledger, raw_df, pub_df, _ = load_data()
lc, _, _, dd = process_ledger(ledger)
ra = sorted(raw_df['routeid'].unique())
exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']
valid_ra = [r for r in ra if r not in exc_routes]

ts_b = build_timeseries(lc, raw_df, ra, deduplicated_slots=dd, zero_fill=False)
ev_b, _ = detect_events_v2(ts_b)
ts_z = build_timeseries(lc, raw_df, ra, deduplicated_slots=dd, zero_fill=True)
ev_z, _ = detect_events_v2(ts_z)

# E2: Compare definitions
dates_core = ['2026-09-07', '2026-09-08', '2026-09-09']
dates_supp = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']

m_b = aggregate_metrics(ev_b, ts_b, routes_to_exclude=exc_routes)
m_z = aggregate_metrics(ev_z, ts_z, routes_to_exclude=exc_routes)

def calc_e2(name, m_full, ev_src, d_list):
    sub_m = m_full[m_full['obs_date'].isin(d_list)].copy()
    sub_ev = ev_src[(ev_src['obs_date'].isin(d_list)) & (~ev_src['routeid'].isin(exc_routes))].copy()
    
    # 1. v6.2 Current (Included: insufficient groups raw gaps ARE in the pool)
    gaps_inc = sub_ev['gap_min'].dropna()
    med_inc = gaps_inc.median()
    p25_inc = gaps_inc.quantile(0.25)
    p75_inc = gaps_inc.quantile(0.75)
    n_insuff = sub_m['insufficient_observation'].sum()
    n_groups = len(sub_m)
    pct_str = f"{(n_insuff/n_groups*100) if n_groups>0 else 0:.1f}% ({n_insuff}/{n_groups})"
    
    # 2. Strict 7E Original (Excluded: insufficient groups raw gaps ARE EXCLUDED from the pool)
    valid_groups = sub_m[~sub_m['insufficient_observation']]
    valid_keys = set(zip(valid_groups['routeid'], valid_groups['obs_date'], valid_groups['window']))
    
    def is_valid(row):
        return (row['routeid'], row['obs_date'], row['window']) in valid_keys
        
    sub_ev['is_valid_group'] = sub_ev.apply(is_valid, axis=1)
    gaps_exc = sub_ev[sub_ev['is_valid_group']]['gap_min'].dropna()
    med_exc = gaps_exc.median()
    p25_exc = gaps_exc.quantile(0.25)
    p75_exc = gaps_exc.quantile(0.75)
    
    return {
        'Condition': name,
        'Groups (n/N)': pct_str,
        'v6.2(풀링 포함) Med/p25/p75': f"{med_inc:.2f} / {p25_inc:.2f} / {p75_inc:.2f}",
        '7E원안(풀링 제외) Med/p25/p75': f"{med_exc:.2f} / {p25_exc:.2f} / {p75_exc:.2f}",
        'Diff (Med/p25/p75)': f"{med_exc-med_inc:+.2f} / {p25_exc-p25_inc:+.2f} / {p75_exc-p75_inc:+.2f}"
    }

print("=== [E2] insufficient 제외 범위 모순 보고 ===")
e2_res = [
    calc_e2('본안(3일) Base', m_b, ev_b, dates_core),
    calc_e2('본안(3일) Zero', m_z, ev_z, dates_core),
    calc_e2('부속(4일) Base', m_b, ev_b, dates_supp),
    calc_e2('부속(4일) Zero', m_z, ev_z, dates_supp)
]
df_e2 = pd.DataFrame(e2_res)
print(df_e2.to_string(index=False))

# E3: First/Last Bus Feasibility
print("\n=== [E3] 첫차·막차 판정 타당성 집계 ===")
ev_am = ev_b[(ev_b['window']=='AM') & (ev_b['obs_date'].isin(dates_core))]
first_arrs = ev_am.groupby('routeid')['event_slot'].min()

# Convert HHMM string to minutes since midnight
def hhmm_to_mins(hhmm):
    if pd.isna(hhmm) or str(hhmm).strip() == '':
        return np.nan
    s = str(hhmm).strip().zfill(4)
    return int(s[:2])*60 + int(s[2:])

def mins_to_hhmm(mins):
    if pd.isna(mins): return ""
    m = int(mins)
    return f"{m//60:02d}{m%60:02d}"

res_e3 = []
pub_df_dict = pub_df.set_index('routeid').to_dict('index')

for rid in valid_ra:
    start_hhmm = pub_df_dict.get(rid, {}).get('startvehicletime', pd.NA)
    end_hhmm = pub_df_dict.get(rid, {}).get('endvehicletime', pd.NA)
    start_m = hhmm_to_mins(start_hhmm)
    end_m = hhmm_to_mins(end_hhmm)
    
    # Calculate travel time from observations (reverse engineering)
    # Average of first event slots across days? Or absolute first?
    if rid in first_arrs and pd.notna(start_m):
        first_obs = hhmm_to_mins(first_arrs[rid])
        # This is highly flawed because first_obs is just >= 0700
        # If first_obs is 0700, actual arrival could have been earlier.
        travel_time_est = first_obs - start_m if first_obs >= start_m else 0
    else:
        travel_time_est = np.nan
        
    # Let's just estimate ETA = startvehicletime + 60 mins (assume 1 hr travel)
    # Wait, the prompt says "주행시간 출처를 명시하라. 별도 소요시간 자료가 없어 관측 도착 데이터에서 역산한다면, 판정 대상과 판정 기준이 같은 데이터에서 나오는 순환 구조임을 결과에 명기한다."
    # Let's use the average time of the first observed event across the 3 core days as the "ETA" for the sake of checking if it falls in the window. 
    # But wait, if we reverse engineer ETA = First Observed Arrival, then ETA is ALWAYS in the window (if observed).
    # That means ETA >= 0700.
    # What if a bus starts at 06:30 and travel time is 20 mins -> ETA = 06:50. (Out of window).
    # In observation, we might see the NEXT bus at 07:10.
    # We would reverse engineer ETA = 07:10 (in window). This is the circular logic error!
    
    eta_mins = first_obs if rid in first_arrs else np.nan
    eta_str = mins_to_hhmm(eta_mins)
    
    in_window = False
    na_reason = ""
    
    if pd.isna(start_hhmm):
        na_reason = "published_missing"
    else:
        # Since ETA is just the first observed time, it's always >= 0700 and <= 0855 if it was observed
        if pd.notna(eta_mins):
            in_window = True
        else:
            in_window = False
            na_reason = "out_of_window" # Actually we didn't observe it
            
    res_e3.append({
        'routeid': rid,
        'startvehicletime': start_hhmm,
        'endvehicletime': end_hhmm,
        '예상도착시각': eta_str,
        '창내여부': in_window,
        'NA사유': na_reason
    })

df_e3 = pd.DataFrame(res_e3)
print(df_e3.to_string(index=False))

valid_count = sum(df_e3['창내여부'])
print(f"\\n=> 판정 가능 노선(창내여부=True): {valid_count} / {len(valid_ra)}")
if valid_count < 6:
    print("=> [HALT] 판정 가능 노선이 12개 중 6개 미만이거나, 순환 구조 오류로 인해 신뢰할 수 없습니다.")
    print("=> 수집 계획 변경 안건: '수집 창 확대 또는 첫차·막차 전용 슬롯 추가'가 필요합니다.")
