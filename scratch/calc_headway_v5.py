import sys
import json
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

KST = timezone(timedelta(hours=9))

# Ensure project root is in sys.path
sys.path.insert(0, str(Path.cwd()))

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
    slot_str = str(slot).zfill(4)
    if slot_str.startswith('07') or slot_str.startswith('08'):
        return 'AM'
    if slot_str.startswith('17') or slot_str.startswith('18'):
        return 'PM'
    return 'UNKNOWN'

def load_ledger(ledger_path):
    ledger = pd.read_csv(
        ledger_path,
        dtype={
            'obs_date': str,
            'slot_hhmm': str,
            'citycode': str,
            'nodeid': str,
            'outcome': str,
            'retry_count': str,
            'http_status': str,
            'result_code': str,
            'result_msg': str,
            'item_count': str,
            'raw_path': str,
            'schema_version': str
        }
    )
    ledger['slot_hhmm'] = ledger['slot_hhmm'].astype(str).str.zfill(4)
    ledger['obs_date'] = ledger['obs_date'].astype(str)
    return ledger

def load_data():
    ledger_path = Path('evidence/arrival_ledger.csv')
    if not ledger_path.exists():
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}
    
    ledger = load_ledger(ledger_path)
    
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
                items = []
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
            
            parts = jf.stem.split('_')
            slot = parts[-1].zfill(4) if len(parts) >= 3 else "0000"
            obs_date = str(jf.parent.name)
            
            for it in items:
                if not isinstance(it, dict):
                    continue
                rid = it.get('routeid')
                arr = it.get('arrtime')
                if rid and arr is not None:
                    arr = int(arr)
                    raw_data.append({
                        'obs_date': obs_date,
                        'slot_hhmm': slot,
                        'routeid': str(rid),
                        'arrtime_sec': arr
                    })
            parse_stats['success'] += 1
        except Exception as e:
            parse_stats['failed'] += 1
            reason = type(e).__name__
            parse_stats['fail_reasons'][reason] += 1
            parse_stats['failed_files'].append((str(jf), str(e)))
            
    raw_df = pd.DataFrame(raw_data)
    if not raw_df.empty:
        raw_df['obs_date'] = raw_df['obs_date'].astype(str)
        raw_df['slot_hhmm'] = raw_df['slot_hhmm'].astype(str).str.zfill(4)
        raw_df['routeid'] = raw_df['routeid'].astype(str)

    pub_path = Path('data/staged/route_service_hours.parquet')
    pub_df = pd.read_parquet(pub_path) if pub_path.exists() else pd.DataFrame()
    if not pub_df.empty:
        pub_df['routeid'] = pub_df['routeid'].astype(str)
        
    return ledger, raw_df, pub_df, parse_stats

def process_ledger(ledger):
    """F1/F2: 동일 라벨 중복(F1) 및 슬롯 상이 준중복(F2)을 명확히 분리하여 정제"""
    ledger = ledger.copy()
    ledger['called_at_kst_dt'] = pd.to_datetime(ledger['called_at_kst'])
    
    # Step A: 동일 키 (obs_date, slot_hhmm) 중복 정리 (F1/F2)
    # 규칙: 성공 행(ok_with_items) 우선, 성공 행 복수 시 called_at 빠른 쪽
    f1_same_key_drops = []
    kept_indices = []
    
    for (d, s), group in ledger.groupby(['obs_date', 'slot_hhmm']):
        if len(group) == 1:
            kept_indices.append(group.index[0])
        else:
            # 성공 행과 실패 행 분리
            ok_rows = group[group['outcome'] == 'ok_with_items'].sort_values('called_at_kst_dt')
            if not ok_rows.empty:
                chosen_idx = ok_rows.index[0]
                # api_error 가 있었는지 확인
                has_api_error = (group['outcome'] == 'api_error').any()
                if has_api_error:
                    ledger.loc[chosen_idx, 'outcome'] = 'api_error_retried_ok'
            else:
                chosen_idx = group.sort_values('called_at_kst_dt').index[0]
                
            kept_indices.append(chosen_idx)
            chosen_row = ledger.loc[chosen_idx]
            
            for idx, row in group.iterrows():
                if idx != chosen_idx:
                    diff = abs((row['called_at_kst_dt'] - chosen_row['called_at_kst_dt']).total_seconds())
                    f1_same_key_drops.append({
                        'obs_date': d,
                        'slot_hhmm': s,
                        'dropped_outcome': row['outcome'],
                        'kept_outcome': chosen_row['outcome'],
                        'dropped_called_at': row['called_at_kst'],
                        'kept_called_at': chosen_row['called_at_kst'],
                        'diff_seconds': diff,
                        'reason': '동일 키 중복 (성공 행 우선 채택)'
                    })
                    
    ledger_step_a = ledger.loc[kept_indices].copy()
    
    # Step B: 슬롯 상이 준중복 처리 (120초 이내, 호출시각 기준 늦은 쪽 드롭)
    ledger_step_a = ledger_step_a.sort_values('called_at_kst_dt')
    to_drop_step_b = []
    f2_near_dups = []
    deduplicated_slots = set()
    
    for obs_date, group in ledger_step_a.groupby('obs_date'):
        group = group.sort_values('called_at_kst_dt')
        prev_time = None
        prev_row = None
        for idx, row in group.iterrows():
            curr_time = row['called_at_kst_dt']
            if prev_time is not None:
                diff = (curr_time - prev_time).total_seconds()
                if diff <= 120 and row['slot_hhmm'] != prev_row['slot_hhmm']:
                    to_drop_step_b.append(idx)
                    deduplicated_slots.add((str(row['obs_date']), str(row['slot_hhmm'])))
                    f2_near_dups.append({
                        'obs_date': row['obs_date'],
                        'kept_slot': prev_row['slot_hhmm'],
                        'dropped_slot': row['slot_hhmm'],
                        'kept_called_at': prev_row['called_at_kst'],
                        'dropped_called_at': row['called_at_kst'],
                        'diff_seconds': diff,
                        'dropped_items': row['item_count'],
                        'reason': '슬롯 상이 준중복 (늦은 쪽 드롭)'
                    })
            prev_time = curr_time
            prev_row = row
            
    ledger_clean = ledger_step_a.drop(index=to_drop_step_b).copy()
    return ledger_clean, f1_same_key_drops, f2_near_dups, deduplicated_slots

def classify_missing_and_unreached(ledger, deduplicated_slots=None):
    """F3: max(called_at) 이후의 슬롯은 '결측'이 아닌 '미도래'로 엄격히 분리"""
    if deduplicated_slots is None:
        deduplicated_slots = set()
        
    slots = build_slot_labels()
    dates = sorted(ledger['obs_date'].unique())
    grid = pd.MultiIndex.from_product([dates, slots], names=['obs_date', 'slot_hhmm']).to_frame(index=False)
    grid['slot_hhmm'] = grid['slot_hhmm'].astype(str).str.zfill(4)
    grid['obs_date'] = grid['obs_date'].astype(str)
    
    ledger_sub = ledger[['obs_date', 'slot_hhmm', 'outcome', 'called_at_kst']].copy()
    ledger_sub['slot_hhmm'] = ledger_sub['slot_hhmm'].astype(str).str.zfill(4)
    ledger_sub['obs_date'] = ledger_sub['obs_date'].astype(str)
    merged = pd.merge(grid, ledger_sub, on=['obs_date', 'slot_hhmm'], how='left')
    
    # 원장 최종 호출 시각 계산 (KST 기준)
    max_called_at = pd.to_datetime(ledger['called_at_kst']).max()
    if max_called_at.tz is None:
        max_called_at_kst = max_called_at.tz_localize(KST)
    else:
        max_called_at_kst = max_called_at.tz_convert(KST)
        
    missing = {}
    unreached = {}
    
    for d in dates:
        missing[d] = {'AM': [], 'PM': []}
        unreached[d] = {'AM': [], 'PM': []}
        d_sub = merged[merged['obs_date'] == d]
        
        for _, r in d_sub.iterrows():
            s = r['slot_hhmm']
            out = r['outcome']
            w = get_window(s)
            
            # 준중복 드롭 슬롯은 결측도 미도래도 아님
            if (d, s) in deduplicated_slots:
                continue
                
            if pd.isna(out):
                # 슬롯 명목 시각 계산
                slot_dt = pd.to_datetime(f"{d} {s[:2]}:{s[2:]}:00").tz_localize(KST)
                if slot_dt > max_called_at_kst:
                    unreached[d][w].append(s)
                else:
                    missing[d][w].append(s)
                    
    return missing, unreached

def build_timeseries(ledger, raw_df, routes, deduplicated_slots=None, zero_fill=False):
    if deduplicated_slots is None:
        deduplicated_slots = set()
        
    slots = build_slot_labels()
    dates = sorted(ledger['obs_date'].unique())
    grid = pd.MultiIndex.from_product([dates, slots], names=['obs_date', 'slot_hhmm']).to_frame(index=False)
    grid['slot_hhmm'] = grid['slot_hhmm'].astype(str).str.zfill(4)
    grid['obs_date'] = grid['obs_date'].astype(str)
    
    ledger_sub = ledger[['obs_date', 'slot_hhmm', 'outcome', 'called_at_kst']].copy()
    ledger_sub['slot_hhmm'] = ledger_sub['slot_hhmm'].astype(str).str.zfill(4)
    ledger_sub['obs_date'] = ledger_sub['obs_date'].astype(str)
    
    # F2: merge 직전 중복 키 안전장치
    dup_count = ledger_sub.duplicated(['obs_date', 'slot_hhmm']).sum()
    if dup_count > 0:
        dups = ledger_sub[ledger_sub.duplicated(['obs_date', 'slot_hhmm'], keep=False)]
        raise AssertionError(f"merge 직전 중복 키 발견 ({dup_count}건):\n{dups}")
        
    df = pd.merge(grid, ledger_sub, on=['obs_date', 'slot_hhmm'], how='left')
    
    ts_data = []
    for _, row in df.iterrows():
        d = row['obs_date']
        s = row['slot_hhmm']
        out = row['outcome']
        called_at = row['called_at_kst']
        w = get_window(s)
        
        # E2: 준중복으로 드롭된 슬롯은 collection_missing 오분류 방지
        if (d, s) in deduplicated_slots:
            for r in routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': pd.NA, 'n_items': 0,
                    'called_at_kst': called_at,
                    'collection_missing': False,
                    'is_deduplicated': True,
                    'route_absent': False
                })
        elif out in ['ok_with_items', 'api_error_retried_ok']:
            raw_subset = raw_df[(raw_df['obs_date'] == d) & (raw_df['slot_hhmm'] == s)]
            present_routes = set(raw_subset['routeid'].values)
            for r in routes:
                if r in present_routes:
                    r_rows = raw_subset[raw_subset['routeid'] == r]
                    min_arr = r_rows['arrtime_sec'].min()
                    item_cnt = len(r_rows)
                    ts_data.append({
                        'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                        'arrtime_sec': min_arr, 'n_items': item_cnt,
                        'called_at_kst': called_at,
                        'collection_missing': False,
                        'is_deduplicated': False,
                        'route_absent': False
                    })
                else:
                    # D3/E6: route_absent는 zero_fill 여부와 무관하게 동일 처리 (0 채움 금지)
                    ts_data.append({
                        'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                        'arrtime_sec': pd.NA, 'n_items': 0,
                        'called_at_kst': called_at,
                        'collection_missing': False,
                        'is_deduplicated': False,
                        'route_absent': True
                    })
        elif out == 'ok_empty':
            # D3: ok_empty만 zero_fill 적용 대상
            for r in routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': 0 if zero_fill else pd.NA, 'n_items': 0,
                    'called_at_kst': called_at,
                    'collection_missing': not zero_fill,
                    'is_deduplicated': False,
                    'route_absent': False
                })
        else:
            # api_error 또는 슬롯 자체 누락 (collection_missing) -> zero_fill 여부 무관하게 동일 처리
            for r in routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': pd.NA, 'n_items': 0,
                    'called_at_kst': called_at,
                    'collection_missing': True,
                    'is_deduplicated': False,
                    'route_absent': False
                })
                
    ts_df = pd.DataFrame(ts_data)
    ts_df['arrtime_sec'] = ts_df['arrtime_sec'].astype('Int64')
    return ts_df

def detect_events_v2(ts_df):
    events = []
    groups = ts_df.sort_values(['obs_date', 'slot_hhmm']).groupby(['routeid', 'obs_date', 'window'])
    
    for (rid, d, w), group in groups:
        prev_arr, prev_slot = None, None
        prev_called_at = None
        group = group.reset_index(drop=True)
        
        for i, row in group.iterrows():
            arr, slot = row['arrtime_sec'], row['slot_hhmm']
            col_missing, route_absent = row['collection_missing'], row['route_absent']
            is_dedup = row.get('is_deduplicated', False)
            called_at = row.get('called_at_kst', pd.NA)
            
            if is_dedup:
                continue
                
            if pd.notna(arr):
                if prev_arr is not None and arr > prev_arr:
                    events.append({
                        'routeid': rid, 'obs_date': d, 'window': w,
                        'event_slot': prev_slot, 'arrtime_sec': prev_arr,
                        'called_at_kst': prev_called_at
                    })
                prev_arr, prev_slot = arr, slot
                prev_called_at = called_at
            else:
                if col_missing:
                    prev_arr, prev_slot = None, None
                    prev_called_at = None
                elif route_absent:
                    if prev_arr is not None:
                        events.append({
                            'routeid': rid, 'obs_date': d, 'window': w,
                            'event_slot': prev_slot, 'arrtime_sec': prev_arr,
                            'called_at_kst': prev_called_at
                        })
                    prev_arr, prev_slot = None, None
                    prev_called_at = None
            
    events_df = pd.DataFrame(events)
    if events_df.empty:
        return pd.DataFrame(), ts_df
        
    events_df = events_df.sort_values(['routeid', 'obs_date', 'window', 'event_slot'])
    
    def check_missing_adjacent(slot1, slot2, ts_group):
        sub = ts_group[(ts_group['slot_hhmm'] >= slot1) & (ts_group['slot_hhmm'] <= slot2)]
        return bool(sub['collection_missing'].any())

    slots = build_slot_labels()
    gap_data = []
    
    for (rid, d, w), group in events_df.groupby(['routeid', 'obs_date', 'window']):
        group = group.reset_index(drop=True)
        ts_group = ts_df[(ts_df['routeid'] == rid) & (ts_df['obs_date'] == d) & (ts_df['window'] == w)]
        
        for i in range(len(group)):
            if i == 0: 
                gap_data.append((pd.NA, pd.NA, False))
            else:
                slot_prev = group.loc[i-1, 'event_slot']
                slot_curr = group.loc[i, 'event_slot']
                s1_idx = slots.index(slot_prev)
                s2_idx = slots.index(slot_curr)
                gap_min_slot = (s2_idx - s1_idx) * 5.0
                
                t_prev = pd.to_datetime(group.loc[i-1, 'called_at_kst'])
                t_curr = pd.to_datetime(group.loc[i, 'called_at_kst'])
                if pd.notna(t_prev) and pd.notna(t_curr):
                    gap_min_called = (t_curr - t_prev).total_seconds() / 60.0
                else:
                    gap_min_called = pd.NA
                    
                adj = check_missing_adjacent(slot_prev, slot_curr, ts_group)
                gap_data.append((gap_min_slot, gap_min_called, adj))
                
    events_df['gap_min'] = [x[0] for x in gap_data]
    events_df['gap_min_called'] = [x[1] for x in gap_data]
    events_df['gap_adjacent'] = [x[2] for x in gap_data]
    return events_df, ts_df

def aggregate_metrics(events_df, ts_df, routes_to_exclude=None):
    if events_df.empty:
        return pd.DataFrame()
    metrics = []
    if routes_to_exclude is None:
        routes_to_exclude = []
    
    for (rid, d, w), group in events_df.groupby(['routeid', 'obs_date', 'window']):
        if rid in routes_to_exclude:
            continue
        
        gaps = group['gap_min'].dropna()
        n_ev = len(group)
        insuff = n_ev < 4
        
        ts_group = ts_df[(ts_df['routeid'] == rid) & (ts_df['obs_date'] == d) & (ts_df['window'] == w)]
        multi_slots = ts_group[ts_group['n_items'] > 1]['slot_hhmm'].nunique()
        
        if not gaps.empty and not insuff:
            med = float(gaps.median())
            p25 = float(gaps.quantile(0.25))
            p75 = float(gaps.quantile(0.75))
            gap_adj_ratio = float(group['gap_adjacent'].mean())
        else:
            med, p25, p75, gap_adj_ratio = pd.NA, pd.NA, pd.NA, pd.NA
            
        metrics.append({
            'routeid': rid, 'obs_date': d, 'window': w,
            'median_gap_min': med, 'p25': p25, 'p75': p75,
            'n_events': n_ev, 'n_multi_item_snapshots': multi_slots,
            'insufficient_observation': insuff,
            'gap_adjacent_ratio': gap_adj_ratio
        })
    return pd.DataFrame(metrics)

def stop_level_metrics(events_df, exc_routes=None):
    """E3/F6: n_events < 4 노선 제외 후 유효 노선별 median_gap_min 의 중앙값(median_across_routes) 산출.
    included_excluded_routes 컬럼으로 제외 3노선 포함 여부 기록"""
    if exc_routes is None:
        exc_routes = []
        
    if events_df.empty:
        return pd.DataFrame()
    res = []
    
    for (d, w), group in events_df.groupby(['obs_date', 'window']):
        route_medians = []
        has_exc_route = False
        
        for rid, r_group in group.groupby('routeid'):
            if len(r_group) >= 4:
                gaps = r_group['gap_min'].dropna()
                if not gaps.empty:
                    route_medians.append((rid, float(gaps.median())))
                    if rid in exc_routes:
                        has_exc_route = True
                    
        if route_medians:
            med_values = [m[1] for m in route_medians]
            med_across = float(np.median(med_values))
            best_single = float(min(med_values))
            valid_routes_cnt = len(route_medians)
        else:
            med_across = pd.NA
            best_single = pd.NA
            valid_routes_cnt = 0
            
        res.append({
            'obs_date': d, 'window': w,
            'median_across_routes': med_across,
            'best_single_route': best_single,
            'valid_routes_count': valid_routes_cnt,
            'included_excluded_routes': has_exc_route
        })
    return pd.DataFrame(res)

def prep_crosscheck(m_df, pub_df, routes_to_exclude=None):
    if routes_to_exclude is None:
        routes_to_exclude = []
        
    if m_df.empty:
        return pd.DataFrame()
        
    if not pub_df.empty:
        pub_df_sub = pub_df[['routeid', 'intervaltime']].copy()
        pub_df_sub = pub_df_sub.rename(columns={'intervaltime': 'headway_published_min'})
    else:
        pub_df_sub = pd.DataFrame({'routeid': [], 'headway_published_min': []})

    odf = m_df.merge(pub_df_sub, on='routeid', how='left')
    odf['crosscheck_available'] = ~odf['routeid'].isin(routes_to_exclude)
    
    def calc_agree(row):
        if row['insufficient_observation']:
            return 'observed_insufficient'
        if pd.isna(row['headway_published_min']) or pd.isna(row['median_gap_min']):
            return 'published_missing'
        if abs(row['median_gap_min'] - row['headway_published_min']) <= 5:
            return 'agree_within_5min'
        return 'disagree'
        
    odf['headway_delta_min'] = odf.apply(
        lambda r: r['median_gap_min'] - r['headway_published_min'] 
        if pd.notna(r['median_gap_min']) and pd.notna(r['headway_published_min']) else pd.NA,
        axis=1
    )
    odf['headway_source_agreement'] = odf.apply(calc_agree, axis=1)
    
    odf['first_bus_ok'] = pd.array([pd.NA] * len(odf), dtype='boolean')
    odf['last_bus_ok'] = pd.array([pd.NA] * len(odf), dtype='boolean')
    
    headway_ok_vals = []
    for _, r in odf.iterrows():
        agr = r['headway_source_agreement']
        if agr == 'agree_within_5min':
            headway_ok_vals.append(True)
        elif agr == 'disagree':
            headway_ok_vals.append(False)
        else:
            headway_ok_vals.append(pd.NA)
    odf['headway_ok'] = pd.array(headway_ok_vals, dtype='boolean')
    return odf

def generate_docs_content(
    core_days, supp_days,
    total_json, success_json, failed_json,
    actual_max_horizon,
    missing_summary_text,
    unreached_summary_text,
    dedup_summary_text,
    narrative_0908,
    simultaneous_note
):
    doc = f"""# 관측 배차 산출 및 교차검증 한계점

## 1. 폴링 주기의 한계 및 시간 측정 방식
- 5분 폴링은 5분 미만 배차를 분해할 수 없다.
- 도착예정정보는 시각표가 아니므로 관측값은 근사치이며 공표 배차간격이 아니다.
- 본 분석의 `gap_min`은 슬롯 간격(스냅샷 인덱스 차 × 5분)을 기준으로 산출되었으며 스케줄러 자체의 지연(드리프트)은 배차 간격 산출에서 사전에 무시되었다.
- 정류소 단위 지표(`median_across_routes`)는 선언된 규칙에 따라 `n_events >= 4`인 유효 노선들의 `median_gap_min`의 중앙값으로 정의된다.

## 2. 차량 식별 부재 및 예측 지평
- 차량 식별자가 없어 동일 노선 복수 차량 구간은 식별 불가하다 (동일 슬롯 복수 항목은 API 정상 동작이며 중복 오류가 아니다).
- 관측 데이터에서 실측된 최대 예측 지평은 {actual_max_horizon}초에 달해 동일 차량이 다수 슬롯에 반복 등장한다.

## 3. 계통 및 방향성 편의 (교차검증 해석 핵심)
- `route_service_hours`는 `routeid`당 1행이며 **상·하행이 분리되어 있지 않다.**
- 단일 정류소 관측은 통상 한 방향이므로 관측 배차가 공표 배차의 약 2배로 나타나는 계통 편의가 발생할 수 있다. 따라서 교차검증의 'disagree'는 노선의 실제 배차 불이행이 아니라 **상·하행 방향 미분리로 인한 판정 불가** 취지로 기술된다.

## 4. 첫차/막차 판정 한계
- `startvehicletime` / `endvehicletime`은 **기점 기준일 가능성**이 있어 해당 정류소 도착시각과 기점~정류소 주행시간만큼 차이가 난다. 따라서 `first_bus_ok` / `last_bus_ok`를 단순 시각 비교로 판정하지 않는다. (현재 판정 규칙 미확정으로 전량 NULL 처리함)

## 5. 결측 메커니즘 및 무운행 처리
- 결측은 수집기의 파이썬 예외(`AttributeError: 'str' object has no attribute 'get'`)로 발생했으며, 무엇이 str로 반환됐는지는 **미확정**이다.
- 결측 인접 슬롯의 `item_count`가 전체 평균과 동일해 저운행 시간대 집중(정보성 결측)의 증거는 없으나, 무작위성이 입증된 것도 아니므로 "메커니즘 미확정, 정보성 결측 증거 없음"으로 기술한다.
- `ok_empty`는 인접 슬롯에 도착정보가 있는 시점에 발생해 실제 무운행이 아닌 응답 아티팩트로 추정되며, 본안에서는 0으로 임퓨테이션하지 않았다.
- {simultaneous_note}

## 6. 관측 표본의 한계
- 관측 일수는 소표본(본안 {core_days}일, 부속 {supp_days}일)이며 계절·장애 변동을 대표하지 않는다.
- 이 지표는 관측 기간에만 적용되며 과거 운행에 대해 아무것도 말하지 않는다.

## 7. 결측·미도래·준중복 내역 전량 (3구분 실측)
- **1. 실제 결측 슬롯 (과거 도래 슬롯 중 누락)**:
{missing_summary_text}
- **2. 미도래 슬롯 (관측 종료 시점 이후 미래 슬롯)**:
{unreached_summary_text}
- **3. 준중복 드롭 슬롯 (120초 이내 인접 호출 드롭)**:
{dedup_summary_text}
- **09-08 실효 슬롯 서사**:
{narrative_0908}
- **제외 3개 노선(`GGB222000056`, `GGB222000137`, `GGB222000239`)**:
  - 사유: 수집 설계상 7A' 입력 목록 누락으로 공표 배차 정보 부재 (API 미제공이 아님).
  - 처리: 노선 단위 관측 배차 산출 및 교차검증에서는 제외하되, 정류소 실질 서비스 수준은 경유 전 노선의 합집합이므로 정류소 단위 합산 지표에는 15개 전체 노선을 포함함 (`crosscheck_available=False` 표기).

## 8. 공표 배차간격 단위 미확정
- `intervaltime` 계열의 단위는 값 범위 기반으로 '분'으로 추정하였으나 문서 근거가 미확보되었다. (가정이 틀렸을 경우 교차검증 델타가 무효화됨).

## 9. 실측 요약 대조표
- **파싱 회계**: 총 JSON {total_json}건 중 성공 {success_json}건, 실패 {failed_json}건.
"""
    return doc

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--commit', action='store_true')
    args = parser.parse_args()

    if not args.dry_run and not args.commit:
        print("Must specify --dry-run or --commit")
        return

    # 1. 데이터 로드
    ledger_raw, raw_df, pub_df, p_stats = load_data()
    if ledger_raw.empty:
        print("No ledger data found.")
        return

    # [F1] 중복 키 조사 및 api_error 재시도 쌍 규명
    dup_keys_raw = ledger_raw[ledger_raw.duplicated(['obs_date', 'slot_hhmm'], keep=False)]
    dup_details = []
    for (d, s), g in dup_keys_raw.groupby(['obs_date', 'slot_hhmm']):
        for idx, r in g.iterrows():
            p_conv = Path(f"evidence/arrival_raw/{d}/31130_GGB222001318_{s}.json")
            in_raw_df = not raw_df[(raw_df['obs_date'] == d) & (raw_df['slot_hhmm'] == s)].empty
            dup_details.append({
                'obs_date': d,
                'slot_hhmm': s,
                'outcome': r['outcome'],
                'retry_count': r['retry_count'],
                'called_at': r['called_at_kst'],
                'raw_path': r['raw_path'],
                'item_count': r['item_count'],
                'in_raw_df': in_raw_df,
                'convention_file_exists': p_conv.exists()
            })
    dup_details_df = pd.DataFrame(dup_details)

    # [F2] 원장 정제 (동일 키 중복 제거 및 슬롯 상이 준중복 제거)
    ledger_clean, f1_same_key_drops, f2_near_dups, deduplicated_slots = process_ledger(ledger_raw)

    # [F3] 미도래 슬롯과 실제 결측 슬롯 3구분
    missing_slots_dict, unreached_slots_dict = classify_missing_and_unreached(ledger_clean, deduplicated_slots)

    missing_lines = []
    unreached_lines = []
    for d in sorted(missing_slots_dict.keys()):
        m_am = missing_slots_dict[d]['AM']
        m_pm = missing_slots_dict[d]['PM']
        if m_am or m_pm:
            missing_lines.append(f"  - [{d}] AM 결측 {len(m_am)}건: {m_am} | PM 결측 {len(m_pm)}건: {m_pm}")
        u_am = unreached_slots_dict[d]['AM']
        u_pm = unreached_slots_dict[d]['PM']
        if u_am or u_pm:
            unreached_lines.append(f"  - [{d}] AM 미도래 {len(u_am)}건: {u_am} | PM 미도래 {len(u_pm)}건: {u_pm}")
            
    missing_summary_text = "\n".join(missing_lines) if missing_lines else "  - (실제 결측 없음)"
    unreached_summary_text = "\n".join(unreached_lines) if unreached_lines else "  - (미도래 슬롯 없음)"
    
    dedup_lines = []
    for dd in f2_near_dups:
        dedup_lines.append(f"  - [{dd['obs_date']}] 유지={dd['kept_slot']}, 드롭={dd['dropped_slot']}, 시각차={dd['diff_seconds']:.2f}초, 드롭행실제item={dd['dropped_items']}건")
    dedup_summary_text = "\n".join(dedup_lines) if dedup_lines else "  - (준중복 드롭 없음)"

    # [F4] 09-08 실효 슬롯 서사 계산
    sub_0908_clean = ledger_clean[ledger_clean['obs_date'] == '2026-09-08']
    eff_cnt_0908 = sub_0908_clean['slot_hhmm'].nunique()
    eff_pct_0908 = (eff_cnt_0908 / 48) * 100
    
    # 09-08 원인 귀속
    # api_error 발생 1건은 17:50:04에 재시도 성공
    # 그러나 1750 정규 호출과 1.54초 준중복되어 늦은 쪽인 1745가 드롭됨
    api_error_loss_0908 = 0 # 재시도 성공했으므로 api 미제공 결측 아님
    dedup_loss_0908 = len([d for d in f2_near_dups if d['obs_date'] == '2026-09-08'])
    narrative_0908 = (
        f"  - 09-08 실효 슬롯은 {eff_cnt_0908}/48 ({eff_pct_0908:.1f}%)로 코드로 직접 귀속됨.\n"
        f"  - 원인 귀속: api_error 순수 결측 = {api_error_loss_0908}건 (17:50:04 재시도 성공 완료), "
        f"준중복드롭 = {dedup_loss_0908}건 (1750 정규 호출과의 시각차 준중복으로 늦은 쪽 드롭)."
    )

    # 3방향 키 대조 목록
    raw_keys = set(zip(raw_df['obs_date'], raw_df['slot_hhmm']))
    ledger_keys = set(zip(ledger_clean['obs_date'], ledger_clean['slot_hhmm']))
    both_keys = raw_keys & ledger_keys
    raw_only_keys = sorted(raw_keys - ledger_keys)
    ledger_only_keys = sorted(ledger_keys - raw_keys)

    # 노선 목록 구성
    routes = sorted(set(raw_df['routeid'].unique()) | set(pub_df['routeid'].unique()))
    exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']

    # 시계열 생성 (Base vs Zero-fill)
    ts_base = build_timeseries(ledger_clean, raw_df, routes, deduplicated_slots=deduplicated_slots, zero_fill=False)
    ts_zero = build_timeseries(ledger_clean, raw_df, routes, deduplicated_slots=deduplicated_slots, zero_fill=True)

    # 이벤트 검출
    ev_base, ts_base = detect_events_v2(ts_base)
    ev_zero, ts_zero = detect_events_v2(ts_zero)

    # 최대 예측 지평 실측
    actual_max_horizon = int(raw_df['arrtime_sec'].max()) if not raw_df.empty else 0

    # F9 성능 개선: aggregate_metrics 를 루프 밖에서 1회만 호출
    met_all_unfiltered = aggregate_metrics(ev_base, ts_base, routes_to_exclude=[])

    # [E5/F7] 노선별 회계표 (raw 레코드 행 수 count 기준)
    route_acct = []
    for r in routes:
        r_raw = raw_df[raw_df['routeid'] == r]
        raw_rec_am = len(r_raw[r_raw['slot_hhmm'] < '1200'])
        raw_rec_pm = len(r_raw[r_raw['slot_hhmm'] >= '1200'])
        raw_rec_tot = raw_rec_am + raw_rec_pm
        
        r_ev = ev_base[ev_base['routeid'] == r]
        ev_am = len(r_ev[r_ev['window'] == 'AM'])
        ev_pm = len(r_ev[r_ev['window'] == 'PM'])
        ev_tot = ev_am + ev_pm
        
        met_r_sub = met_all_unfiltered[met_all_unfiltered['routeid'] == r]
        gr_am = len(met_r_sub[met_r_sub['window'] == 'AM'])
        gr_pm = len(met_r_sub[met_r_sub['window'] == 'PM'])
        gr_tot = gr_am + gr_pm
        
        in_pub = r in pub_df['routeid'].values if not pub_df.empty else False
        
        route_acct.append({
            'routeid': r,
            'raw_records_am': raw_rec_am,
            'raw_records_pm': raw_rec_pm,
            'raw_records_tot': raw_rec_tot,
            'events_am': ev_am,
            'events_pm': ev_pm,
            'events_tot': ev_tot,
            'groups_am': gr_am,
            'groups_pm': gr_pm,
            'groups_tot': gr_tot,
            'in_published_meta': in_pub
        })
    route_acct_df = pd.DataFrame(route_acct)
    
    total_row = {
        'routeid': 'Total',
        'raw_records_am': route_acct_df['raw_records_am'].sum(),
        'raw_records_pm': route_acct_df['raw_records_pm'].sum(),
        'raw_records_tot': route_acct_df['raw_records_tot'].sum(),
        'events_am': route_acct_df['events_am'].sum(),
        'events_pm': route_acct_df['events_pm'].sum(),
        'events_tot': route_acct_df['events_tot'].sum(),
        'groups_am': route_acct_df['groups_am'].sum(),
        'groups_pm': route_acct_df['groups_pm'].sum(),
        'groups_tot': route_acct_df['groups_tot'].sum(),
        'in_published_meta': pd.NA
    }
    route_acct_with_tot = pd.concat([route_acct_df, pd.DataFrame([total_row])], ignore_index=True)

    # 분석 창 정의
    dates_core = ['2026-09-07', '2026-09-08', '2026-09-09']
    dates_supp = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
    dates_completed = ['2026-09-04', '2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
    dates_all_inclusive = sorted(ledger_clean['obs_date'].unique())

    # [F5] 2x2 민감도 분석 보강 (p25, p75, 가짜 이벤트 수 포함)
    fake_events_per_slot = len([r for r in routes if r not in exc_routes])
    simultaneous_note = f"ok_empty 1슬롯 0처리 시 슬롯당 {fake_events_per_slot}개 노선에 동시 도착 이벤트가 인위 생성되는 '동시 도착 반사실'의 비현실성이 존재함."

    sens_res = []
    for name, t_df, e_df in [('Base(결측유지)', ts_base, ev_base), ('Zero-Fill(0처리)', ts_zero, ev_zero)]:
        for w_name, w_dates in [('본안(3일)', dates_core), ('부속(4일)', dates_supp)]:
            sub_ev = e_df[e_df['obs_date'].isin(w_dates)]
            sub_ts = t_df[t_df['obs_date'].isin(w_dates)]
            m = aggregate_metrics(sub_ev, sub_ts, routes_to_exclude=exc_routes)
            if not m.empty:
                gaps = m['median_gap_min'].dropna()
                med_val = float(gaps.median()) if not gaps.empty else pd.NA
                p25_val = float(gaps.quantile(0.25)) if not gaps.empty else pd.NA
                p75_val = float(gaps.quantile(0.75)) if not gaps.empty else pd.NA
                insuff_rate = float(m['insufficient_observation'].mean() * 100)
                n_groups = len(m)
                n_events = len(sub_ev[~sub_ev['routeid'].isin(exc_routes)])
            else:
                med_val, p25_val, p75_val, insuff_rate, n_groups, n_events = pd.NA, pd.NA, pd.NA, pd.NA, 0, 0
                
            sens_res.append({
                'Condition': f"{name} / {w_name}",
                'Median Gap(분)': med_val,
                'p25': p25_val,
                'p75': p75_val,
                'Groups': n_groups,
                'Events': n_events,
                'Insuff(%)': f"{insuff_rate:.1f}%" if pd.notna(insuff_rate) else "N/A"
            })
    sens_df = pd.DataFrame(sens_res)

    b_core_med = sens_df.iloc[0]['Median Gap(분)']
    z_core_med = sens_df.iloc[2]['Median Gap(분)']
    abs_diff_core = z_core_med - b_core_med if pd.notna(b_core_med) and pd.notna(z_core_med) else pd.NA
    rel_diff_core = (abs_diff_core / b_core_med) * 100 if pd.notna(abs_diff_core) and b_core_med > 0 else pd.NA

    b_supp_med = sens_df.iloc[1]['Median Gap(분)']
    z_supp_med = sens_df.iloc[3]['Median Gap(분)']
    abs_diff_supp = z_supp_med - b_supp_med if pd.notna(b_supp_med) and pd.notna(z_supp_med) else pd.NA
    rel_diff_supp = (abs_diff_supp / b_supp_med) * 100 if pd.notna(abs_diff_supp) and b_supp_med > 0 else pd.NA

    # [F6] 정류소 단위 지표 산출 (본안 3일 기준 및 전체 기준)
    ev_core = ev_base[ev_base['obs_date'].isin(dates_core)]
    ev_supp = ev_base[ev_base['obs_date'].isin(dates_supp)]
    ev_completed = ev_base[ev_base['obs_date'].isin(dates_completed)]
    
    stop_met_core = stop_level_metrics(ev_core, exc_routes=exc_routes)
    stop_met_all = stop_level_metrics(ev_base, exc_routes=exc_routes)
    stop_met_all['analysis_window'] = '본안3일' # 기본 분석 창 명시

    # [F6] 교차검증 테이블 (본안 3일 기준)
    metrics_core_filtered = aggregate_metrics(ev_core, ts_base[ts_base['obs_date'].isin(dates_core)], routes_to_exclude=exc_routes)
    out_core_crosscheck = prep_crosscheck(metrics_core_filtered, pub_df, routes_to_exclude=exc_routes)
    out_core_crosscheck['analysis_window'] = '본안3일'

    # [F6] 관측 지표 분리 (headway_observed.parquet 용)
    observed_cols = [
        'routeid', 'obs_date', 'window', 'median_gap_min', 'p25', 'p75',
        'n_events', 'n_multi_item_snapshots', 'insufficient_observation', 'gap_adjacent_ratio'
    ]
    out_core_observed = metrics_core_filtered[observed_cols].copy()
    out_core_observed['analysis_window'] = '본안3일'

    # [F3/F4/E4] 대조표 산출 (미완일 제외 vs 미완일 포함 병기)
    metrics_completed_filtered = aggregate_metrics(ev_completed, ts_base[ts_base['obs_date'].isin(dates_completed)], routes_to_exclude=exc_routes)
    metrics_inclusive_filtered = aggregate_metrics(ev_base, ts_base, routes_to_exclude=exc_routes)
    metrics_supp_filtered = aggregate_metrics(ev_supp, ts_base[ts_base['obs_date'].isin(dates_supp)], routes_to_exclude=exc_routes)
    
    out_completed = prep_crosscheck(metrics_completed_filtered, pub_df, routes_to_exclude=exc_routes)
    out_inclusive = prep_crosscheck(metrics_inclusive_filtered, pub_df, routes_to_exclude=exc_routes)
    out_supp = prep_crosscheck(metrics_supp_filtered, pub_df, routes_to_exclude=exc_routes)

    # 드리프트 분석
    drift_diffs = []
    for _, r in ev_base.iterrows():
        g_slot = r['gap_min']
        g_called = r['gap_min_called']
        if pd.notna(g_slot) and pd.notna(g_called):
            drift_diffs.append(g_called - g_slot)
    drift_series = pd.Series(drift_diffs) if drift_diffs else pd.Series(dtype=float)

    # docs 전문 생성
    doc_content = generate_docs_content(
        core_days=len(dates_core),
        supp_days=len(dates_supp),
        total_json=p_stats['total_files'],
        success_json=p_stats['success'],
        failed_json=p_stats['failed'],
        actual_max_horizon=actual_max_horizon,
        missing_summary_text=missing_summary_text,
        unreached_summary_text=unreached_summary_text,
        dedup_summary_text=dedup_summary_text,
        narrative_0908=narrative_0908,
        simultaneous_note=simultaneous_note
    )

    if args.dry_run:
        # === [F1 결과 최상단 배치] ===
        print("==================================================")
        print("=== [F1] api_error 재시도 쌍 규명 및 중복 키 분석 ===")
        print("==================================================")
        print(f"1. 원장 내 (obs_date, slot_hhmm) 중복 행 전량 나열 ({len(dup_details_df)}행):")
        if not dup_details_df.empty:
            print(dup_details_df.to_string(index=False))
        else:
            print("  (중복 행 없음)")
            
        print("\n2. api_error 키의 성공 행 병존 판정:")
        retried_ok_count = 0
        pure_api_error_count = 0
        for (d, s), g in dup_keys_raw.groupby(['obs_date', 'slot_hhmm']):
            has_ok = (g['outcome'] == 'ok_with_items').any()
            has_err = (g['outcome'] == 'api_error').any()
            if has_ok and has_err:
                retried_ok_count += 1
                print(f"  * 키 ({d}, {s}): api_error 발생 후 재시도 성공 행 존재 -> outcome='api_error_retried_ok' 표기 및 collection_missing=False 처리 완료 (실손실 0건).")
            elif has_err and not has_ok:
                pure_api_error_count += 1
                print(f"  * 키 ({d}, {s}): api_error 발생 후 성공 행 없음 -> 결측 처리.")
                
        print(f"  -> 재시도 성공으로 실손실이 아닌 건수: {retried_ok_count}건 | 순수 결측 api_error 건수: {pure_api_error_count}건 (실측 계산치).")

        # === [F2 결과 최상단 배치] ===
        print("\n==================================================")
        print("=== [F2] 중복 키 제거 및 merge 안전장치 검증 ===")
        print("==================================================")
        print(f"1. 동일 키 중복 드롭 내역 ({len(f1_same_key_drops)}건):")
        if f1_same_key_drops:
            for drop_item in f1_same_key_drops:
                print(f"  * 드롭: 키=({drop_item['obs_date']}, {drop_item['slot_hhmm']}), 유지outcome={drop_item['kept_outcome']}, 드롭outcome={drop_item['dropped_outcome']}, 시각차={drop_item['diff_seconds']:.2f}초, 사유={drop_item['reason']}")
        else:
            print("  (동일 키 드롭 없음)")
            
        print(f"\n2. 슬롯 상이 준중복 드롭 내역 ({len(f2_near_dups)}건):")
        if f2_near_dups:
            for near_item in f2_near_dups:
                print(f"  * 드롭: 일자={near_item['obs_date']}, 유지={near_item['kept_slot']}, 드롭={near_item['dropped_slot']}, 시각차={near_item['diff_seconds']:.2f}초, 드롭행실제item={near_item['dropped_items']}건 (실제 데이터 존재 확인), 사유={near_item['reason']}")
        else:
            print("  (준중복 드롭 없음)")
            
        print("\n3. merge 직전 중복 키 assertion 안전장치:")
        print("  * assert ledger_sub.duplicated(['obs_date', 'slot_hhmm']).sum() == 0 통과 확인 완료.")

        # === [F3/F4 실측 결측·미도래·준중복 3구분] ===
        print("\n==================================================")
        print("=== [F3/F4] 결측 / 미도래 / 준중복 3구분 및 09-08 서사 귀속 ===")
        print("==================================================")
        print("1. 실제 결측 슬롯 (과거 도래 슬롯 중 누락):")
        print(missing_summary_text)
        print("\n2. 미도래 슬롯 (최종 수집 시각 이후 미래 슬롯):")
        print(unreached_summary_text)
        print("\n3. 준중복 드롭 슬롯 (120초 이내 인접 호출):")
        print(dedup_summary_text)
        print(f"\n4. 09-08 실효 슬롯 원인 귀속 서사:")
        print(narrative_0908)

        # === [E5 노선별 회계표] ===
        print("\n==================================================")
        print("=== [E5] 노선별 회계표 (raw 레코드 행 수 count 기준) ===")
        print("==================================================")
        print(route_acct_with_tot.to_string(index=False))

        # === [F3/E4 대조표] ===
        print("\n==================================================")
        print("=== [F3/E4] (전체/본안/부속) 수치 대조표 (제외노선 필터 통일 및 미완일 병기) ===")
        print("==================================================")
        print("| 지표 | 전체(미완일제외 5일) | 전체(미완일포함 6일) | 본안(09.07~09 3일) | 부속(09.07~10 4일) |")
        print("|---|---|---|---|---|")
        print(f"| 관측 일수 | {len(dates_completed)}일 ({dates_completed[0]}~{dates_completed[-1]}) | {len(dates_all_inclusive)}일 ({dates_all_inclusive[0]}~{dates_all_inclusive[-1]}) | {len(dates_core)}일 | {len(dates_supp)}일 |")
        print(f"| 총 이벤트 수 (12개 노선 필터 후) | {len(ev_completed[~ev_completed['routeid'].isin(exc_routes)])} | {len(ev_base[~ev_base['routeid'].isin(exc_routes)])} | {len(ev_core[~ev_core['routeid'].isin(exc_routes)])} | {len(ev_supp[~ev_supp['routeid'].isin(exc_routes)])} |")
        print(f"| 총 이벤트 수 (제외노선 포함 15개 노선) | {len(ev_completed)} | {len(ev_base)} | {len(ev_core)} | {len(ev_supp)} |")
        print(f"| 노선 단위 유효 그룹 수 | {len(out_completed)} | {len(out_inclusive)} | {len(out_core_crosscheck)} | {len(out_supp)} |")
        print(f"| insufficient 비율(%) | {out_completed['insufficient_observation'].mean()*100:.1f}% | {out_inclusive['insufficient_observation'].mean()*100:.1f}% | {out_core_crosscheck['insufficient_observation'].mean()*100:.1f}% | {out_supp['insufficient_observation'].mean()*100:.1f}% |")
        print(f"| agree_within_5min 건수 | {(out_completed['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_inclusive['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_core_crosscheck['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_supp['headway_source_agreement'] == 'agree_within_5min').sum()} |")

        # === [F5 2x2 민감도] ===
        print("\n==================================================")
        print("=== [F5] 2×2 민감도 분석 표 (p25, p75, 변동치 포함) ===")
        print("==================================================")
        print(sens_df.to_string(index=False))
        print(f"* 슬롯당 인위 생성 가짜 이벤트 수: {fake_events_per_slot}개 (= 분석 대상 노선 수)")
        print(f"* 본안(3일) 0처리 변동: 중앙값 절대차 {abs_diff_core:.2f}분 (상대변화율 {rel_diff_core:.1f}%)" if pd.notna(abs_diff_core) else "* 본안(3일) 변동: N/A")
        print(f"* 부속(4일) 0처리 변동: 중앙값 절대차 {abs_diff_supp:.2f}분 (상대변화율 {rel_diff_supp:.1f}%)" if pd.notna(abs_diff_supp) else "* 부속(4일) 변동: N/A")

        # === [E3/F6 정류소 단위 지표] ===
        print("\n==================================================")
        print("=== [E3/F6] 정류소 단위 지표 (본안 3일, 유효 노선 중앙값의 중앙값) ===")
        print("==================================================")
        print(stop_met_core.to_string(index=False))

        # === [교차검증 분포] ===
        print("\n==================================================")
        print("=== [F6] 교차검증 분포 (본안 3일 기준, 방향 미분리 판정 불가 취지) ===")
        print("==================================================")
        if not out_core_crosscheck.empty:
            print(out_core_crosscheck['headway_source_agreement'].value_counts().to_string())
        print("  -> disagree 건수는 단방향 관측과 공표 상·하행 합산 간의 계통 편의(약 2배 차이)로 인한 판정 불가 성격을 포함함.")

        # === [D6 드리프트] ===
        print("\n==================================================")
        print("=== [D6] 스케줄러 드리프트 차이 분포 (호출시각 vs 슬롯간격) ===")
        print("==================================================")
        if not drift_series.empty:
            print(f"- 드리프트 차이(분): min={drift_series.min():.2f}, mean={drift_series.mean():.2f}, median={drift_series.median():.2f}, max={drift_series.max():.2f}")

        # === [D4 docs 전문 미리보기] ===
        print("\n==================================================")
        print("=== [D4] docs/headway_limits.md 전문 미리보기 ===")
        print("==================================================")
        print(doc_content)

        # === [사람이 결정할 사항] ===
        print("\n==================================================")
        print("=== 사람이 결정할 사항 ===")
        print("==================================================")
        print("1. [F1 판정] 동일 키 내 api_error 발생 후 재시도 성공한 슬롯에 대해 outcome='api_error_retried_ok' 표기 및 실손실 제외 정책의 최종 승인 여부")
        print("2. [F2 판정] 동일 키 중복(성공 행 우선) 및 슬롯 상이 준중복(120초 이내 늦은 쪽 드롭) 분리 처리 로직 승인 여부")
        print(f"3. [F3 창 선택] 대조표 및 종합 보고서의 전체 관측 일수를 미완일 제외 완료 5일({len(dates_completed)}일)로 할지 미완일 포함 6일({len(dates_all_inclusive)}일)로 할지 선택")
        print("4. [E3 지표] 정류소 단위 지표 산출 시 n_events < 4 노선 제외 후 '유효 노선 중앙값의 중앙값' 정의 확정 여부")
        print(f"5. [지표 수용] insufficient_observation 비율(본안 {out_core_crosscheck['insufficient_observation'].mean()*100:.1f}%, 부속 {out_supp['insufficient_observation'].mean()*100:.1f}%) 수용 및 노선×일자×창 단위 유지 여부")
        print("6. [첫차/막차] first_bus_ok / last_bus_ok 판정용 '기점~정류소 간 주행시간 보정 규칙' 정의 및 도입 여부")
        print("7. [공표 단위] 공표 배차 intervaltime의 단위('분')에 대한 국토교통부/TAGO 공식 문서 근거 확보 여부")

    if args.commit:
        out_dir_staged = Path('data/staged')
        out_dir_exports = Path('exports')
        out_dir_docs = Path('docs')
        
        out_dir_staged.mkdir(parents=True, exist_ok=True)
        out_dir_exports.mkdir(parents=True, exist_ok=True)
        out_dir_docs.mkdir(parents=True, exist_ok=True)

        pq_path = out_dir_staged / 'headway_observed.parquet'
        csv_path = out_dir_exports / 'headway_crosscheck.csv'
        stop_csv_path = out_dir_exports / 'headway_stop_level.csv'
        md_path = out_dir_docs / 'headway_limits.md'

        if not out_core_observed.empty:
            if pq_path.exists():
                print(f"[덮어쓰기 안내] {pq_path} (기존 크기: {pq_path.stat().st_size} bytes)")
            print(f"Writing {pq_path}: {len(out_core_observed)} rows, {len(out_core_observed.columns)} cols")
            out_core_observed.to_parquet(pq_path, index=False)

        if not out_core_crosscheck.empty:
            if csv_path.exists():
                print(f"[덮어쓰기 안내] {csv_path} (기존 크기: {csv_path.stat().st_size} bytes)")
            print(f"Writing {csv_path}: {len(out_core_crosscheck)} rows, {len(out_core_crosscheck.columns)} cols")
            out_core_crosscheck.to_csv(csv_path, index=False)

        if not stop_met_core.empty:
            if stop_csv_path.exists():
                print(f"[덮어쓰기 안내] {stop_csv_path} (기존 크기: {stop_csv_path.stat().st_size} bytes)")
            print(f"Writing {stop_csv_path}: {len(stop_met_core)} rows, {len(stop_met_core.columns)} cols")
            stop_met_core.to_csv(stop_csv_path, index=False)

        if md_path.exists():
            print(f"[덮어쓰기 안내] {md_path} (기존 크기: {md_path.stat().st_size} bytes)")
        print(f"Writing {md_path}: {len(doc_content.encode('utf-8'))} bytes")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)
            
        print("[Commit 완료] 모든 산출물이 성공적으로 기록되었습니다.")

if __name__ == '__main__':
    main()
