import sys
import json
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

# Try importing build_slot_labels
try:
    from src.collectors.arrival_slots import build_slot_labels
except ImportError as e:
    print(f"[Import] src.collectors.arrival_slots.build_slot_labels 실패: {e}. 로컬 정의 사용.")
    def build_slot_labels():
        slots = []
        for h in [7, 8, 17, 18]:
            for m in range(0, 60, 5):
                slots.append(f"{h:02d}{m:02d}")
        return sorted(slots)

def get_window(slot):
    if slot.startswith('07') or slot.startswith('08'): return 'AM'
    if slot.startswith('17') or slot.startswith('18'): return 'PM'
    return 'UNKNOWN'

def load_data():
    ledger_path = Path('evidence/arrival_ledger.csv')
    if not ledger_path.exists():
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}
    ledger = pd.read_csv(ledger_path)
    
    raw_dir = Path('evidence/arrival_raw')
    raw_data = []
    
    parse_stats = {
        'total_files': 0,
        'success': 0,
        'failed': 0,
        'fail_reasons': Counter(),
        'failed_files': [],
        'path_samples': []
    }
    
    files = list(raw_dir.rglob('*.json'))
    parse_stats['total_files'] = len(files)
    parse_stats['path_samples'] = [str(f) for f in files[:5]]
    
    for jf in files:
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            resp = data.get('response', {})
            body = resp.get('body', {})
            if isinstance(body, str):
                items = [] # Body is a string, probably error or empty
            else:
                items = body.get('items', {})
                if isinstance(items, dict):
                    items = items.get('item', [])
                elif isinstance(items, str):
                    items = []
                
            if isinstance(items, dict): 
                items = [items]
            elif not isinstance(items, list):
                items = []
            
            route_map = {}
            for it in items:
                if not isinstance(it, dict): continue
                rid = it.get('routeid')
                arr = it.get('arrtime')
                if rid and arr is not None:
                    arr = int(arr)
                    if rid not in route_map:
                        route_map[rid] = {'arrtimes': []}
                    route_map[rid]['arrtimes'].append(arr)
            
            parts = jf.stem.split('_')
            if len(parts) >= 3:
                slot = parts[-1]
                obs_date = jf.parent.name
                for rid, info in route_map.items():
                    arrs = info['arrtimes']
                    raw_data.append({
                        'obs_date': obs_date,
                        'slot_hhmm': slot,
                        'routeid': str(rid),
                        'arrtime_sec': min(arrs),
                        'n_items': len(arrs)
                    })
            parse_stats['success'] += 1
        except Exception as e:
            parse_stats['failed'] += 1
            reason = type(e).__name__
            parse_stats['fail_reasons'][reason] += 1
            parse_stats['failed_files'].append((str(jf), str(e)))
            
    raw_df = pd.DataFrame(raw_data)
    pub_path = Path('data/staged/route_service_hours.parquet')
    pub_df = pd.read_parquet(pub_path) if pub_path.exists() else pd.DataFrame()
        
    return ledger, raw_df, pub_df, parse_stats

def process_ledger(ledger):
    ledger = ledger.sort_values('called_at_kst')
    to_drop = []
    for obs_date, group in ledger.groupby('obs_date'):
        group = group.sort_values('called_at_kst')
        prev_time = None
        prev_idx = None
        for idx, row in group.iterrows():
            curr_time = pd.to_datetime(row['called_at_kst'])
            if prev_time is not None:
                diff = (curr_time - prev_time).total_seconds()
                if diff <= 120 and row['slot_hhmm'] != ledger.loc[prev_idx, 'slot_hhmm']:
                    to_drop.append(idx)
            prev_time = curr_time
            prev_idx = idx
    ledger = ledger.drop(index=to_drop)
    return ledger, len(to_drop)

def build_timeseries(ledger, raw_df, routes, zero_fill=False):
    slots = build_slot_labels()
    dates = ledger['obs_date'].unique()
    grid = pd.MultiIndex.from_product([dates, slots], names=['obs_date', 'slot_hhmm']).to_frame(index=False)
    grid['slot_hhmm'] = grid['slot_hhmm'].astype(str)
    ledger['slot_hhmm'] = ledger['slot_hhmm'].astype(str)
    
    df = pd.merge(grid, ledger[['obs_date', 'slot_hhmm', 'outcome']], on=['obs_date', 'slot_hhmm'], how='left')
    
    ts_data = []
    for _, row in df.iterrows():
        d, s, out = row['obs_date'], row['slot_hhmm'], row['outcome']
        w = get_window(s)
        
        if out == 'ok_with_items':
            raw_subset = raw_df[(raw_df['obs_date'] == d) & (raw_df['slot_hhmm'] == s)]
            present_routes = set(raw_subset['routeid'].values)
            for _, rr in raw_subset.iterrows():
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': rr['routeid'],
                    'arrtime_sec': rr['arrtime_sec'], 'n_items': rr['n_items'],
                    'collection_missing': False, 'route_absent': False
                })
            for r in set(routes) - present_routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': 0 if zero_fill else pd.NA, 'n_items': 0,
                    'collection_missing': False, 'route_absent': not zero_fill
                })
        elif out == 'ok_empty':
            for r in routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': 0 if zero_fill else pd.NA, 'n_items': 0,
                    'collection_missing': not zero_fill, 'route_absent': False
                })
        else:
            for r in routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': 0 if zero_fill else pd.NA, 'n_items': 0,
                    'collection_missing': not zero_fill, 'route_absent': False
                })
                
    ts_df = pd.DataFrame(ts_data)
    ts_df['arrtime_sec'] = ts_df['arrtime_sec'].astype('Int64')
    return ts_df

def detect_events_v1(ts_df):
    # 과거 로직 재현 (이벤트 수 대조용)
    events = []
    groups = ts_df.sort_values(['obs_date', 'slot_hhmm']).groupby(['routeid', 'obs_date', 'window'])
    for (rid, d, w), group in groups:
        prev_arr = None
        for i, row in group.iterrows():
            arr = row['arrtime_sec']
            if pd.notna(arr):
                if prev_arr is not None and arr > prev_arr:
                    events.append({'routeid': rid})
                prev_arr = arr
            else:
                if prev_arr is not None:
                    events.append({'routeid': rid})
                prev_arr = None
        if prev_arr is not None:
            events.append({'routeid': rid})
    return len(events)

def detect_events_v2(ts_df):
    events = []
    groups = ts_df.sort_values(['obs_date', 'slot_hhmm']).groupby(['routeid', 'obs_date', 'window'])
    
    for (rid, d, w), group in groups:
        prev_arr, prev_slot = None, None
        group = group.reset_index(drop=True)
        
        for i, row in group.iterrows():
            arr, slot = row['arrtime_sec'], row['slot_hhmm']
            col_missing, route_absent = row['collection_missing'], row['route_absent']
            
            if pd.notna(arr):
                if prev_arr is not None and arr > prev_arr:
                    events.append({'routeid': rid, 'obs_date': d, 'window': w, 'event_slot': prev_slot, 'arrtime_sec': prev_arr})
                prev_arr, prev_slot = arr, slot
            else:
                if col_missing:
                    # 절단 (이벤트 미발생)
                    prev_arr, prev_slot = None, None
                elif route_absent:
                    # 노선 부재 -> 도착으로 간주
                    if prev_arr is not None:
                        events.append({'routeid': rid, 'obs_date': d, 'window': w, 'event_slot': prev_slot, 'arrtime_sec': prev_arr})
                    prev_arr, prev_slot = None, None
                
        # Loop ends -> right-censored, DO NOT add event for prev_arr
            
    events_df = pd.DataFrame(events)
    if events_df.empty: return pd.DataFrame(), ts_df
    events_df = events_df.sort_values(['routeid', 'obs_date', 'window', 'event_slot'])
    
    def check_missing_adjacent(d, w, slot1, slot2, ts_group):
        sub = ts_group[(ts_group['slot_hhmm'] >= slot1) & (ts_group['slot_hhmm'] <= slot2)]
        return sub['collection_missing'].any()

    gap_data = []
    for (rid, d, w), group in events_df.groupby(['routeid', 'obs_date', 'window']):
        group = group.reset_index(drop=True)
        ts_group = ts_df[(ts_df['routeid'] == rid) & (ts_df['obs_date'] == d) & (ts_df['window'] == w)]
        
        # We need slot indices to calculate gap
        slots = build_slot_labels()
        
        for i in range(len(group)):
            if i == 0: 
                gap_data.append((pd.NA, False))
            else:
                slot_prev = group.loc[i-1, 'event_slot']
                slot_curr = group.loc[i, 'event_slot']
                
                s1_idx = slots.index(slot_prev)
                s2_idx = slots.index(slot_curr)
                gap_min = (s2_idx - s1_idx) * 5.0
                
                adj = check_missing_adjacent(d, w, slot_prev, slot_curr, ts_group)
                gap_data.append((gap_min, adj))
                
    events_df['gap_min'] = [x[0] for x in gap_data]
    events_df['gap_adjacent'] = [x[1] for x in gap_data]
    return events_df, ts_df

def aggregate_metrics(events_df, ts_df, routes_to_exclude=None):
    if events_df.empty: return pd.DataFrame()
    metrics = []
    
    # Apply filtering for route-level metrics
    if routes_to_exclude is None: routes_to_exclude = []
    
    for (rid, d, w), group in events_df.groupby(['routeid', 'obs_date', 'window']):
        if rid in routes_to_exclude: continue
        
        gaps = group['gap_min'].dropna()
        n_ev = len(group)
        insuff = n_ev < 4
        
        ts_group = ts_df[(ts_df['routeid'] == rid) & (ts_df['obs_date'] == d) & (ts_df['window'] == w)]
        n_multi_snapshots = len(ts_group[ts_group['n_items'] > 1])
        
        if not gaps.empty and not insuff:
            med, p25, p75 = gaps.median(), gaps.quantile(0.25), gaps.quantile(0.75)
            gap_adj_ratio = group['gap_adjacent'].mean()
        else:
            med, p25, p75, gap_adj_ratio = pd.NA, pd.NA, pd.NA, pd.NA
            
        metrics.append({
            'routeid': rid, 'obs_date': d, 'window': w, 'median_gap_min': med, 'p25': p25, 'p75': p75,
            'n_events': n_ev, 'n_multi_item_snapshots': n_multi_snapshots, 'insufficient_observation': insuff,
            'gap_adjacent_ratio': gap_adj_ratio
        })
    return pd.DataFrame(metrics)

def stop_level_metrics(events_df):
    if events_df.empty: return pd.DataFrame()
    # For the whole stop (all routes combined)
    # median-across-routes: all gaps
    # best-single-route: route with lowest median gap
    res = []
    for (d, w), group in events_df.groupby(['obs_date', 'window']):
        gaps = group['gap_min'].dropna()
        med_across = gaps.median() if not gaps.empty else pd.NA
        
        route_meds = group.groupby('routeid')['gap_min'].median().dropna()
        best_single = route_meds.min() if not route_meds.empty else pd.NA
        
        res.append({
            'obs_date': d, 'window': w,
            'median_across_routes': med_across,
            'best_single_route': best_single
        })
    return pd.DataFrame(res)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--commit', action='store_true')
    args = parser.parse_args()

    ledger, raw_df, pub_df, p_stats = load_data()
    if ledger.empty: return
    
    # We define total 15 routes manually or from all json?
    # Actually all unique routeids from raw_df + pub_df?
    # But wait, pub_df has 12 routes. The total is 15. We can just take all routes seen in raw_df + pub_df.
    routes = set(raw_df['routeid'].unique()) | set(pub_df['routeid'].unique())
    
    ledger, n_dropped = process_ledger(ledger)

    ts_base = build_timeseries(ledger, raw_df, routes, zero_fill=False)
    ts_zero = build_timeseries(ledger, raw_df, routes, zero_fill=True)
    
    old_ev_count = detect_events_v1(ts_base)
    ev_base, ts_base = detect_events_v2(ts_base)
    ev_zero, ts_zero = detect_events_v2(ts_zero)
    
    exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']
    
    # For route accounting table
    route_acct = []
    for r in sorted(routes):
        r_ts = ts_base[ts_base['routeid'] == r]
        r_ev = ev_base[ev_base['routeid'] == r]
        raw_slots = len(r_ts[(r_ts['arrtime_sec'].notna())])
        ev_cnt = len(r_ev)
        gr_cnt = len(r_ev.groupby(['obs_date', 'window']))
        
        reason = ""
        if gr_cnt == 0:
            if r in exc_routes and raw_slots == 0:
                reason = "7A' 누락으로 수집 미시도"
            else:
                reason = "관측 빈도 부족 (이벤트 0)"
                
        route_acct.append({'routeid': r, 'raw_slots': raw_slots, 'events': ev_cnt, 'groups': gr_cnt, 'reason': reason})
    route_acct_df = pd.DataFrame(route_acct)
    
    # C1. Filter evaluation
    metrics_all = aggregate_metrics(ev_base, ts_base, routes_to_exclude=[])
    metrics_base = aggregate_metrics(ev_base, ts_base, exc_routes)

    dates_core = ['2026-09-07', '2026-09-08', '2026-09-09']
    dates_supp = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
    
    # 2x2 Sensitivity
    sens_res = []
    for name, ts_df, ev_df in [('Base', ts_base, ev_base), ('Zero-Fill', ts_zero, ev_zero)]:
        for w_name, w_dates in [('Core(3일)', dates_core), ('Supp(4일)', dates_supp)]:
            sub_ev = ev_df[ev_df['obs_date'].isin(w_dates)]
            sub_ts = ts_df[ts_df['obs_date'].isin(w_dates)]
            m = aggregate_metrics(sub_ev, sub_ts, exc_routes)
            if not m.empty:
                sens_res.append({
                    'Condition': f"{name} / {w_name}",
                    'Median Gap': m['median_gap_min'].median(),
                    'Groups': len(m),
                    'Insuff %': f"{m['insufficient_observation'].mean()*100:.1f}%"
                })
            else:
                sens_res.append({'Condition': f"{name} / {w_name}", 'Median Gap': pd.NA, 'Groups': 0, 'Insuff %': "N/A"})
    sens_df = pd.DataFrame(sens_res)

    # Output prep
    if not pub_df.empty: pub_df['headway_published_min'] = pub_df['intervaltime']
    else: pub_df = pd.DataFrame({'routeid': [], 'headway_published_min': []})

    def prep_out(m_df):
        if m_df.empty: return m_df
        odf = m_df.merge(pub_df[['routeid', 'headway_published_min']], on='routeid', how='left')
        odf['crosscheck_available'] = ~odf['routeid'].isin(exc_routes)
        def calc_agree(row):
            if row['insufficient_observation']: return 'observed_insufficient'
            if pd.isna(row['headway_published_min']) or pd.isna(row['median_gap_min']): return 'published_missing'
            if abs(row['median_gap_min'] - row['headway_published_min']) <= 5: return 'agree_within_5min'
            return 'disagree'
        odf['headway_source_agreement'] = odf.apply(calc_agree, axis=1)
        return odf
        
    ev_core = ev_base[ev_base['obs_date'].isin(dates_core)]
    out_core = prep_out(aggregate_metrics(ev_core, ts_base[ts_base['obs_date'].isin(dates_core)], exc_routes))
    
    if not out_core.empty:
        out_core['first_bus_ok'] = pd.Series(pd.NA, dtype='boolean')
        out_core['last_bus_ok'] = pd.Series(pd.NA, dtype='boolean')
        out_core['headway_ok'] = (out_core['headway_source_agreement'] == 'agree_within_5min').astype('boolean')
        mask = out_core['headway_source_agreement'].isin(['observed_insufficient', 'published_missing'])
        out_core.loc[mask, 'headway_ok'] = pd.NA

    # Stop metrics
    stop_met = stop_level_metrics(ev_core)

    if args.dry_run:
        print("=== C3. 파싱 회계 ===")
        print(f"- Total JSON: {p_stats['total_files']} | Success: {p_stats['success']} | Failed: {p_stats['failed']}")
        if p_stats['failed'] > 0:
            print(f"- Fail reasons: {dict(p_stats['fail_reasons'])}")
        print("- obs_date 경로 추출 검증 샘플 5개:")
        for sp in p_stats['path_samples']: print(f"  {sp}")
        print("\n[노선별 회계표]")
        print(route_acct_df.to_string(index=False))

        print("\n=== C2. 이벤트 수정 전후 대조 ===")
        print(f"- 수정 전(NA무조건 이벤트, 끝단 이벤트): {old_ev_count}건")
        print(f"- 수정 후(route_absent 분리, 우측절단 제외): {len(ev_base)}건")

        print("\n=== C1. 노선 제외 필터링 대조 ===")
        print(f"- 필터링 전: 그룹 {len(metrics_all)}건, 이벤트 {ev_base['routeid'].isin(routes).sum()}건") # Wait, sum is just total
        print(f"- 필터링 후: 그룹 {len(metrics_base)}건, 이벤트 {ev_base[~ev_base['routeid'].isin(exc_routes)].shape[0]}건")

        print("\n=== C4. 민감도 2x2 ===")
        print(sens_df.to_string(index=False))
        # 결론 판단
        b_c = sens_df.iloc[0]['Median Gap']
        z_c = sens_df.iloc[2]['Median Gap']
        if pd.notna(b_c) and pd.notna(z_c) and abs(b_c - z_c) > 5:
            print("-> 결론: 0 처리에 따라 중앙값이 5분 이상 변동하여 결론이 뒤집힘.")
        else:
            print("-> 결론: 0 처리에 따른 중앙값 변동이 미미하여 결론이 뒤집히지 않음.")

        print("\n=== C5. 정류소 단위 지표 (Core) ===")
        print(stop_met.to_string(index=False))

        print("\n=== 교차검증 분포 (Core Base) ===")
        if not out_core.empty: print(out_core['headway_source_agreement'].value_counts())
        
        print("\n=== 사람이 결정할 사항 ===")
        print("1. insufficient_observation 비율 과도 시 그룹 단위(노선×일자×창) 상향 논의")
        print("2. first_bus_ok / last_bus_ok 판정용 '기점~정류소 주행시간' 보정 규칙 수립")
        print("3. intervaltime 단위('분')에 대한 공식 문서 근거 확보")
        
    if args.commit:
        if not out_core.empty:
            pq_path = 'data/staged/headway_observed.parquet'
            csv_path = 'exports/headway_crosscheck.csv'
            print(f"Writing {pq_path} ({len(out_core)} rows, {len(out_core.columns)} cols)")
            out_core.to_parquet(pq_path, index=False)
            print(f"Writing {csv_path}")
            out_core.to_csv(csv_path, index=False)
        
        md_path = 'docs/headway_limits.md'
        print(f"Writing {md_path}")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# 관측 배차 산출 및 교차검증 한계점\n\n(본문 생략, dry-run 시 사전 출력됨)")
            
if __name__ == '__main__':
    main()
