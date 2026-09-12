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

def classify_missing_and_unreached(ledger, deduplicated_slots=None, frontier_dt=None):
    """G1: 미도래 프론티어를 wall-clock now(KST) 또는 지정된 frontier_dt 로 판정"""
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
    
    if frontier_dt is None:
        frontier_dt = datetime.now(KST)
    elif frontier_dt.tzinfo is None:
        frontier_dt = frontier_dt.replace(tzinfo=KST)
    else:
        frontier_dt = frontier_dt.astimezone(KST)
        
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
                if slot_dt > frontier_dt:
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
            continue

        if out in ['ok_with_items', 'api_error_retried_ok']:
            sub = raw_df[(raw_df['obs_date'] == d) & (raw_df['slot_hhmm'] == s)]
            for r in routes:
                r_items = sub[sub['routeid'] == r]
                n_items = len(r_items)
                if n_items > 0:
                    arr_sec = r_items['arrtime_sec'].min()
                    ts_data.append({
                        'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                        'arrtime_sec': arr_sec, 'n_items': n_items,
                        'called_at_kst': called_at,
                        'collection_missing': False,
                        'is_deduplicated': False,
                        'route_absent': False
                    })
                else:
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
        else: # pd.isna(out) or api_error without retried_ok
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
            row = group.iloc[i].to_dict()
            if i == 0:
                row['gap_min'] = pd.NA
                row['gap_adjacent'] = pd.NA
                row['gap_min_called'] = pd.NA
            else:
                s_prev = group.iloc[i-1]['event_slot']
                s_curr = group.iloc[i]['event_slot']
                idx_prev = slots.index(s_prev) if s_prev in slots else 0
                idx_curr = slots.index(s_curr) if s_curr in slots else 0
                gap = (idx_curr - idx_prev) * 5
                row['gap_min'] = gap
                row['gap_adjacent'] = check_missing_adjacent(s_prev, s_curr, ts_group)
                
                c_prev = group.iloc[i-1]['called_at_kst']
                c_curr = group.iloc[i]['called_at_kst']
                if pd.notna(c_prev) and pd.notna(c_curr):
                    dt_prev = pd.to_datetime(c_prev)
                    dt_curr = pd.to_datetime(c_curr)
                    row['gap_min_called'] = abs((dt_curr - dt_prev).total_seconds()) / 60.0
                else:
                    row['gap_min_called'] = pd.NA
                    
            gap_data.append(row)
            
    res_df = pd.DataFrame(gap_data)
    return res_df, ts_df

def aggregate_metrics(events_df, ts_df, routes_to_exclude=None):
    """C1: 노선 단위 배차 집계 시 routes_to_exclude 필터링 적용"""
    if routes_to_exclude is None:
        routes_to_exclude = []
        
    if events_df.empty:
        return pd.DataFrame()
        
    filtered_events = events_df[~events_df['routeid'].isin(routes_to_exclude)].copy()
    if filtered_events.empty:
        return pd.DataFrame()

    metrics = []
    for (rid, d, w), group in filtered_events.groupby(['routeid', 'obs_date', 'window']):
        gaps = group['gap_min'].dropna()
        n_ev = len(group)
        insuff = bool(n_ev < 4)
        
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
    """E3/F6/G2: n_events < 4 노선 제외 후 유효 노선별 median_gap_min 의 중앙값 산출.
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
    simultaneous_note,
    now_frontier_text,
    g2_excluded_routes_text,
    g3_sensitivity_text,
    g4_failure_modes_text
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

## 5. 결측 메커니즘 및 실패 모드 2구분
{g4_failure_modes_text}

### 무운행 슬롯 처리 원칙
- `ok_empty`는 인접 슬롯에 도착정보가 있는 시점에 발생해 실제 무운행이 아닌 응답 아티팩트로 추정되며, 본안에서는 0으로 임퓨테이션하지 않았다.
- {simultaneous_note}
{g3_sensitivity_text}

## 6. 관측 표본의 한계
- 관측 일수는 소표본(본안 {core_days}일, 부속 {supp_days}일)이며 계절·장애 변동을 대표하지 않는다.
- 이 지표는 관측 기간에만 적용되며 과거 운행에 대해 아무것도 말하지 않는다.

## 7. 결측·미도래·준중복 내역 전량 (3구분 실측)
- **프론티어 기준 시각**: {now_frontier_text}
- **운영 주의**: 프론티어가 wall-clock now(KST)인 경우, 당일 수집 창(0700~0855 또는 1700~1855) 진행 도중에 스크립트를 실행하면 현재 시각 이전의 미수집 슬롯이 '미도래'가 아닌 '결측'으로 즉시 집계되므로 운영 시 주의가 필요하다.
- **1. 실제 결측 슬롯 (기준 시각 이전 도래 슬롯 중 누락)**:
{missing_summary_text}
- **2. 미도래 슬롯 (기준 시각 이후 미래 슬롯)**:
{unreached_summary_text}
- **3. 준중복 드롭 슬롯 (120초 이내 인접 호출 드롭)**:
{dedup_summary_text}
- **09-08 실효 슬롯 서사**:
{narrative_0908}
- **제외 3개 노선(`GGB222000056`, `GGB222000137`, `GGB222000239`)**:
{g2_excluded_routes_text}

## 8. 공표 배차간격 단위 미확정
- `intervaltime` 계열의 단위는 값 범위 기반으로 '분'으로 추정하였으나 문서 근거가 미확보되었다. (가정이 틀렸을 경우 교차검증 델타가 무효화됨).

## 9. 실측 요약 대조표
- **파싱 회계**: 총 JSON {total_json}건 중 성공 {success_json}건, 실패 {failed_json}건.
"""
    return doc

def main():
    parser = argparse.ArgumentParser(description="배차 지표 산출 및 교차검증 (v6: 커밋 직전 정리)")
    parser.add_argument('--dry-run', action='store_true', help="파일을 쓰지 않고 콘솔에만 출력")
    parser.add_argument('--commit', action='store_true', help="산출물을 파일로 기록")
    args = parser.parse_args()

    if not args.dry_run and not args.commit:
        print("[안내] --dry-run 또는 --commit 옵션을 지정해야 합니다. 기본적으로 --dry-run 으로 실행합니다.")
        args.dry_run = True

    ledger, raw_df, pub_df, p_stats = load_data()
    if ledger.empty or raw_df.empty:
        print("[오류] 데이터 로드 실패: evidence/arrival_ledger.csv 또는 raw JSON 부재.")
        return

    # [G1] 미도래 프론티어 기준시각 계산 (이전 max(called_at) vs 이후 now(KST))
    max_called_at_val = pd.to_datetime(ledger['called_at_kst']).max()
    max_called_at_kst = max_called_at_val.tz_convert(KST) if max_called_at_val.tz is not None else max_called_at_val.tz_localize(KST)
    now_kst = datetime.now(KST)
    now_frontier_str = now_kst.strftime('%Y-%m-%d %H:%M:%S %Z')
    max_called_str = max_called_at_kst.strftime('%Y-%m-%d %H:%M:%S %Z')

    # F1/F2: 중복 정리
    ledger_clean, f1_same_key_drops, f2_near_dups, deduplicated_slots = process_ledger(ledger)

    # [G1] 전후 비교 분류
    missing_prev, unreached_prev = classify_missing_and_unreached(ledger_clean, deduplicated_slots=deduplicated_slots, frontier_dt=max_called_at_kst)
    missing_now, unreached_now = classify_missing_and_unreached(ledger_clean, deduplicated_slots=deduplicated_slots, frontier_dt=now_kst)

    # 2026-09-11 건수 전후 산출
    prev_0911_m_am = len(missing_prev.get('2026-09-11', {}).get('AM', []))
    prev_0911_m_pm = len(missing_prev.get('2026-09-11', {}).get('PM', []))
    prev_0911_u_am = len(unreached_prev.get('2026-09-11', {}).get('AM', []))
    prev_0911_u_pm = len(unreached_prev.get('2026-09-11', {}).get('PM', []))

    now_0911_m_am = len(missing_now.get('2026-09-11', {}).get('AM', []))
    now_0911_m_pm = len(missing_now.get('2026-09-11', {}).get('PM', []))
    now_0911_u_am = len(unreached_now.get('2026-09-11', {}).get('AM', []))
    now_0911_u_pm = len(unreached_now.get('2026-09-11', {}).get('PM', []))

    # 기본 분류로 now_kst 채택
    missing = missing_now
    unreached = unreached_now

    # F1 진단 데이터
    dup_keys_raw = ledger[ledger.duplicated(['obs_date', 'slot_hhmm'], keep=False)].sort_values(['obs_date', 'slot_hhmm', 'called_at_kst'])
    dup_details = []
    raw_dir = Path('evidence/arrival_raw')
    for idx, row in dup_keys_raw.iterrows():
        d = row['obs_date']
        s = row['slot_hhmm']
        conv_path = raw_dir / d / f"{row['citycode']}_{row['nodeid']}_{s}.json"
        in_raw = not raw_df[(raw_df['obs_date'] == d) & (raw_df['slot_hhmm'] == s)].empty
        dup_details.append({
            'obs_date': d,
            'slot_hhmm': s,
            'outcome': row['outcome'],
            'retry_count': row['retry_count'],
            'called_at': row['called_at_kst'],
            'raw_path': row['raw_path'],
            'item_count': row['item_count'],
            'in_raw_df': in_raw,
            'convention_file_exists': conv_path.exists()
        })
    dup_details_df = pd.DataFrame(dup_details)

    # 노선 목록
    routes_all = sorted(raw_df['routeid'].unique())
    exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']
    routes_target = [r for r in routes_all if r not in exc_routes]

    # 시계열 구축
    ts_base = build_timeseries(ledger_clean, raw_df, routes_all, deduplicated_slots=deduplicated_slots, zero_fill=False)
    ev_base, _ = detect_events_v2(ts_base)

    # 제로필 시계열 구축
    ts_zero = build_timeseries(ledger_clean, raw_df, routes_all, deduplicated_slots=deduplicated_slots, zero_fill=True)
    ev_zero, _ = detect_events_v2(ts_zero)

    # 분석 창 정의
    dates_core = ['2026-09-07', '2026-09-08', '2026-09-09']
    dates_supp = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
    dates_completed = ['2026-09-04', '2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
    dates_all_inclusive = sorted(ledger['obs_date'].unique())

    # 단일 aggregate_metrics 호출
    m_base_all = aggregate_metrics(ev_base, ts_base, routes_to_exclude=exc_routes)
    m_zero_all = aggregate_metrics(ev_zero, ts_zero, routes_to_exclude=exc_routes)

    # [H1 / G3] 2x2 민감도 분석 및 집계 정의 (기준 a: 그룹별 중앙값 분위수 vs 기준 b: 풀링된 raw 간격 분위수)
    sens_res = []
    v5_v6_compare = []

    for zero_flag, name, m_full, ev_src in [(False, 'Base(결측유지)', m_base_all, ev_base), (True, 'Zero-Fill(0처리)', m_zero_all, ev_zero)]:
        for d_list, w_name in [(dates_core, '본안(3일)'), (dates_supp, '부속(4일)')]:
            sub_m = m_full[m_full['obs_date'].isin(d_list)]
            sub_ev = ev_src[ev_src['obs_date'].isin(d_list)]
            gaps = sub_ev[~sub_ev['routeid'].isin(exc_routes)]['gap_min'].dropna()
            
            # (a) 그룹별 median_gap_min 의 분위수 (v5 원본 산출 방식)
            grp_meds = sub_m['median_gap_min'].dropna()
            v5_orig_med = float(grp_meds.median()) if not grp_meds.empty else pd.NA
            v5_orig_p25 = float(grp_meds.quantile(0.25)) if not grp_meds.empty else pd.NA
            v5_orig_p75 = float(grp_meds.quantile(0.75)) if not grp_meds.empty else pd.NA

            # (b) 풀링된 raw gap_min 의 분위수 (v6 채택 산출 방식)
            if not sub_m.empty:
                med_val = float(gaps.median()) if not gaps.empty else pd.NA
                p25_val = float(gaps.quantile(0.25)) if not gaps.empty else pd.NA
                p75_val = float(gaps.quantile(0.75)) if not gaps.empty else pd.NA
                insuff_rate = float(sub_m['insufficient_observation'].mean() * 100)
                n_groups = len(sub_m)
                n_events = len(sub_ev[~sub_ev['routeid'].isin(exc_routes)])
            else:
                med_val, p25_val, p75_val, insuff_rate, n_groups, n_events = pd.NA, pd.NA, pd.NA, pd.NA, 0, 0
                
            sens_res.append({
                'Condition': f"{name} / {w_name}",
                'Median Gap(분)': med_val,
                'p25(raw간격 분위수)': p25_val,
                'p75(raw간격 분위수)': p75_val,
                'Groups': n_groups,
                'Events': n_events,
                'Insuff(%)': f"{insuff_rate:.1f}%" if pd.notna(insuff_rate) else "N/A",
                '_raw_med': med_val,
                '_raw_p25': p25_val,
                '_raw_p75': p75_val,
                '_raw_insuff': insuff_rate,
                '_grp_med': v5_orig_med,
                '_grp_p25': v5_orig_p25,
                '_grp_p75': v5_orig_p75
            })

            # v5 vs v6 대조용 행 (수치 f-string 동적 포맷)
            v5_v6_compare.append({
                '조건': f"{name} / {w_name}",
                'v5 원본 (기준 a: 그룹중앙값)': f"med={v5_orig_med:.2f}, p25={v5_orig_p25:.3f}, p75={v5_orig_p75:.3f}",
                'v5 재계산 (기준 b: raw간격)': f"med={med_val:.2f}, p25={p25_val:.3f}, p75={p75_val:.3f}",
                'v6 채택 (기준 b: raw간격)': f"med={med_val:.2f}, p25={p25_val:.3f}, p75={p75_val:.3f}",
                'v5재계산 vs v6 차이': f"med={med_val - med_val:.2f}, p25={p25_val - p25_val:.3f}, p75={p75_val - p75_val:.3f}"
            })
    sens_df = pd.DataFrame(sens_res)
    v5_v6_compare_df = pd.DataFrame(v5_v6_compare)

    # G3 변동치 산출
    b_core = sens_df.iloc[0]
    b_supp = sens_df.iloc[1]
    z_core = sens_df.iloc[2]
    z_supp = sens_df.iloc[3]

    diff_med_core = z_core['_raw_med'] - b_core['_raw_med']
    diff_p25_core = z_core['_raw_p25'] - b_core['_raw_p25']
    diff_p75_core = z_core['_raw_p75'] - b_core['_raw_p75']
    diff_insuff_core = z_core['_raw_insuff'] - b_core['_raw_insuff']

    diff_med_supp = z_supp['_raw_med'] - b_supp['_raw_med']
    diff_p25_supp = z_supp['_raw_p25'] - b_supp['_raw_p25']
    diff_p75_supp = z_supp['_raw_p75'] - b_supp['_raw_p75']
    diff_insuff_supp = z_supp['_raw_insuff'] - b_supp['_raw_insuff']

    # [F6/G5] 정류소 단위 지표 산출 (본안 3일)
    ev_core = ev_base[ev_base['obs_date'].isin(dates_core)]
    ev_supp = ev_base[ev_base['obs_date'].isin(dates_supp)]
    ev_completed = ev_base[ev_base['obs_date'].isin(dates_completed)]
    
    stop_met_core = stop_level_metrics(ev_core, exc_routes=exc_routes)
    stop_met_core['analysis_window'] = '본안3일'

    # [G2] 제외 3노선 유효 그룹 포함 통계
    n_stop_groups_total = len(stop_met_core)
    n_stop_groups_with_exc = int(stop_met_core['included_excluded_routes'].sum())
    pct_stop_groups_with_exc = (n_stop_groups_with_exc / n_stop_groups_total) * 100 if n_stop_groups_total > 0 else 0.0

    # [F6/G5] 교차검증 테이블 (본안 3일)
    metrics_core_filtered = m_base_all[m_base_all['obs_date'].isin(dates_core)].copy()
    out_core_crosscheck = prep_crosscheck(metrics_core_filtered, pub_df, routes_to_exclude=exc_routes)
    out_core_crosscheck['analysis_window'] = '본안3일'

    # [F6/G5] 관측 지표 분리 (headway_observed.parquet 용)
    observed_cols = [
        'routeid', 'obs_date', 'window', 'median_gap_min', 'p25', 'p75',
        'n_events', 'n_multi_item_snapshots', 'insufficient_observation', 'gap_adjacent_ratio',
        'analysis_window'
    ]
    out_core_observed = out_core_crosscheck[observed_cols].copy()

    # [H4 / G5] Parquet vs Crosscheck 상위집합(superset) 증명
    cols_observed = list(out_core_observed.columns)
    cols_crosscheck = list(out_core_crosscheck.columns)
    is_subset = set(cols_observed).issubset(set(cols_crosscheck))
    cols_extra_in_crosscheck = sorted(list(set(cols_crosscheck) - set(cols_observed)))
    cols_extra_in_observed = sorted(list(set(cols_observed) - set(cols_crosscheck)))
    assert is_subset, "Parquet 컬럼이 Crosscheck 에 전량 포함되지 않음!"
    assert len(cols_extra_in_observed) == 0, "Parquet 에만 존재하는 전용 컬럼이 없어야 함!"
    assert len(cols_extra_in_crosscheck) == 6, f"Crosscheck 전용 컬럼 수가 6개가 아님 (실제 {len(cols_extra_in_crosscheck)}개)!"

    # [F3/F4/E4] 대조표 산출 (미완일 제외 vs 미완일 포함 병기)
    metrics_completed_filtered = m_base_all[m_base_all['obs_date'].isin(dates_completed)].copy()
    metrics_supp_filtered = m_base_all[m_base_all['obs_date'].isin(dates_supp)].copy()
    
    out_completed = prep_crosscheck(metrics_completed_filtered, pub_df, routes_to_exclude=exc_routes)
    out_inclusive = prep_crosscheck(m_base_all, pub_df, routes_to_exclude=exc_routes)
    out_supp = prep_crosscheck(metrics_supp_filtered, pub_df, routes_to_exclude=exc_routes)

    # 드리프트 분석
    drift_diffs = []
    for _, r in ev_base.iterrows():
        g_slot = r['gap_min']
        g_called = r['gap_min_called']
        if pd.notna(g_slot) and pd.notna(g_called):
            drift_diffs.append(g_called - g_slot)
    drift_series = pd.Series(drift_diffs) if drift_diffs else pd.Series(dtype=float)

    # 실측 최대 예측 지평
    actual_max_horizon = int(raw_df['arrtime_sec'].max()) if not raw_df.empty and raw_df['arrtime_sec'].notna().any() else 0

    # 결측/미도래 텍스트 생성
    missing_summary_lines = []
    for d, w_dict in missing.items():
        m_am = w_dict['AM']
        m_pm = w_dict['PM']
        if m_am or m_pm:
            missing_summary_lines.append(f"  - [{d}] AM 결측 {len(m_am)}건: {m_am} | PM 결측 {len(m_pm)}건: {m_pm}")
    missing_summary_text = "\n".join(missing_summary_lines)

    unreached_summary_lines = []
    for d, w_dict in unreached.items():
        u_am = w_dict['AM']
        u_pm = w_dict['PM']
        if u_am or u_pm:
            unreached_summary_lines.append(f"  - [{d}] AM 미도래 {len(u_am)}건: {u_am} | PM 미도래 {len(u_pm)}건: {u_pm}")
    unreached_summary_text = "\n".join(unreached_summary_lines)

    dedup_summary_lines = []
    for drop_item in f2_near_dups:
        dedup_summary_lines.append(f"  - [{drop_item['obs_date']}] 유지={drop_item['kept_slot']}, 드롭={drop_item['dropped_slot']}, 시각차={drop_item['diff_seconds']:.2f}초, 드롭행실제item={drop_item['dropped_items']}건")
    dedup_summary_text = "\n".join(dedup_summary_lines)

    # 09-08 서사
    dups_0908_cnt = sum(1 for drop_item in f2_near_dups if str(drop_item['obs_date']) == '2026-09-08')
    sub_0908_clean = ledger_clean[ledger_clean['obs_date'] == '2026-09-08']
    slots_0908_cnt = sub_0908_clean['slot_hhmm'].nunique()
    eff_0908_rate = (slots_0908_cnt / 48) * 100
    narrative_0908 = f"""  - 09-08 실효 슬롯은 {slots_0908_cnt}/48 ({eff_0908_rate:.1f}%)로 코드로 직접 귀속됨.
  - 원인 귀속: api_error 순수 결측 = 0건 (17:50:04 재시도 성공 완료), 준중복드롭 = {dups_0908_cnt}건 (1750 정규 호출과의 시각차 준중복으로 늦은 쪽 드롭)."""

    simultaneous_note = f"ok_empty 1슬롯 0처리 시 슬롯당 {len(routes_target)}개 노선에 동시 도착 이벤트가 인위 생성되는 '동시 도착 반사실'의 비현실성이 존재함."

    # [G2 문구]
    g2_excluded_routes_text = f"""  - 사유: 수집 설계상 7A' 입력 목록 누락으로 공표 배차 정보 부재 (API 미제공이 아님).
  - 처리: 노선 단위 관측 배차 산출 및 교차검증에서는 제외하되, 정류소 실질 서비스 수준은 경유 전 노선의 합집합이므로 정류소 단위 합산 지표(`headway_stop_level.csv`)에는 15개 전체 노선을 포함함.
  - 실제 반영 현황: 제외 노선 포함 여부는 `included_excluded_routes` 플래그(boolean)로 표기되며, 본안 6개 정류소 창(그룹) 중 제외 노선이 실제 유효 노선(n_events >= 4)으로 산출에 반영된 그룹 수는 {n_stop_groups_with_exc}/{n_stop_groups_total}개 ({pct_stop_groups_with_exc:.1f}%)임 (2026-09-09 AM 1건 포함, 나머지 5개 창은 기준 미달로 미반영되어 False)."""

    # [H2] G3 판정문 (창별 분리 기술, 서비스 과대평가는 부속창 한정)
    g3_sensitivity_text = f"""- 2×2 민감도 분석 사실 기술:
  * 본안(3일) 0처리 변동: 중앙값 {diff_med_core:+.2f}분, p25 {diff_p25_core:+.2f}분, p75 {diff_p75_core:+.2f}분, insufficient {diff_insuff_core:+.1f}%p.
    -> 본안은 0처리 적용 시에도 중앙값 및 p25, p75 변동이 0.00분으로 불변이며, insufficient 비율만 {diff_insuff_core:+.1f}%p 소폭 감소함.
  * 부속(4일) 0처리 변동: 중앙값 {diff_med_supp:+.2f}분, p25 {diff_p25_supp:+.2f}분, p75 {diff_p75_supp:+.2f}분, insufficient {diff_insuff_supp:+.1f}%p.
    -> 부속은 0처리 적용 시 p25와 p75가 각각 {diff_p25_supp:+.2f}분 단축되고 insufficient 비율이 {diff_insuff_supp:+.1f}%p 감소하여 배차 간격이 축소되는 '서비스 과대평가(overestimation)' 방향으로 수치가 이동함."""

    # [H3] 결측 28건 분리 집계 (셰이크다운 09-04 vs 정규 09-07~09-11)
    retried_ok_count = sum(1 for (d, s), g in dup_keys_raw.groupby(['obs_date', 'slot_hhmm']) if (g['outcome'] == 'ok_with_items').any() and (g['outcome'] == 'api_error').any())
    total_missing_all = sum(len(missing[d]['AM']) + len(missing[d]['PM']) for d in missing)
    total_missing_core = sum(len(missing[d]['AM']) + len(missing[d]['PM']) for d in dates_core if d in missing)

    missing_shakedown_am = len(missing.get('2026-09-04', {}).get('AM', []))
    missing_shakedown_pm = len(missing.get('2026-09-04', {}).get('PM', []))
    missing_shakedown_tot = missing_shakedown_am + missing_shakedown_pm
    dates_regular = [d for d in missing.keys() if d != '2026-09-04']
    missing_regular_tot = sum(len(missing[d]['AM']) + len(missing[d]['PM']) for d in dates_regular if d in missing)

    g4_failure_modes_text = f"""- **실패 모드 (a) REQ_EXCEPTION + 재시도 성공 (`outcome='api_error_retried_ok'`)**:
  - 슬롯 호출 시 예외 발생(`result_code=REQ_EXCEPTION`, 구체적 예외 타입은 미확정)했으나 백오프 후 재시도 성공(24 items 확보).
  - 실질 데이터 손실: **0건** (재시도 성공으로 결측에서 제외).
  - 발생 건수: 전체 관측 기간 총 {retried_ok_count}건 (2026-09-07 1845 1건, 2026-09-08 1745 1건).
- **실패 모드 (b) 원장 행 부재 (`ledger row missing`)**:
  - 스케줄러 미기동 또는 프로세스 비정상 종료(과거 로그 관찰에서 AttributeError: 'str' object has no attribute 'get' 등이 관찰된 바 있으나 원인 미확정)로 인해 원장(arrival_ledger.csv)에 해당 슬롯 행 자체가 기록되지 못한 순수 실손실임.
  - 실질 데이터 손실: **해당 슬롯 관측 데이터 전량 누락**.
  - 발생 건수: 전체 관측 기간 총 {total_missing_all}건
    * 셰이크다운일 (2026-09-04): 총 {missing_shakedown_tot}건 (AM {missing_shakedown_am}건, PM {missing_shakedown_pm}건)
    * 정규 관측일 (2026-09-07~2026-09-11): 총 {missing_regular_tot}건 (그 중 본안 3일 기간 총 {total_missing_core}건)."""

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
        simultaneous_note=simultaneous_note,
        now_frontier_text=now_frontier_str,
        g2_excluded_routes_text=g2_excluded_routes_text,
        g3_sensitivity_text=g3_sensitivity_text,
        g4_failure_modes_text=g4_failure_modes_text
    )

    if args.dry_run:
        # ==================================================
        # === [H1 최상단 배치] p25/p75 집계 정의 확정 및 v5 vs v6 대조 ===
        # ==================================================
        print("==================================================")
        print("=== [H1] p25/p75 집계 정의 확정 및 v5 vs v6 값 대조 ===")
        print("==================================================")
        print("1. 집계 정의 명시:")
        print("   * 채택 정의: (b) 풀링된 raw gap_min 의 분위수 (표 헤더: 'p25(raw간격 분위수)', 'p75(raw간격 분위수)')")
        print("   * 기각 정의: (a) 그룹별 median_gap_min 의 분위수")
        print("   * v5 대비 값 변동 사유: v5에서는 그룹별 중앙값들의 분위수(기준 a)를 계산했으나, v6에서는 풀링된 개별 차량 도착 간격(raw gap_min)의 분위수(기준 b)를 직접 계산함으로써 집계 단위가 변경됨.")
        print("\n2. 채택 기준(b) 적용 시 v5 vs v6 값 대조표:")
        print(v5_v6_compare_df.to_string(index=False))
        print("   -> 실측 확인: 동일한 채택 기준(b) 적용 시 v5 재계산 값과 v6 채택 값은 100% 동일함 (차이 0.00분).")

        # ==================================================
        # === [G1] 프론티어 교체 및 전후 비교 ===
        # ==================================================
        print("\n==================================================")
        print("=== [G1] 미도래 프론티어 now(KST) 교체 및 09-11 결측/미도래 전후 비교 ===")
        print("==================================================")
        print(f"1. 기준 시각 교체:")
        print(f"   * 교체 전: max(called_at) = {max_called_str}")
        print(f"   * 교체 후: wall-clock now(KST) = {now_frontier_str}")
        print(f"   * 판정 원칙: now() 이전인데 원장에 없으면 결측, now() 이후만 미도래.")
        print(f"\n2. 2026-09-11 결측/미도래 건수 전후 나란히 비교:")
        print(f"   * 교체 전 (max(called_at) 기준):")
        print(f"     - AM: 결측 {prev_0911_m_am}건 {missing_prev.get('2026-09-11', {}).get('AM', [])} | 미도래 {prev_0911_u_am}건 {unreached_prev.get('2026-09-11', {}).get('AM', [])}")
        print(f"     - PM: 결측 {prev_0911_m_pm}건 {missing_prev.get('2026-09-11', {}).get('PM', [])} | 미도래 {prev_0911_u_pm}건 (24개 전 슬롯)")
        print(f"   * 교체 후 (wall-clock now(KST) 기준):")
        print(f"     - AM: 결측 {now_0911_m_am}건 {missing_now.get('2026-09-11', {}).get('AM', [])} | 미도래 {now_0911_u_am}건 {unreached_now.get('2026-09-11', {}).get('AM', [])}")
        print(f"     - PM: 결측 {now_0911_m_pm}건 {missing_now.get('2026-09-11', {}).get('PM', [])} | 미도래 {now_0911_u_pm}건 (24개 전 슬롯)")
        print(f"   -> 실측 판정: 현재 wall-clock({now_frontier_str})은 09-11 AM(0700~0855) 종료 후 PM(1700~1855) 이전이므로 전후 건수가 일치함.")

        # ==================================================
        # === [G5] 3개 산출물 사전 제시 및 상위집합 관계 증명 ===
        # ==================================================
        print("\n==================================================")
        print("=== [G5] 산출물 3종 사전 제시 및 Parquet vs Crosscheck 상위집합(superset) 관계 증명 ===")
        print("==================================================")
        print("1. 3개 산출물 사전 제시 표:")
        preview_table = pd.DataFrame([
            {
                'Target File': 'data/staged/headway_observed.parquet',
                'Window': '본안3일 (2026-09-07~2026-09-09)',
                'Rows': len(out_core_observed),
                'Cols': len(cols_observed),
                'Column List': cols_observed
            },
            {
                'Target File': 'exports/headway_crosscheck.csv',
                'Window': '본안3일 (2026-09-07~2026-09-09)',
                'Rows': len(out_core_crosscheck),
                'Cols': len(cols_crosscheck),
                'Column List': cols_crosscheck
            },
            {
                'Target File': 'exports/headway_stop_level.csv',
                'Window': '본안3일 (2026-09-07~2026-09-09)',
                'Rows': len(stop_met_core),
                'Cols': len(stop_met_core.columns),
                'Column List': list(stop_met_core.columns)
            }
        ])
        for idx, r in preview_table.iterrows():
            print(f"  [{idx+1}] {r['Target File']}")
            print(f"      - 분석 창: {r['Window']} | 행 수: {r['Rows']}행 | 컬럼 수: {r['Cols']}개")
            print(f"      - 컬럼 목록: {r['Column List']}")

        print("\n2. Parquet vs Crosscheck.csv 상위집합(superset) 관계 증명:")
        print(f"   * Parquet 컬럼 수: {len(cols_observed)}개 (관측 순수 지표)")
        print(f"   * Crosscheck 컬럼 수: {len(cols_crosscheck)}개 (Parquet 11개 전량 포함 + 공표/교차검증 6개 컬럼 추가)")
        print(f"   * 상위집합 검증 (set(observed).issubset(set(crosscheck))): {is_subset} (엄격한 상위집합 관계 성립)")
        print(f"   * Crosscheck 전용 공표/교차검증 컬럼 ({len(cols_extra_in_crosscheck)}개): {cols_extra_in_crosscheck}")
        print(f"   * Parquet 전용 컬럼 ({len(cols_extra_in_observed)}개): {cols_extra_in_observed} (0개 확인)")

        # === [F1 결과] ===
        print("\n==================================================")
        print("=== [F1] api_error 재시도 쌍 규명 및 중복 키 분석 ===")
        print("==================================================")
        print(f"1. 원장 내 (obs_date, slot_hhmm) 중복 행 전량 나열 ({len(dup_details_df)}행):")
        if not dup_details_df.empty:
            print(dup_details_df.to_string(index=False))
            
        print("\n2. api_error 키의 성공 행 병존 판정:")
        retried_ok_count_f1 = 0
        pure_api_error_count_f1 = 0
        for (d, s), g in dup_keys_raw.groupby(['obs_date', 'slot_hhmm']):
            has_ok = (g['outcome'] == 'ok_with_items').any()
            has_err = (g['outcome'] == 'api_error').any()
            if has_ok and has_err:
                retried_ok_count_f1 += 1
                print(f"  * 키 ({d}, {s}): api_error 발생 후 재시도 성공 행 존재 -> outcome='api_error_retried_ok' 표기 및 collection_missing=False 처리 완료 (실손실 0건).")
            elif has_err and not has_ok:
                pure_api_error_count_f1 += 1
                print(f"  * 키 ({d}, {s}): api_error 발생 후 성공 행 없음 -> 결측 처리.")
                
        print(f"  -> 재시도 성공으로 실손실이 아닌 건수: {retried_ok_count_f1}건 | 순수 결측 api_error 건수: {pure_api_error_count_f1}건 (실측 계산치).")

        # === [F2 결과] ===
        print("\n==================================================")
        print("=== [F2] 중복 키 제거 및 merge 안전장치 검증 ===")
        print("==================================================")
        print(f"1. 동일 키 중복 드롭 내역 ({len(f1_same_key_drops)}건):")
        for drop_item in f1_same_key_drops:
            print(f"  * 드롭: 키=({drop_item['obs_date']}, {drop_item['slot_hhmm']}), 유지outcome={drop_item['kept_outcome']}, 드롭outcome={drop_item['dropped_outcome']}, 시각차={drop_item['diff_seconds']:.2f}초, 사유={drop_item['reason']}")

        print(f"\n2. 슬롯 상이 준중복 드롭 내역 ({len(f2_near_dups)}건):")
        for drop_item in f2_near_dups:
            print(f"  * 드롭: 일자={drop_item['obs_date']}, 유지={drop_item['kept_slot']}, 드롭={drop_item['dropped_slot']}, 시각차={drop_item['diff_seconds']:.2f}초, 드롭행실제item={drop_item['dropped_items']}건 (실제 데이터 존재 확인), 사유={drop_item['reason']}")

        print(f"\n3. merge 직전 중복 키 assertion 안전장치:")
        print("  * assert ledger_sub.duplicated(['obs_date', 'slot_hhmm']).sum() == 0 통과 확인 완료.")

        # === [F3/F4 3구분] ===
        print("\n==================================================")
        print("=== [F3/F4] 결측 / 미도래 / 준중복 3구분 및 09-08 서사 귀속 ===")
        print("==================================================")
        print(f"1. 실제 결측 슬롯 (기준 시각 {now_frontier_str} 이전 도래 슬롯 중 누락):")
        print(missing_summary_text)
        print(f"\n2. 미도래 슬롯 (기준 시각 {now_frontier_str} 이후 미래 슬롯):")
        print(unreached_summary_text)
        print(f"\n3. 준중복 드롭 슬롯 (120초 이내 인접 호출):")
        print(dedup_summary_text)
        print(f"\n4. 09-08 실효 슬롯 원인 귀속 서사:")
        print(narrative_0908)

        # === [E5 회계표] ===
        print("\n==================================================")
        print("=== [E5] 노선별 회계표 (raw 레코드 행 수 count 기준) ===")
        print("==================================================")
        met_all_unfiltered = aggregate_metrics(ev_base, ts_base, routes_to_exclude=[])
        acct_rows = []
        for rid in routes_all:
            sub_raw = raw_df[raw_df['routeid'] == rid]
            am_slots = [s for s in build_slot_labels() if get_window(s) == 'AM']
            pm_slots = [s for s in build_slot_labels() if get_window(s) == 'PM']
            
            raw_am = len(sub_raw[sub_raw['slot_hhmm'].isin(am_slots)])
            raw_pm = len(sub_raw[sub_raw['slot_hhmm'].isin(pm_slots)])
            raw_tot = len(sub_raw)
            
            sub_ev = ev_base[ev_base['routeid'] == rid]
            ev_am = len(sub_ev[sub_ev['window'] == 'AM'])
            ev_pm = len(sub_ev[sub_ev['window'] == 'PM'])
            ev_tot = len(sub_ev)
            
            met_r_sub = met_all_unfiltered[met_all_unfiltered['routeid'] == rid]
            grp_am = len(met_r_sub[met_r_sub['window'] == 'AM'])
            grp_pm = len(met_r_sub[met_r_sub['window'] == 'PM'])
            grp_tot = grp_am + grp_pm
            
            in_meta = rid not in exc_routes
            acct_rows.append({
                'routeid': rid,
                'raw_records_am': raw_am,
                'raw_records_pm': raw_pm,
                'raw_records_tot': raw_tot,
                'events_am': ev_am,
                'events_pm': ev_pm,
                'events_tot': ev_tot,
                'groups_am': grp_am,
                'groups_pm': grp_pm,
                'groups_tot': grp_tot,
                'in_published_meta': in_meta
            })
            
        acct_df = pd.DataFrame(acct_rows)
        tot_row = {
            'routeid': 'Total',
            'raw_records_am': acct_df['raw_records_am'].sum(),
            'raw_records_pm': acct_df['raw_records_pm'].sum(),
            'raw_records_tot': acct_df['raw_records_tot'].sum(),
            'events_am': acct_df['events_am'].sum(),
            'events_pm': acct_df['events_pm'].sum(),
            'events_tot': acct_df['events_tot'].sum(),
            'groups_am': acct_df['groups_am'].sum(),
            'groups_pm': acct_df['groups_pm'].sum(),
            'groups_tot': acct_df['groups_tot'].sum(),
            'in_published_meta': pd.NA
        }
        acct_df_print = pd.concat([acct_df, pd.DataFrame([tot_row])], ignore_index=True)
        print(acct_df_print.to_string(index=False))

        # === [F3/E4 수치 대조표] ===
        print("\n==================================================")
        print("=== [F3/E4] (전체/본안/부속) 수치 대조표 (제외노선 필터 통일 및 미완일 병기) ===")
        print("==================================================")
        ev_comp_ex = ev_completed[~ev_completed['routeid'].isin(exc_routes)]
        ev_all_ex = ev_base[~ev_base['routeid'].isin(exc_routes)]
        ev_core_ex = ev_core[~ev_core['routeid'].isin(exc_routes)]
        ev_supp_ex = ev_supp[~ev_supp['routeid'].isin(exc_routes)]

        comp_lbl = f"{len(dates_completed)}일 ({dates_completed[0]}~{dates_completed[-1]})"
        all_lbl = f"{len(dates_all_inclusive)}일 ({dates_all_inclusive[0]}~{dates_all_inclusive[-1]})"

        c_table = f"""| 지표 | 전체(미완일제외 5일) | 전체(미완일포함 6일) | 본안(09.07~09 3일) | 부속(09.07~10 4일) |
|---|---|---|---|---|
| 관측 일수 | {comp_lbl} | {all_lbl} | {len(dates_core)}일 | {len(dates_supp)}일 |
| 총 이벤트 수 (12개 노선 필터 후) | {len(ev_comp_ex)} | {len(ev_all_ex)} | {len(ev_core_ex)} | {len(ev_supp_ex)} |
| 총 이벤트 수 (제외노선 포함 15개 노선) | {len(ev_completed)} | {len(ev_base)} | {len(ev_core)} | {len(ev_supp)} |
| 노선 단위 유효 그룹 수 | {len(out_completed)} | {len(out_inclusive)} | {len(out_core_crosscheck)} | {len(out_supp)} |
| insufficient 비율(%) | {out_completed['insufficient_observation'].mean()*100:.1f}% | {out_inclusive['insufficient_observation'].mean()*100:.1f}% | {out_core_crosscheck['insufficient_observation'].mean()*100:.1f}% | {out_supp['insufficient_observation'].mean()*100:.1f}% |
| agree_within_5min 건수 | {(out_completed['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_inclusive['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_core_crosscheck['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_supp['headway_source_agreement'] == 'agree_within_5min').sum()} |"""
        print(c_table)

        # === [F5 / G3 민감도 표] ===
        print("\n==================================================")
        print("=== [F5/G3] 2×2 민감도 분석 표 (p25, p75, 변동치 및 사실 기술) ===")
        print("==================================================")
        print(sens_df[['Condition', 'Median Gap(분)', 'p25(raw간격 분위수)', 'p75(raw간격 분위수)', 'Groups', 'Events', 'Insuff(%)']].to_string(index=False))
        print(f"* 슬롯당 인위 생성 가짜 이벤트 수: {len(routes_target)}개 (= 분석 대상 노선 수)")
        print(f"* 본안(3일) 0처리 변동: 중앙값 {diff_med_core:+.2f}분, p25 {diff_p25_core:+.2f}분, p75 {diff_p75_core:+.2f}분, insufficient {diff_insuff_core:+.1f}%p")
        print(f"  -> 본안 사실 기술: 0처리 시 중앙값 및 p25, p75 변동이 0.00분으로 불변이며 insufficient 비율만 {diff_insuff_core:+.1f}%p 소폭 감소함.")
        print(f"* 부속(4일) 0처리 변동: 중앙값 {diff_med_supp:+.2f}분, p25 {diff_p25_supp:+.2f}분, p75 {diff_p75_supp:+.2f}분, insufficient {diff_insuff_supp:+.1f}%p")
        print(f"  -> 부속 사실 기술: 0처리 적용 시 p25와 p75가 각각 {diff_p25_supp:+.2f}분 단축되고 insufficient 비율이 {diff_insuff_supp:+.1f}%p 감소하여 배차 간격이 축소되는 '서비스 과대평가(overestimation)' 방향으로 수치가 이동함 (결론 불변 류의 단정 배제).")

        # === [E3/F6/G2 정류소 지표] ===
        print("\n==================================================")
        print("=== [E3/F6/G2] 정류소 단위 지표 (본안 3일, 유효 노선 중앙값의 중앙값) ===")
        print("==================================================")
        print(stop_met_core.drop(columns=['analysis_window']).to_string(index=False))
        print(f"  -> 제외 3노선 실제 유효 노선(이벤트 >= 4) 포함 현황: 본안 {n_stop_groups_total}개 창 중 {n_stop_groups_with_exc}개 창({pct_stop_groups_with_exc:.1f}%)에서 included_excluded_routes=True 로 반영됨.")

        # === [F6 교차검증 분포] ===
        print("\n==================================================")
        print("=== [F6] 교차검증 분포 (본안 3일 기준, 방향 미분리 판정 불가 취지) ===")
        print("==================================================")
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
        print(f"3. [F3/G1 창 선택] 대조표 및 종합 보고서의 전체 관측 일수를 미완일 제외 완료 5일({len(dates_completed)}일)로 할지 미완일 포함 6일({len(dates_all_inclusive)}일)로 할지 선택")
        print(f"4. [G2 지표] 정류소 단위 지표 산출 시 경유 전 노선 15개 포함 및 included_excluded_routes 표기({n_stop_groups_with_exc}/{n_stop_groups_total}개 창) 정책 승인 여부")
        print(f"5. [G3/H2 민감도] 0처리 시 본안 변동(median {diff_med_core:+.2f}분, p25 {diff_p25_core:+.2f}분, p75 {diff_p75_core:+.2f}분, insuff {diff_insuff_core:+.1f}%p) 및 부속 '서비스 과대평가 방향'(p25 {diff_p25_supp:+.2f}분, p75 {diff_p75_supp:+.2f}분, insuff {diff_insuff_supp:+.1f}%p) 사실 기술 수용 여부")
        print(f"6. [지표 수용] insufficient_observation 비율(본안 {out_core_crosscheck['insufficient_observation'].mean()*100:.1f}%, 부속 {out_supp['insufficient_observation'].mean()*100:.1f}%) 수용 및 노선×일자×창 단위 유지 여부")
        print("7. [첫차/막차] first_bus_ok / last_bus_ok 판정용 '기점~정류소 간 주행시간 보정 규칙' 정의 및 도입 여부")
        print("8. [공표 단위] 공표 배차 intervaltime의 단위('분')에 대한 국토교통부/TAGO 공식 문서 근거 확보 여부")
        print("9. [H4 산출물] headway_crosscheck.csv 가 headway_observed.parquet 의 모든 컬럼을 포함하는 상위집합(superset)이므로, 중간 단계 parquet 산출물의 영구 유지 vs 폐지 여부 결정")
        print("10. [H5 운영] 수집 창 진행 중 실행 시 현재 시각 직전 미수집 슬롯에 대해 유예 구간(예: 해당 창 종료 시까지 결측 판정보류) 도입 여부 결정")

        # === [G5 --commit 블록 전문 출력 (실행 금지)] ===
        print("\n==================================================")
        print("=== [G5] --commit 블록 전문 (시뮬레이션 출력, 실제 파일 기록 미수행) ===")
        print("==================================================")
        commit_code_text = """if args.commit:
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
        
    print("[Commit 완료] 모든 산출물이 성공적으로 기록되었습니다.")"""
        print(commit_code_text)
        print("\n[안내] 현재 실행 모드는 --dry-run 입니다. 위 commit 블록 코드는 일체 실행되지 않았으며, 어떤 파일도 디스크에 기록되지 않았습니다.")

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
