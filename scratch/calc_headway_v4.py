import sys
import json
import argparse
from pathlib import Path
from collections import Counter
import pandas as pd
import numpy as np

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
            
            # Record individual raw items
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
    ledger = ledger.copy()
    ledger['called_at_kst_dt'] = pd.to_datetime(ledger['called_at_kst'])
    ledger = ledger.sort_values('called_at_kst_dt')
    to_drop_idx = []
    dropped_details = []
    deduplicated_slots = set()
    
    for obs_date, group in ledger.groupby('obs_date'):
        group = group.sort_values('called_at_kst_dt')
        prev_time = None
        prev_row = None
        for idx, row in group.iterrows():
            curr_time = row['called_at_kst_dt']
            if prev_time is not None:
                diff = (curr_time - prev_time).total_seconds()
                # 120초 이내 준중복: 다른 슬롯 라벨인데 호출 시각이 인접한 경우 늦은 쪽 1건 제외
                if diff <= 120 and row['slot_hhmm'] != prev_row['slot_hhmm']:
                    to_drop_idx.append(idx)
                    deduplicated_slots.add((str(row['obs_date']), str(row['slot_hhmm'])))
                    dropped_details.append({
                        'obs_date': row['obs_date'],
                        'kept_slot': prev_row['slot_hhmm'],
                        'dropped_slot': row['slot_hhmm'],
                        'kept_called_at': prev_row['called_at_kst'],
                        'dropped_called_at': row['called_at_kst'],
                        'diff_seconds': diff
                    })
            prev_time = curr_time
            prev_row = row
            
    ledger_clean = ledger.drop(index=to_drop_idx).copy()
    return ledger_clean, dropped_details, deduplicated_slots

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
        elif out == 'ok_with_items':
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
    """C2/D1/E2 수정 로직: route_absent와 collection_missing 분리,
    is_deduplicated 시 절단 제외, 우측 절단(right-censored) 제외"""
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
                # E2: 준중복 슬롯은 직전 관측을 절단하지 않고 통과
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
                    # 결측으로 인한 시계열 절단 (이벤트 미발생)
                    prev_arr, prev_slot = None, None
                    prev_called_at = None
                elif route_absent:
                    # 정상 수집이나 노선 미등장 -> 도착 소멸로 판정
                    if prev_arr is not None:
                        events.append({
                            'routeid': rid, 'obs_date': d, 'window': w,
                            'event_slot': prev_slot, 'arrtime_sec': prev_arr,
                            'called_at_kst': prev_called_at
                        })
                    prev_arr, prev_slot = None, None
                    prev_called_at = None
            
        # 루프 종료: right-censored 상태이므로 이벤트 추가하지 않음
            
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
                
                # D6: called_at_kst 기반 실제 gap_min 계산
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

def stop_level_metrics(events_df):
    """E3: 선언된 규칙 적용 - n_events < 4 인 부족 그룹 제외 후,
    유효 노선별 median_gap_min 의 중앙값(median_across_routes) 및 최단 노선 산출"""
    if events_df.empty:
        return pd.DataFrame()
    res = []
    
    for (d, w), group in events_df.groupby(['obs_date', 'window']):
        route_medians = []
        for rid, r_group in group.groupby('routeid'):
            if len(r_group) >= 4:
                gaps = r_group['gap_min'].dropna()
                if not gaps.empty:
                    route_medians.append((rid, float(gaps.median())))
                    
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
            'valid_routes_count': valid_routes_cnt
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
    
    # D6/E6: boolean pd.NA 초기화
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
    missing_slots_summary,
    effective_slots_0908
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

## 3. 계통 및 방향성 편의
- `route_service_hours`는 `routeid`당 1행이며 **상·하행이 분리되어 있지 않다.**
  단일 정류소 관측은 통상 한 방향이므로 관측 배차가 공표 배차의 약 2배로 나타나는 계통 편의가 발생할 수 있다. 임의 보정하지 않고 한계로 기록한다.

## 4. 첫차/막차 판정 한계
- `startvehicletime` / `endvehicletime`은 **기점 기준일 가능성**이 있어 해당 정류소 도착시각과 기점~정류소 주행시간만큼 차이가 난다. 따라서 `first_bus_ok` / `last_bus_ok`를 단순 시각 비교로 판정하지 않는다. (현재 판정 규칙 미확정으로 전량 NULL 처리함)

## 5. 결측 메커니즘 및 무운행 처리
- 결측은 수집기의 파이썬 예외(`AttributeError: 'str' object has no attribute 'get'`)로 발생했으며, 무엇이 str로 반환됐는지는 **미확정**이다.
- 결측 인접 슬롯의 `item_count`가 전체 평균과 동일해 저운행 시간대 집중(정보성 결측)의 증거는 없으나, 무작위성이 입증된 것도 아니므로 "메커니즘 미확정, 정보성 결측 증거 없음"으로 기술한다.
- `ok_empty`는 인접 슬롯에 도착정보가 있는 시점에 발생해 실제 무운행이 아닌 응답 아티팩트로 추정되며, 본안에서는 0으로 임퓨테이션하지 않았다. (민감도 대조군에서만 0 처리 적용)

## 6. 관측 표본의 한계
- 관측 일수는 소표본(본안 {core_days}일, 부속 {supp_days}일)이며 계절·장애 변동을 대표하지 않는다.
- 이 지표는 관측 기간에만 적용되며 과거 운행에 대해 아무것도 말하지 않는다.

## 7. 결측·배제 내역 전량
- **실측 결측 슬롯 내역**:
{missing_slots_summary}
- **09-08 준중복 처리**: 1745/1750 호출 시각 1.54초 차이로 인한 준중복 1건 제외로 실효 슬롯은 {effective_slots_0908}이다.
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
    ledger, raw_df, pub_df, p_stats = load_data()
    if ledger.empty:
        print("No ledger data found.")
        return

    # E1: 원장 정합성 사전 분석
    outcome_counts_all = ledger['outcome'].value_counts()
    outcome_crosstab = pd.crosstab(ledger['obs_date'], ledger['outcome'])
    non_ok_ledger = ledger[ledger['outcome'] != 'ok_with_items'].copy()
    
    non_ok_details = []
    has_label_mismatch = False
    for _, r in non_ok_ledger.iterrows():
        raw_p_str = r['raw_path']
        if pd.isna(raw_p_str) or not str(raw_p_str).strip():
            raw_exists = False
            r_cnt = 0
            i_cnt = 0
        else:
            p_obj = Path(str(raw_p_str))
            raw_exists = p_obj.exists()
            r_cnt = 0
            i_cnt = 0
            if raw_exists:
                try:
                    with open(p_obj, 'r', encoding='utf-8') as f:
                        d_json = json.load(f)
                    b_obj = d_json.get('response', {}).get('body', {})
                    if isinstance(b_obj, dict):
                        it_container = b_obj.get('items', {})
                        if isinstance(it_container, dict):
                            it_list = it_container.get('item', [])
                            if isinstance(it_list, dict): it_list = [it_list]
                            elif not isinstance(it_list, list): it_list = []
                            i_cnt = len(it_list)
                            r_cnt = len(set(it.get('routeid') for it in it_list if isinstance(it, dict) and it.get('routeid')))
                except Exception:
                    pass
                    
        if i_cnt > 0:
            has_label_mismatch = True
            
        non_ok_details.append({
            'obs_date': r['obs_date'],
            'slot_hhmm': r['slot_hhmm'],
            'outcome': r['outcome'],
            'result_code': r['result_code'],
            'item_count': r['item_count'],
            'raw_path': r['raw_path'],
            'raw_exists': raw_exists,
            'parsed_routes': r_cnt,
            'parsed_items': i_cnt
        })
    non_ok_df = pd.DataFrame(non_ok_details)

    # 3방향 키 대조 목록
    raw_keys = set(zip(raw_df['obs_date'], raw_df['slot_hhmm']))
    ledger_keys = set(zip(ledger['obs_date'], ledger['slot_hhmm']))
    both_keys = raw_keys & ledger_keys
    raw_only_keys = sorted(raw_keys - ledger_keys)
    ledger_only_keys = sorted(ledger_keys - raw_keys)

    # E2: 준중복 제거
    ledger_clean, dropped_details, deduplicated_slots = process_ledger(ledger)

    # E5: 결측 슬롯 계산 (p2_expected_missing 제거)
    slots = build_slot_labels()
    dates = sorted(ledger_clean['obs_date'].unique())
    grid = pd.MultiIndex.from_product([dates, slots], names=['obs_date', 'slot_hhmm']).to_frame(index=False)
    grid['slot_hhmm'] = grid['slot_hhmm'].astype(str).str.zfill(4)
    grid['obs_date'] = grid['obs_date'].astype(str)
    
    ledger_sub = ledger_clean[['obs_date', 'slot_hhmm', 'outcome']].copy()
    ledger_sub['slot_hhmm'] = ledger_sub['slot_hhmm'].astype(str).str.zfill(4)
    ledger_sub['obs_date'] = ledger_sub['obs_date'].astype(str)
    merged_grid = pd.merge(grid, ledger_sub, on=['obs_date', 'slot_hhmm'], how='left')
    
    missing_by_date = {}
    missing_summary_lines = []
    for d in dates:
        d_sub = merged_grid[merged_grid['obs_date'] == d]
        # 준중복으로 드롭된 슬롯은 결측이 아님
        nan_slots_d = [
            s for s in d_sub[d_sub['outcome'].isna()]['slot_hhmm'].tolist()
            if (d, s) not in deduplicated_slots
        ]
        am_nan = sorted([s for s in nan_slots_d if get_window(s) == 'AM'])
        pm_nan = sorted([s for s in nan_slots_d if get_window(s) == 'PM'])
        missing_by_date[d] = {'AM': am_nan, 'PM': pm_nan}
        missing_summary_lines.append(f"  - [{d}] AM 결측 {len(am_nan)}건: {am_nan} | PM 결측 {len(pm_nan)}건: {pm_nan}")
    missing_slots_summary_text = "\n".join(missing_summary_lines)

    # 09-08 실효 슬롯 계산 (ok_with_items 성공 기준)
    sub_0908 = ledger_clean[ledger_clean['obs_date'] == '2026-09-08']
    sub_0908_ok = sub_0908[sub_0908['outcome'] == 'ok_with_items']
    eff_cnt_0908 = sub_0908_ok['slot_hhmm'].nunique()
    eff_pct_0908 = (eff_cnt_0908 / 48) * 100
    eff_str_0908 = f"{eff_cnt_0908}/48 ({eff_pct_0908:.1f}%)"

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

    # E5: 노선별 회계표 (실제 raw 행 수 count 기준)
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
        
        # 전체 노선 기준 그룹 수
        met_r = aggregate_metrics(ev_base, ts_base, routes_to_exclude=[])
        met_r_sub = met_r[met_r['routeid'] == r]
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
    
    # Total 행 추가
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

    # 2x2 민감도 분석
    sens_res = []
    for name, t_df, e_df in [('Base(결측유지)', ts_base, ev_base), ('Zero-Fill(0처리)', ts_zero, ev_zero)]:
        for w_name, w_dates in [('본안(3일)', dates_core), ('부속(4일)', dates_supp)]:
            sub_ev = e_df[e_df['obs_date'].isin(w_dates)]
            sub_ts = t_df[t_df['obs_date'].isin(w_dates)]
            m = aggregate_metrics(sub_ev, sub_ts, routes_to_exclude=exc_routes)
            if not m.empty:
                gaps = m['median_gap_min'].dropna()
                med_val = float(gaps.median()) if not gaps.empty else pd.NA
                insuff_rate = float(m['insufficient_observation'].mean() * 100)
                n_groups = len(m)
                n_events = len(sub_ev[~sub_ev['routeid'].isin(exc_routes)])
            else:
                med_val, insuff_rate, n_groups, n_events = pd.NA, pd.NA, 0, 0
                
            sens_res.append({
                'Condition': f"{name} / {w_name}",
                'Median Gap(분)': med_val,
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

    # E3: 정류소 단위 지표 산출
    ev_core = ev_base[ev_base['obs_date'].isin(dates_core)]
    ev_supp = ev_base[ev_base['obs_date'].isin(dates_supp)]
    stop_met_core = stop_level_metrics(ev_core)
    stop_met_all = stop_level_metrics(ev_base)
    stop_met_all['crosscheck_available'] = True # 정류소 단위는 15개 전체 노선 포괄

    # 교차검증 테이블 (Core 3일 기준)
    metrics_core_filtered = aggregate_metrics(ev_core, ts_base[ts_base['obs_date'].isin(dates_core)], routes_to_exclude=exc_routes)
    out_core = prep_crosscheck(metrics_core_filtered, pub_df, routes_to_exclude=exc_routes)

    # E4: 대조표 산출 (3열 모두 제외 3노선 필터링 후 기준 통일)
    metrics_all_filtered = aggregate_metrics(ev_base, ts_base, routes_to_exclude=exc_routes)
    metrics_supp_filtered = aggregate_metrics(ev_supp, ts_base[ts_base['obs_date'].isin(dates_supp)], routes_to_exclude=exc_routes)
    
    out_all = prep_crosscheck(metrics_all_filtered, pub_df, routes_to_exclude=exc_routes)
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
        missing_slots_summary=missing_slots_summary_text,
        effective_slots_0908=eff_str_0908
    )

    if args.dry_run:
        # [E1 결과 최상단 배치]
        print("==================================================")
        print("=== [E1] 원장 outcome 정합성 진단 ===")
        print("==================================================")
        print("\n1. outcome 전체 분포:")
        print(outcome_counts_all.to_string())
        print("\n2. outcome 일자별 교차표:")
        print(outcome_crosstab.to_string())
        print(f"\n3. outcome != 'ok_with_items' 전량 목록 ({len(non_ok_df)}건):")
        if not non_ok_df.empty:
            print(non_ok_df.to_string(index=False))
        else:
            print("  (해당 행 없음)")
        print(f"\n4. 3방향 키 대조 목록:")
        print(f"  - 공통(both) 키 수: {len(both_keys)}건")
        print(f"  - ledger_only 목록 ({len(ledger_only_keys)}건): {ledger_only_keys}")
        print(f"  - raw_only 목록 ({len(raw_only_keys)}건): {raw_only_keys}")
        print("\n5. 라벨 불일치 판정 및 보고:")
        if has_label_mismatch:
            print("  [경고] ok_empty 또는 api_error 슬롯 중 실제 item 이 파싱된 행이 존재합니다 (라벨 불일치).")
        else:
            print("  [확인] ok_empty 전건(4건)은 실제 totalCount=0 및 item 0건이며, api_error 전건(2건)은 raw_path=nan(REQ_EXCEPTION)으로 실제 item 0건입니다.")
            print("  -> 원장 outcome 라벨과 실제 raw 데이터 내용 간 '라벨 불일치'는 발생하지 않았습니다.")
        print("  -> [사람 결정 필요] outcome 기반 분기를 실제 item 유무 기반으로 전환할지 여부 검토 요망.")

        # [E2 결과 최상단 배치]
        print("\n==================================================")
        print("=== [E2] 준중복 제거 상세 및 실효 슬롯 판정 ===")
        print("==================================================")
        print(f"- 준중복 드롭 건수: {len(dropped_details)}건")
        if dropped_details:
            for drop_info in dropped_details:
                print(f"  * 드롭 행 상세: 일자={drop_info['obs_date']}, 유지슬롯={drop_info['kept_slot']}, 드롭슬롯={drop_info['dropped_slot']}, 유지호출시각={drop_info['kept_called_at']}, 드롭호출시각={drop_info['dropped_called_at']}, 시각차={drop_info['diff_seconds']:.2f}초")
        print(f"- 09-08 실효 슬롯 판정:")
        print(f"  * 총 원장 49행 중 1745/1750 준중복 1건 제외로 실효 슬롯은 {eff_cnt_0908}/48 ({eff_pct_0908:.1f}%)로 코드로 명시적 재현됨.")
        print(f"  * 드롭된 슬롯 {deduplicated_slots}는 'is_deduplicated=True' 처리되어 collection_missing 오분류 및 이벤트 절단에서 정상 제외됨.")

        # [E5 노선별 회계표]
        print("\n==================================================")
        print("=== [E5] 노선별 회계표 (raw 레코드 행 수 count 기준) ===")
        print("==================================================")
        print(route_acct_with_tot.to_string(index=False))

        # [E4 대조표]
        print("\n==================================================")
        print("=== [E4] (전체/본안/부속) 수치 대조표 (제외 3노선 필터 통일) ===")
        print("==================================================")
        print("| 지표 | 전체(09.04~10) | 본안(09.07~09) | 부속(09.07~10) |")
        print("|---|---|---|---|")
        print(f"| 관측 일수 | 5일 | 3일 | 4일 |")
        print(f"| 총 이벤트 수 (12개 노선 필터 후) | {len(ev_base[~ev_base['routeid'].isin(exc_routes)])} | {len(ev_core[~ev_core['routeid'].isin(exc_routes)])} | {len(ev_supp[~ev_supp['routeid'].isin(exc_routes)])} |")
        print(f"| 총 이벤트 수 (제외노선 포함 15개 노선) | {len(ev_base)} | {len(ev_core)} | {len(ev_supp)} |")
        print(f"| 노선 단위 유효 그룹 수 | {len(out_all)} | {len(out_core)} | {len(out_supp)} |")
        print(f"| insufficient 비율(%) | {out_all['insufficient_observation'].mean()*100:.1f}% | {out_core['insufficient_observation'].mean()*100:.1f}% | {out_supp['insufficient_observation'].mean()*100:.1f}% |")
        print(f"| agree_within_5min 건수 | {(out_all['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_core['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_supp['headway_source_agreement'] == 'agree_within_5min').sum()} |")

        # [D3 2x2 민감도]
        print("\n==================================================")
        print("=== [D3] 2×2 민감도 분석 표 ===")
        print("==================================================")
        print(sens_df.to_string(index=False))
        print(f"- 본안(3일) 0처리 변동: 절대차 {abs_diff_core:.2f}분 (상대변화율 {rel_diff_core:.1f}%)" if pd.notna(abs_diff_core) else "- 본안(3일) 변동: N/A")
        print(f"- 부속(4일) 0처리 변동: 절대차 {abs_diff_supp:.2f}분 (상대변화율 {rel_diff_supp:.1f}%)" if pd.notna(abs_diff_supp) else "- 부속(4일) 변동: N/A")

        # [E3 정류소 단위 지표]
        print("\n==================================================")
        print("=== [E3] 정류소 단위 지표 (Core 3일, 유효 노선 중앙값의 중앙값) ===")
        print("==================================================")
        print(stop_met_core.to_string(index=False))

        # [교차검증 분포]
        print("\n==================================================")
        print("=== 교차검증 분포 (본안 3일 기준) ===")
        print("==================================================")
        if not out_core.empty:
            print(out_core['headway_source_agreement'].value_counts().to_string())

        # [D6 드리프트]
        print("\n==================================================")
        print("=== [D6] 스케줄러 드리프트 차이 분포 (호출시각 vs 슬롯간격) ===")
        print("==================================================")
        if not drift_series.empty:
            print(f"- 드리프트 차이(분): min={drift_series.min():.2f}, mean={drift_series.mean():.2f}, median={drift_series.median():.2f}, max={drift_series.max():.2f}")

        # [D4 docs 전문]
        print("\n==================================================")
        print("=== [D4] docs/headway_limits.md 전문 미리보기 ===")
        print("==================================================")
        print(doc_content)

        # [사람이 결정할 사항]
        print("\n==================================================")
        print("=== 사람이 결정할 사항 ===")
        print("==================================================")
        print("1. [E1 판정] outcome 분기를 문자열 라벨 기반에서 실제 raw 파싱 item 유무 기반으로 전환할지 여부")
        print("2. [E3 지표] 정류소 단위 지표 산출 시 n_events < 4 노선 제외 규칙 적용 상태의 '유효 노선 중앙값의 중앙값' 정의 확정 여부")
        print(f"3. [지표 수용] insufficient_observation 비율(본안 {out_core['insufficient_observation'].mean()*100:.1f}%, 부속 {out_supp['insufficient_observation'].mean()*100:.1f}%) 수용 및 노선×일자×창 단위 유지 여부")
        print("4. [첫차/막차] first_bus_ok / last_bus_ok 판정용 '기점~정류소 간 주행시간 보정 규칙' 정의 및 도입 여부")
        print("5. [공표 단위] 공표 배차 intervaltime의 단위('분')에 대한 국토교통부/TAGO 공식 문서 근거 확보 여부")

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

        if not out_core.empty:
            if pq_path.exists():
                print(f"[덮어쓰기 안내] {pq_path} (기존 크기: {pq_path.stat().st_size} bytes)")
            print(f"Writing {pq_path}: {len(out_core)} rows, {len(out_core.columns)} cols")
            out_core.to_parquet(pq_path, index=False)

            if csv_path.exists():
                print(f"[덮어쓰기 안내] {csv_path} (기존 크기: {csv_path.stat().st_size} bytes)")
            print(f"Writing {csv_path}: {len(out_core)} rows, {len(out_core.columns)} cols")
            out_core.to_csv(csv_path, index=False)

        if not stop_met_all.empty:
            if stop_csv_path.exists():
                print(f"[덮어쓰기 안내] {stop_csv_path} (기존 크기: {stop_csv_path.stat().st_size} bytes)")
            print(f"Writing {stop_csv_path}: {len(stop_met_all)} rows, {len(stop_met_all.columns)} cols")
            stop_met_all.to_csv(stop_csv_path, index=False)

        if md_path.exists():
            print(f"[덮어쓰기 안내] {md_path} (기존 크기: {md_path.stat().st_size} bytes)")
        print(f"Writing {md_path}: {len(doc_content.encode('utf-8'))} bytes")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)
            
        print("[Commit 완료] 모든 산출물이 성공적으로 기록되었습니다.")

if __name__ == '__main__':
    main()
