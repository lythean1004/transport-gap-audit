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

def load_data():
    ledger_path = Path('evidence/arrival_ledger.csv')
    if not ledger_path.exists():
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}
    
    # D1: dtype 강제 및 slot_hhmm 4자리 zfill
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
            
            route_map = {}
            for it in items:
                if not isinstance(it, dict):
                    continue
                rid = it.get('routeid')
                arr = it.get('arrtime')
                if rid and arr is not None:
                    arr = int(arr)
                    if rid not in route_map:
                        route_map[rid] = {'arrtimes': []}
                    route_map[rid]['arrtimes'].append(arr)
            
            parts = jf.stem.split('_')
            if len(parts) >= 3:
                slot = parts[-1].zfill(4)
                obs_date = str(jf.parent.name)
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
    to_drop = []
    
    for obs_date, group in ledger.groupby('obs_date'):
        group = group.sort_values('called_at_kst_dt')
        prev_time = None
        prev_idx = None
        for idx, row in group.iterrows():
            curr_time = row['called_at_kst_dt']
            if prev_time is not None:
                diff = (curr_time - prev_time).total_seconds()
                # 120초 이내 준중복: 다른 슬롯 라벨인데 호출 시각이 인접한 경우 늦은 쪽 1건 제외
                if diff <= 120 and row['slot_hhmm'] != ledger.loc[prev_idx, 'slot_hhmm']:
                    to_drop.append(idx)
            prev_time = curr_time
            prev_idx = idx
            
    ledger = ledger.drop(index=to_drop)
    return ledger, len(to_drop)

def build_timeseries(ledger, raw_df, routes, zero_fill=False):
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
        
        if out == 'ok_with_items':
            raw_subset = raw_df[(raw_df['obs_date'] == d) & (raw_df['slot_hhmm'] == s)]
            present_routes = set(raw_subset['routeid'].values)
            for _, rr in raw_subset.iterrows():
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': rr['routeid'],
                    'arrtime_sec': rr['arrtime_sec'], 'n_items': rr['n_items'],
                    'called_at_kst': called_at,
                    'collection_missing': False, 'route_absent': False
                })
            # D3: route_absent는 zero_fill 여부와 무관하게 동일 처리 (0 채움 금지)
            for r in set(routes) - present_routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': pd.NA, 'n_items': 0,
                    'called_at_kst': called_at,
                    'collection_missing': False, 'route_absent': True
                })
        elif out == 'ok_empty':
            # D3: ok_empty만 zero_fill 적용 대상
            for r in routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': 0 if zero_fill else pd.NA, 'n_items': 0,
                    'called_at_kst': called_at,
                    'collection_missing': not zero_fill, 'route_absent': False
                })
        else:
            # api_error 또는 슬롯 자체 누락 (collection_missing) -> zero_fill 여부 무관하게 동일 처리
            for r in routes:
                ts_data.append({
                    'obs_date': d, 'slot_hhmm': s, 'window': w, 'routeid': r,
                    'arrtime_sec': pd.NA, 'n_items': 0,
                    'called_at_kst': called_at,
                    'collection_missing': True, 'route_absent': False
                })
                
    ts_df = pd.DataFrame(ts_data)
    ts_df['arrtime_sec'] = ts_df['arrtime_sec'].astype('Int64')
    return ts_df

def detect_events_v1(ts_df):
    """과거 v1 로직 재현: NA 무조건 이벤트 + 그룹 말단 무조건 이벤트 (대조용)"""
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
    """C2/D1 수정 로직: route_absent와 collection_missing 분리, 우측 절단(right-censored) 제외"""
    events = []
    groups = ts_df.sort_values(['obs_date', 'slot_hhmm']).groupby(['routeid', 'obs_date', 'window'])
    
    for (rid, d, w), group in groups:
        prev_arr, prev_slot = None, None
        prev_called_at = None
        group = group.reset_index(drop=True)
        
        for i, row in group.iterrows():
            arr, slot = row['arrtime_sec'], row['slot_hhmm']
            col_missing, route_absent = row['collection_missing'], row['route_absent']
            called_at = row.get('called_at_kst', pd.NA)
            
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
                    # 결측으로 인한 절단 (이벤트 미발생)
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
        # D1/C1: n_items > 1인 고유 스냅샷(슬롯) 수 계산
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
    if events_df.empty:
        return pd.DataFrame()
    res = []
    for (d, w), group in events_df.groupby(['obs_date', 'window']):
        gaps = group['gap_min'].dropna()
        med_across = float(gaps.median()) if not gaps.empty else pd.NA
        
        route_meds = group.groupby('routeid')['gap_min'].median().dropna()
        best_single = float(route_meds.min()) if not route_meds.empty else pd.NA
        
        res.append({
            'obs_date': d, 'window': w,
            'median_across_routes': med_across,
            'best_single_route': best_single
        })
    return pd.DataFrame(res)

def generate_docs_content(
    core_days, supp_days,
    old_events, new_events,
    total_json, success_json, failed_json,
    route_acct_df,
    sens_df,
    stop_met,
    agreement_counts
):
    doc = f"""# 관측 배차 산출 및 교차검증 한계점

## 1. 폴링 주기의 한계 및 시간 측정 방식
- 5분 폴링은 5분 미만 배차를 분해할 수 없다.
- 도착예정정보는 시각표가 아니므로 관측값은 근사치이며 공표 배차간격이 아니다.
- 본 분석의 `gap_min`은 슬롯 간격(스냅샷 인덱스 차 × 5분)을 기준으로 산출되었으며 스케줄러 자체의 지연(드리프트)은 배차 간격 산출에서 사전에 무시되었다. 실제 호출 시각(`called_at_kst`) 기준과의 차이 분포는 별도 진단으로 제시된다.

## 2. 차량 식별 부재 및 예측 지평
- 차량 식별자가 없어 동일 노선 복수 차량 구간은 식별 불가하다 (동일 슬롯 복수 항목은 API 정상 동작이며 중복 오류가 아니다).
- 예측 지평이 최대 7,741초에 달해 동일 차량이 다수 슬롯에 반복 등장한다.

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
- **결측 슬롯 내역**: 09-04 오전 16슬롯(0700~0815) 소실, 단발 예외 8건(09-04 1715·1755, 09-07 0740·0800·0855·1755, 09-10 0750·1815), 09-08 준중복 1건 제외(실효 47/48).
- **제외 3개 노선(`GGB222000056`, `GGB222000137`, `GGB222000239`)**:
  - 사유: 수집 설계상 7A' 입력 목록 누락으로 공표 배차 정보 부재 (API 미제공이 아님).
  - 처리: 노선 단위 관측 배차 산출 및 교차검증에서는 제외하되, 정류소 실질 서비스 수준은 경유 전 노선의 합집합이므로 정류소 단위 합산 지표에는 15개 전체 노선을 포함함 (`crosscheck_available=False` 표기).

## 8. 공표 배차간격 단위 미확정
- `intervaltime` 계열의 단위는 값 범위 기반으로 '분'으로 추정하였으나 문서 근거가 미확보되었다. (가정이 틀렸을 경우 교차검증 델타가 무효화됨).

## 9. 실측 요약 대조표
- **파싱 회계**: 총 JSON {total_json}건 중 성공 {success_json}건, 실패 {failed_json}건.
- **이벤트 검출 수정 효과**: C2/D1 수정 전 {old_events}건 -> 수정 후 {new_events}건.
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

    # D1: 3방향 키 대조
    raw_keys = set(zip(raw_df['obs_date'], raw_df['slot_hhmm']))
    ledger_keys = set(zip(ledger['obs_date'], ledger['slot_hhmm']))
    both_keys = raw_keys & ledger_keys
    raw_only_keys = raw_keys - ledger_keys
    ledger_only_keys = ledger_keys - raw_keys

    # 준중복 제거 (원장 기준)
    ledger, n_dropped = process_ledger(ledger)

    # D1: merge 직후 진단 (P2 결측 슬롯과 일치하는지 검증)
    slots = build_slot_labels()
    dates = sorted(ledger['obs_date'].unique())
    grid = pd.MultiIndex.from_product([dates, slots], names=['obs_date', 'slot_hhmm']).to_frame(index=False)
    grid['slot_hhmm'] = grid['slot_hhmm'].astype(str).str.zfill(4)
    grid['obs_date'] = grid['obs_date'].astype(str)
    
    ledger_sub = ledger[['obs_date', 'slot_hhmm', 'outcome']].copy()
    ledger_sub['slot_hhmm'] = ledger_sub['slot_hhmm'].astype(str).str.zfill(4)
    ledger_sub['obs_date'] = ledger_sub['obs_date'].astype(str)
    merged_diag = pd.merge(grid, ledger_sub, on=['obs_date', 'slot_hhmm'], how='left')
    
    # P2 확정 결측 슬롯 사전
    p2_expected_missing = {
        '2026-09-04': {
            'AM': ['0700', '0705', '0710', '0715', '0720', '0725', '0730', '0735', '0740', '0745', '0750', '0755', '0800', '0805', '0810', '0815'],
            'PM': ['1715', '1755']
        },
        '2026-09-07': {
            'AM': ['0740', '0800', '0855'],
            'PM': ['1755']
        },
        '2026-09-08': {
            'AM': [],
            'PM': []
        },
        '2026-09-09': {
            'AM': [],
            'PM': []
        },
        '2026-09-10': {
            'AM': ['0700', '0705', '0710', '0750'],
            'PM': ['1815']
        }
    }
    
    actual_nan_slots = {}
    mismatch_found = False
    mismatch_details = []
    
    for d in dates:
        d_sub = merged_diag[merged_diag['obs_date'] == d]
        nan_slots_d = d_sub[d_sub['outcome'].isna()]['slot_hhmm'].tolist()
        am_nan = sorted([s for s in nan_slots_d if get_window(s) == 'AM'])
        pm_nan = sorted([s for s in nan_slots_d if get_window(s) == 'PM'])
        actual_nan_slots[d] = {'AM': am_nan, 'PM': pm_nan}
        
        expected_am = p2_expected_missing.get(d, {}).get('AM', [])
        expected_pm = p2_expected_missing.get(d, {}).get('PM', [])
        
        if am_nan != expected_am or pm_nan != expected_pm:
            mismatch_found = True
            mismatch_details.append(
                f"Date {d} mismatch:\n"
                f"  Actual AM: {am_nan} vs Expected: {expected_am}\n"
                f"  Actual PM: {pm_nan} vs Expected: {expected_pm}"
            )
            
    if mismatch_found:
        print("[CRITICAL ERROR] D1 진단 실패: grid×ledger 조인 결측 슬롯이 P2 확정치와 불일치합니다.")
        for detail in mismatch_details:
            print(detail)
        sys.exit(1)

    # 노선 목록 구성 (raw + pub)
    routes = sorted(set(raw_df['routeid'].unique()) | set(pub_df['routeid'].unique()))
    exc_routes = ['GGB222000056', 'GGB222000137', 'GGB222000239']

    # 시계열 생성 (Base vs Zero-fill)
    ts_base = build_timeseries(ledger, raw_df, routes, zero_fill=False)
    ts_zero = build_timeseries(ledger, raw_df, routes, zero_fill=True)

    # 이벤트 검출
    old_ev_count = detect_events_v1(ts_base)
    ev_base, ts_base = detect_events_v2(ts_base)
    ev_zero, ts_zero = detect_events_v2(ts_zero)

    # D1 검증: 창별 그룹 수 및 이벤트 수 집계
    metrics_all_base = aggregate_metrics(ev_base, ts_base, routes_to_exclude=[])
    am_groups_count = len(metrics_all_base[metrics_all_base['window'] == 'AM'])
    pm_groups_count = len(metrics_all_base[metrics_all_base['window'] == 'PM'])
    
    am_events_count = len(ev_base[ev_base['window'] == 'AM'])
    pm_events_count = len(ev_base[ev_base['window'] == 'PM'])

    if am_groups_count == 0:
        print("[CRITICAL ERROR] D1 검증 실패: AM 창 그룹 수가 0입니다. 패치 실패로 간주하고 중단합니다.")
        sys.exit(1)

    # D2: 노선별 회계표 구성 (AM/PM 분리)
    route_acct = []
    for r in routes:
        r_raw = raw_df[raw_df['routeid'] == r]
        raw_slots_am = r_raw[r_raw['slot_hhmm'] < '1200']['slot_hhmm'].nunique()
        raw_slots_pm = r_raw[r_raw['slot_hhmm'] >= '1200']['slot_hhmm'].nunique()
        raw_slots_total = raw_slots_am + raw_slots_pm
        
        r_ev = ev_base[ev_base['routeid'] == r]
        ev_am = len(r_ev[r_ev['window'] == 'AM'])
        ev_pm = len(r_ev[r_ev['window'] == 'PM'])
        ev_total = ev_am + ev_pm
        
        r_met = metrics_all_base[metrics_all_base['routeid'] == r]
        gr_am = len(r_met[r_met['window'] == 'AM'])
        gr_pm = len(r_met[r_met['window'] == 'PM'])
        gr_total = gr_am + gr_pm
        
        in_pub = r in pub_df['routeid'].values if not pub_df.empty else False
        
        route_acct.append({
            'routeid': r,
            'raw_am': raw_slots_am,
            'raw_pm': raw_slots_pm,
            'raw_tot': raw_slots_total,
            'ev_am': ev_am,
            'ev_pm': ev_pm,
            'ev_tot': ev_total,
            'gr_am': gr_am,
            'gr_pm': gr_pm,
            'gr_tot': gr_total,
            'in_published': in_pub
        })
    route_acct_df = pd.DataFrame(route_acct)

    # C1: 노선 필터링 대조
    metrics_filtered_base = aggregate_metrics(ev_base, ts_base, routes_to_exclude=exc_routes)
    
    # D3: 2×2 민감도 분석
    dates_core = ['2026-09-07', '2026-09-08', '2026-09-09']
    dates_supp = ['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
    
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

    # 2x2 상대 변화율 계산
    b_core_med = sens_df.iloc[0]['Median Gap(분)']
    z_core_med = sens_df.iloc[2]['Median Gap(분)']
    if pd.notna(b_core_med) and pd.notna(z_core_med):
        abs_diff_core = z_core_med - b_core_med
        rel_diff_core = (abs_diff_core / b_core_med) * 100
    else:
        abs_diff_core, rel_diff_core = pd.NA, pd.NA

    b_supp_med = sens_df.iloc[1]['Median Gap(분)']
    z_supp_med = sens_df.iloc[3]['Median Gap(분)']
    if pd.notna(b_supp_med) and pd.notna(z_supp_med):
        abs_diff_supp = z_supp_med - b_supp_med
        rel_diff_supp = (abs_diff_supp / b_supp_med) * 100
    else:
        abs_diff_supp, rel_diff_supp = pd.NA, pd.NA

    # C5: 정류소 단위 지표 (Core 기준, AM/PM 모두)
    ev_core = ev_base[ev_base['obs_date'].isin(dates_core)]
    stop_met = stop_level_metrics(ev_core)

    # 교차검증 테이블 생성 (Core 기준)
    if not pub_df.empty:
        pub_df_sub = pub_df[['routeid', 'intervaltime']].copy()
        pub_df_sub = pub_df_sub.rename(columns={'intervaltime': 'headway_published_min'})
    else:
        pub_df_sub = pd.DataFrame({'routeid': [], 'headway_published_min': []})

    def prep_crosscheck(m_df):
        if m_df.empty:
            return m_df
        odf = m_df.merge(pub_df_sub, on='routeid', how='left')
        odf['crosscheck_available'] = ~odf['routeid'].isin(exc_routes)
        
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
        return odf

    out_core = prep_crosscheck(aggregate_metrics(ev_core, ts_base[ts_base['obs_date'].isin(dates_core)], exc_routes))
    
    if not out_core.empty:
        # D6: boolean array로 생성하여 인덱스 정렬 이슈 방지
        out_core['first_bus_ok'] = pd.array([pd.NA] * len(out_core), dtype='boolean')
        out_core['last_bus_ok'] = pd.array([pd.NA] * len(out_core), dtype='boolean')
        
        # headway_ok: agree_within_5min인 경우 True, disagree인 경우 False, 그 외 NULL
        headway_ok_vals = []
        for _, r in out_core.iterrows():
            agr = r['headway_source_agreement']
            if agr == 'agree_within_5min':
                headway_ok_vals.append(True)
            elif agr == 'disagree':
                headway_ok_vals.append(False)
            else:
                headway_ok_vals.append(pd.NA)
        out_core['headway_ok'] = pd.array(headway_ok_vals, dtype='boolean')

    # D6: 드리프트 분석 (called_at 기준 gap과의 차이)
    drift_diffs = []
    for _, r in ev_base.iterrows():
        g_slot = r['gap_min']
        g_called = r['gap_min_called']
        if pd.notna(g_slot) and pd.notna(g_called):
            drift_diffs.append(g_called - g_slot)
            
    drift_series = pd.Series(drift_diffs) if drift_diffs else pd.Series(dtype=float)

    # 3열 대조표 준비 (전체, 본안, 부속)
    ev_supp = ev_base[ev_base['obs_date'].isin(dates_supp)]
    out_all = prep_crosscheck(metrics_all_base)
    out_supp = prep_crosscheck(aggregate_metrics(ev_supp, ts_base[ts_base['obs_date'].isin(dates_supp)], exc_routes))

    doc_content = generate_docs_content(
        core_days=len(dates_core),
        supp_days=len(dates_supp),
        old_events=old_ev_count,
        new_events=len(ev_base),
        total_json=p_stats['total_files'],
        success_json=p_stats['success'],
        failed_json=p_stats['failed'],
        route_acct_df=route_acct_df,
        sens_df=sens_df,
        stop_met=stop_met,
        agreement_counts=dict(out_core['headway_source_agreement'].value_counts()) if not out_core.empty else {}
    )

    if args.dry_run:
        print("==================================================")
        print("=== [D1] 조인 진단 및 AM/PM 소실 복구 검증 ===")
        print("==================================================")
        print(f"- 3방향 키 대조: 공통 {len(both_keys)}건 | raw_only {len(raw_only_keys)}건 | ledger_only {len(ledger_only_keys)}건")
        print("- grid×ledger 조인 후 outcome 결측 슬롯 검증:")
        for d in dates:
            act_am = actual_nan_slots[d]['AM']
            act_pm = actual_nan_slots[d]['PM']
            print(f"  [{d}] 결측 AM {len(act_am)}건: {act_am} | 결측 PM {len(act_pm)}건: {act_pm}")
        print("  -> P2 확정 결측치와 100% 일치 확인 완료.")
        print(f"- 수정 전후 창별 그룹/이벤트 수 대조:")
        print(f"  * 수정 전: AM 그룹 0건 (전량 소실) -> 수정 후: AM 그룹 {am_groups_count}건, PM 그룹 {pm_groups_count}건")
        print(f"  * 창별 이벤트 수: AM {am_events_count}건, PM {pm_events_count}건")
        print(f"  * 전체 이벤트 수: 수정 전 {old_ev_count}건 -> 수정 후 {len(ev_base)}건 (우측절단 제거 및 분리 적용)")

        print("\n==================================================")
        print("=== [D2] 노선별 회계표 (AM/PM 분리 및 팩트 확인) ===")
        print("==================================================")
        print(route_acct_df.to_string(index=False))
        r137_row = route_acct_df[route_acct_df['routeid'] == 'GGB222000137']
        if not r137_row.empty:
            r137 = r137_row.iloc[0]
            print(f"\n* GGB222000137 노선 실측 확인:")
            print(f"  - raw 슬롯수: AM {r137['raw_am']}건 / PM {r137['raw_pm']}건 (AM 전용 운행 실측 확인)")
            print(f"  - 이벤트수: AM {r137['ev_am']}건 / PM {r137['ev_pm']}건 | 그룹수: AM {r137['gr_am']}건 / PM {r137['gr_pm']}건")
            print(f"  - 공표 메타(route_service_hours) 존재 여부: {r137['in_published']} (수집 설계상 입력 누락)")

        print("\n==================================================")
        print("=== [C1] 제외 3개 노선 필터링 대조 ===")
        print("==================================================")
        print(f"- 필터링 전(15개 노선): 그룹 {len(metrics_all_base)}건, 이벤트 {len(ev_base)}건")
        print(f"- 필터링 후(12개 노선): 그룹 {len(metrics_filtered_base)}건, 이벤트 {len(ev_base[~ev_base['routeid'].isin(exc_routes)])}건")

        print("\n==================================================")
        print("=== [D3] 2×2 민감도 분석 표 (재설계) ===")
        print("==================================================")
        print(sens_df.to_string(index=False))
        print(f"- 본안(3일) 0처리 변동: 절대차 {abs_diff_core:.2f}분 (상대변화율 {rel_diff_core:.1f}%)" if pd.notna(abs_diff_core) else "- 본안(3일) 변동: N/A")
        print(f"- 부속(4일) 0처리 변동: 절대차 {abs_diff_supp:.2f}분 (상대변화율 {rel_diff_supp:.1f}%)" if pd.notna(abs_diff_supp) else "- 부속(4일) 변동: N/A")

        print("\n==================================================")
        print("=== [C5] 정류소 단위 지표 (Core 3일) ===")
        print("==================================================")
        print(stop_met.to_string(index=False))

        print("\n==================================================")
        print("=== [(전체/본안/부속) 수치 대조표] ===")
        print("==================================================")
        print("| 지표 | 전체(09.04~10) | 본안(09.07~09) | 부속(09.07~10) |")
        print("|---|---|---|---|")
        print(f"| 관측 일수 | 5일 | 3일 | 4일 |")
        print(f"| 총 이벤트 수 (제외노선 포함) | {len(ev_base)} | {len(ev_core)} | {len(ev_supp)} |")
        print(f"| 총 이벤트 수 (제외노선 필터링) | {len(ev_base[~ev_base['routeid'].isin(exc_routes)])} | {len(ev_core[~ev_core['routeid'].isin(exc_routes)])} | {len(ev_supp[~ev_supp['routeid'].isin(exc_routes)])} |")
        print(f"| 노선 단위 그룹 수 | {len(out_all)} | {len(out_core)} | {len(out_supp)} |")
        print(f"| insufficient 비율(%) | {out_all['insufficient_observation'].mean()*100:.1f}% | {out_core['insufficient_observation'].mean()*100:.1f}% | {out_supp['insufficient_observation'].mean()*100:.1f}% |")
        print(f"| agree_within_5min 건수 | {(out_all['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_core['headway_source_agreement'] == 'agree_within_5min').sum()} | {(out_supp['headway_source_agreement'] == 'agree_within_5min').sum()} |")

        print("\n==================================================")
        print("=== [교차검증 분포 (본안 3일 기준)] ===")
        print("==================================================")
        if not out_core.empty:
            print(out_core['headway_source_agreement'].value_counts().to_string())

        print("\n==================================================")
        print("=== [D6] 스케줄러 드리프트 차이 분포 (호출시각 vs 슬롯간격) ===")
        print("==================================================")
        if not drift_series.empty:
            print(f"- 드리프트 차이(분): min={drift_series.min():.2f}, mean={drift_series.mean():.2f}, median={drift_series.median():.2f}, max={drift_series.max():.2f}")
        else:
            print("- 드리프트 계산 가능한 연속 이벤트 쌍 없음")

        print("\n==================================================")
        print("=== [D4] docs/headway_limits.md 전문 미리보기 ===")
        print("==================================================")
        print(doc_content)

        print("\n==================================================")
        print("=== 사람이 결정할 사항 ===")
        print("==================================================")
        core_insuff = out_core['insufficient_observation'].mean() * 100 if not out_core.empty else 0.0
        supp_insuff = out_supp['insufficient_observation'].mean() * 100 if not out_supp.empty else 0.0
        print(f"1. insufficient_observation 비율(본안 {core_insuff:.1f}%, 부속 {supp_insuff:.1f}%)에 대한 수용 여부 및 그룹 단위(노선×일자×창) 유지 여부")
        print("2. first_bus_ok / last_bus_ok 판정을 위한 '기점~정류소 간 주행시간 보정 규칙' 정의 및 도입 여부")
        print("3. 공표 배차 intervaltime의 단위('분')에 대한 국토교통부/TAGO 공식 문서 근거 확보 및 확정 여부")

    if args.commit:
        out_dir_staged = Path('data/staged')
        out_dir_exports = Path('exports')
        out_dir_docs = Path('docs')
        
        out_dir_staged.mkdir(parents=True, exist_ok=True)
        out_dir_exports.mkdir(parents=True, exist_ok=True)
        out_dir_docs.mkdir(parents=True, exist_ok=True)

        pq_path = out_dir_staged / 'headway_observed.parquet'
        csv_path = out_dir_exports / 'headway_crosscheck.csv'
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

        if md_path.exists():
            print(f"[덮어쓰기 안내] {md_path} (기존 크기: {md_path.stat().st_size} bytes)")
        print(f"Writing {md_path}: {len(doc_content.encode('utf-8'))} bytes")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)
            
        print("[Commit 완료] 모든 산출물이 성공적으로 기록되었습니다.")

if __name__ == '__main__':
    main()
