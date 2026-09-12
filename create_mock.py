import polars as pl
import pandas as pd
import os

df_kapt = pl.read_parquet('data/staged/kapt_basic.parquet')
plan = pd.read_csv('bldg_query_plan.csv')
plan = plan[plan['lookup_status'] == 'SUCCESS'].head(5)

rows = []
for idx, p in plan.iterrows():
    kapt_row = df_kapt.filter(pl.col('kapt_code') == p['cluster_id'])
    if len(kapt_row) == 0: continue
    
    # exact match for 3 rows, diff for 2 rows to test classification
    modifier = 0
    if idx == 0:
        modifier = 15 # within 30 days
    elif idx == 1:
        modifier = 100 # within 180 days
    elif idx == 2:
        modifier = 200 # conflict
        
    date_val = None
    if kapt_row['approval_date'][0]:
        base_date = pd.to_datetime(kapt_row['approval_date'][0])
        hub_date = base_date + pd.Timedelta(days=modifier)
        date_val = hub_date.strftime('%Y-%m-%d')
        date_raw = hub_date.strftime('%Y%m%d')
    else:
        date_val = None
        date_raw = None
        
    hc = kapt_row['household_count'][0]
    if hc is None: hc = 100
    
    rows.append({
        'mgmBldrgstPk': f'MOCK_{p["query_key"]}_1',
        'mgmUpBldrgstPk': 'UP',
        'sigunguCd': str(p['sigunguCd']),
        'bjdongCd': str(p['bjdongCd']),
        'platGbCd': str(p['platGbCd']),
        'bun': str(p['bun']),
        'ji': str(p['ji']),
        'platPlc': p['addr_legal'],
        'newPlatPlc': '도로명',
        'bldNm': p['complex_name'],
        'dongNm': '101동',
        'mainPurpsCdNm': '공동주택',
        'regstrKindCd': '표제부',
        'hhldCnt': int(hc // 2),
        'fmlyCnt': 0,
        'pmsDay': '20100101',
        'stcnsDay': '20100201',
        'useAprDay_raw': date_raw,
        'useAprDay': date_val,
        'crtnDay': '20200101'
    })
    
    rows.append({
        'mgmBldrgstPk': f'MOCK_{p["query_key"]}_2',
        'mgmUpBldrgstPk': 'UP',
        'sigunguCd': str(p['sigunguCd']),
        'bjdongCd': str(p['bjdongCd']),
        'platGbCd': str(p['platGbCd']),
        'bun': str(p['bun']),
        'ji': str(p['ji']),
        'platPlc': p['addr_legal'],
        'newPlatPlc': '도로명',
        'bldNm': p['complex_name'],
        'dongNm': '102동',
        'mainPurpsCdNm': '공동주택',
        'regstrKindCd': '표제부',
        'hhldCnt': int(hc - (hc // 2)),
        'fmlyCnt': 0,
        'pmsDay': '20100101',
        'stcnsDay': '20100201',
        'useAprDay_raw': date_raw,
        'useAprDay': date_val,
        'crtnDay': '20200101'
    })

schema = {
        'mgmBldrgstPk': pl.Utf8, 'mgmUpBldrgstPk': pl.Utf8, 'sigunguCd': pl.Utf8,
        'bjdongCd': pl.Utf8, 'platGbCd': pl.Utf8, 'bun': pl.Utf8, 'ji': pl.Utf8,
        'platPlc': pl.Utf8, 'newPlatPlc': pl.Utf8, 'bldNm': pl.Utf8, 'dongNm': pl.Utf8,
        'mainPurpsCdNm': pl.Utf8, 'regstrKindCd': pl.Utf8, 'hhldCnt': pl.Int64,
        'fmlyCnt': pl.Int64, 'pmsDay': pl.Utf8, 'stcnsDay': pl.Utf8,
        'useAprDay_raw': pl.Utf8, 'useAprDay': pl.Utf8, 'crtnDay': pl.Utf8
}
df = pl.DataFrame(rows, schema=schema)
# 모의자료는 제출 분석 및 실제 가공자료와 분리해 보관한다.
os.makedirs('qa/submission_v1', exist_ok=True)
df.write_parquet('qa/submission_v1/mock_bldg_title.parquet')
print('Created QA-only mock_bldg_title.parquet')
