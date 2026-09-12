import pandas as pd
import polars as pl
from pathlib import Path
import os
import math

def run_crosscheck():
    # 1. Load data
    kapt = pl.read_parquet('data/staged/kapt_basic.parquet').to_pandas()
    # Get confirmed from match candidates
    candidates = pd.read_csv('exports/kapt_match_candidates.csv')
    confirmed_codes = candidates[candidates['human_match_status'] == 'confirmed']['kapt_code'].tolist()
    kapt = kapt[kapt['kapt_code'].isin(confirmed_codes)].copy()
    
    hub_file = Path('data/staged/bldg_title.parquet')
    if hub_file.exists():
        hub = pl.read_parquet(hub_file).to_pandas()
    else:
        hub = pd.DataFrame(columns=['sigunguCd', 'bjdongCd', 'platGbCd', 'bun', 'ji', 'useAprDay', 'hhldCnt'])

    plan = pd.read_csv('bldg_query_plan.csv')
    plan = plan[plan['lookup_status'] == 'SUCCESS']

    # Map kapt_code to query keys (many-to-many due to legacy/new)
    # A single cluster_id can have multiple query_keys (new/legacy variants)
    results = []
    
    for _, k_row in kapt.iterrows():
        code = k_row['kapt_code']
        k_date = k_row['approval_date']
        k_hh = k_row['household_count']
        
        # Find hub rows
        p_rows = plan[plan['cluster_id'] == code]
        hub_rows = pd.DataFrame()
        
        if len(p_rows) > 0 and len(hub) > 0:
            for _, pr in p_rows.iterrows():
                # match on sigunguCd, bjdongCd, platGbCd, bun, ji
                # In hub, they might be stored as string or float depending on polars parsing
                # But our building_hub collector casts them to string. Let's do exact match
                match = hub[
                    (hub['sigunguCd'].astype(str) == str(int(pr['sigunguCd']))) &
                    (hub['bjdongCd'].astype(str) == str(int(pr['bjdongCd'])).zfill(5)) &
                    (hub['platGbCd'].astype(str) == str(int(pr['platGbCd']))) &
                    (hub['bun'].astype(str) == str(pr['bun']).zfill(4)) &
                    (hub['ji'].astype(str) == str(pr['ji']).zfill(4))
                ]
                hub_rows = pd.concat([hub_rows, match])
                
        # Drop duplicates if any (due to legacy/new hitting same building? no, but just in case)
        hub_rows = hub_rows.drop_duplicates(subset=['mgmBldrgstPk'])
        
        h_date = None
        h_hh = None
        
        if len(hub_rows) > 0:
            # hub_first_useAprDay
            valid_dates = pd.to_datetime(hub_rows['useAprDay'], errors='coerce').dropna()
            if len(valid_dates) > 0:
                h_date = valid_dates.min().strftime('%Y-%m-%d')
                
            # hub_total_hhldCnt
            h_hh = hub_rows['hhldCnt'].sum(skipna=True)
            if pd.isna(h_hh):
                h_hh = 0
                
        # Classification
        c_status = 'hub_missing'
        if len(hub_rows) > 0:
            if pd.isna(k_date) and pd.isna(h_date):
                c_status = 'exact_match' # both missing
            elif pd.isna(k_date):
                c_status = 'kapt_missing'
            elif h_date is None:
                c_status = 'hub_missing' # Actually hub date missing
            else:
                kd = pd.to_datetime(k_date)
                hd = pd.to_datetime(h_date)
                diff = abs((kd - hd).days)
                if diff == 0:
                    c_status = 'exact_match'
                elif diff <= 30:
                    c_status = 'within_30_days'
                elif diff <= 180:
                    c_status = 'within_180_days'
                else:
                    c_status = 'conflict'
                    
        # Household count
        pct_diff = None
        flag_5pct = False
        if pd.notna(k_hh) and h_hh is not None and k_hh > 0:
            pct_diff = round(((h_hh - k_hh) / k_hh) * 100, 2)
            if abs(pct_diff) > 5.0:
                flag_5pct = True
                
        results.append({
            'kapt_code': code,
            'complex_name': k_row['kapt_name'],
            'kapt_approval_date': k_date,
            'hub_first_useAprDay': h_date,
            'date_match_status': c_status,
            'kapt_household_count': k_hh,
            'hub_total_hhldCnt': h_hh,
            'hhldCnt_pct_diff': pct_diff,
            'hhldCnt_flag_5pct': flag_5pct,
            'chosen_value': '',
            'chosen_by': ''
        })

    out_df = pd.DataFrame(results)
    os.makedirs('exports', exist_ok=True)
    out_df.to_csv('exports/approval_crosscheck.csv', index=False, encoding='utf-8-sig')

    # Summary
    total = len(out_df)
    stats = out_df['date_match_status'].value_counts().to_dict()
    hh_flags = out_df['hhldCnt_flag_5pct'].sum()
    
    md = f"""# K-apt vs 건축HUB 표제부 대조 리포트

## ⚠️ 데이터 한계 및 주의사항 (Caveats)
* **K-apt (공동주택관리정보시스템)**: 본 데이터는 매주 갱신되는 **단순 참고자료**로, 단지 사정에 따라 사후 수정될 수 있습니다.
* **건축HUB (표제부)**: 건축행정시스템(세움터) 기반의 월간 스냅샷으로, 공부상 확정값을 반영합니다.
* **사용승인일 ≠ 입주일**: 두 시스템의 날짜 모두 '최초 입주일(Occupancy Start Date)'이 아닙니다. 입주 지정기간은 보통 사용승인일 이후에 시작됩니다.
* **불일치는 '오류'가 아닌 '발견'**: 공적 장부 간의 차이는 데이터 품질 검증 과정에서 발견된 현상일 뿐, 특정 데이터가 무조건 틀렸음을 숨겨야 할 오류로 간주하지 않습니다.

## 대조 결과 요약
* **대상 단지**: 총 {total}개 (Confirmed 후보군)

### 1. 사용승인일 (Approval Date) 대조
- `exact_match` (정확히 일치): {stats.get('exact_match', 0)}건
- `within_30_days` (30일 이내 오차): {stats.get('within_30_days', 0)}건
- `within_180_days` (180일 이내 오차): {stats.get('within_180_days', 0)}건
- `conflict` (180일 초과 불일치): {stats.get('conflict', 0)}건
- `hub_missing` (건축HUB 조회 실패 또는 날짜 누락): {stats.get('hub_missing', 0)}건
- `kapt_missing` (K-apt 날짜 누락): {stats.get('kapt_missing', 0)}건

### 2. 세대수 (Household Count) 대조
- **5% 이상 오차 발생 단지**: {hh_flags}건

## 후속 작업 지침 (Human Review)
`exports/approval_crosscheck.csv`에는 `chosen_value`와 `chosen_by` 컬럼이 비어 있습니다. 
두 공적 출처의 값이 다른 경우, 에이전트가 임의로(winner) 선택하지 않았습니다. 반드시 **사람이 확인**하고 어떤 값을 사용할지 근거와 함께 채워 넣어야 합니다.
"""

    os.makedirs('docs', exist_ok=True)
    with open('docs/approval_crosscheck.md', 'w', encoding='utf-8') as f:
        f.write(md)
        
    print("Crosscheck complete.")

if __name__ == "__main__":
    run_crosscheck()
