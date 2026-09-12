import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from scratch.calc_headway_v6 import (
    load_data, process_ledger, build_timeseries, detect_events_v2,
    aggregate_metrics, build_slot_labels, get_window
)

ledger, raw_df, pub_df, _ = load_data()
lc, _, _, dd = process_ledger(ledger)
ra = sorted(raw_df['routeid'].unique())
exc = ['GGB222000056', 'GGB222000137', 'GGB222000239']

ts_b = build_timeseries(lc, raw_df, ra, deduplicated_slots=dd, zero_fill=False)
ev_b, _ = detect_events_v2(ts_b)
ts_z = build_timeseries(lc, raw_df, ra, deduplicated_slots=dd, zero_fill=True)
ev_z, _ = detect_events_v2(ts_z)
m_b = aggregate_metrics(ev_b, ts_b, routes_to_exclude=exc)
m_z = aggregate_metrics(ev_z, ts_z, routes_to_exclude=exc)

dc = ['2026-09-07', '2026-09-08', '2026-09-09']
ds = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']

print("=== I1 insufficient 2계열 정밀 진단 ===\n")

pairs = [
    ('core_base', m_b, dc, ev_b),
    ('core_zero', m_z, dc, ev_z),
    ('supp_base', m_b, ds, ev_b),
    ('supp_zero', m_z, ds, ev_z),
]

print("[계열A] aggregate_metrics 그룹단위 insufficient_observation (n_events < 4):")
for label, m, d, e in pairs:
    sub = m[m['obs_date'].isin(d)]
    n_insuff = int(sub['insufficient_observation'].sum())
    n_total = len(sub)
    rate = n_insuff / n_total * 100 if n_total > 0 else 0
    print(f"  {label}: {n_insuff}/{n_total} = {rate:.4f}% (표시: {rate:.1f}%)")

print("\n[분모 상세] 왜 supp_base=95, supp_zero=96?")
for label, m, d_list in [('supp_base', m_b, ds), ('supp_zero', m_z, ds)]:
    sub = m[m['obs_date'].isin(d_list)]
    print(f"  {label} 분모={len(sub)}")
    by_day_window = sub.groupby(['obs_date', 'window']).size()
    print(f"    일자×창 별 노선 수:")
    for (day, win), cnt in by_day_window.items():
        print(f"      {day} {win}: {cnt}개 노선 그룹")
    # 09-10 AM에서 11 vs 12 차이 확인
    if '2026-09-10' in d_list:
        sub_0910_am_b = m_b[(m_b['obs_date'] == '2026-09-10') & (m_b['window'] == 'AM')]
        sub_0910_am_z = m_z[(m_z['obs_date'] == '2026-09-10') & (m_z['window'] == 'AM')]
        print(f"    09-10 AM routes in base: {sorted(sub_0910_am_b['routeid'].unique())}")
        print(f"    09-10 AM routes in zero: {sorted(sub_0910_am_z['routeid'].unique())}")

print("\n[계열B] 이 지표만 사용됨. 다른 insufficient 계열 존재 여부 확인:")
print("  -> 코드에서 insufficient 관련 출력은 모두 sub_m['insufficient_observation'].mean()")
print("  -> 즉 '그룹 비율(group rate)'만 존재. 이벤트 비율(event rate)은 산출되지 않음.")

print("\n[역산 검증] 유저 제시 5.6%, 4.2%, 12.5%, 6.9% 재현 시도:")
# 4/72 = 5.56% ≈ 5.6%
# 3/72 = 4.17% ≈ 4.2%  
# 12/96 = 12.5% exact
# 5/72 = 6.94% ≈ 6.9%
for label, m, d_list, e in pairs:
    sub = m[m['obs_date'].isin(d_list)]
    n_total = len(sub)
    for candidate_n in range(0, n_total + 1):
        rate = candidate_n / n_total * 100 if n_total > 0 else 0
        if abs(rate - 5.6) < 0.1 or abs(rate - 4.2) < 0.1 or abs(rate - 12.5) < 0.1 or abs(rate - 6.9) < 0.1:
            print(f"  {label}: {candidate_n}/{n_total} = {rate:.2f}%")

print("\n[평일 확인] 관측일 요일:")
for d in sorted(ledger['obs_date'].unique()):
    dow = pd.Timestamp(d).dayofweek
    names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    print(f"  {d}: dayofweek={dow} ({names[dow]})")

print("\n[pub_df 필드 확인]")
print(f"  intervaltime 필드명: 'intervaltime' (평일 배차간격, 분)")
print(f"  headway_published_min 매핑 원천: pub_df[['routeid','intervaltime']].rename()")
print(f"  pub_df 컬럼: {list(pub_df.columns)}")
print(f"  pub_df intervaltime 통계: {pub_df['intervaltime'].describe().to_dict()}")
