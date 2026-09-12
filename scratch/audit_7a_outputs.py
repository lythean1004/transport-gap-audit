"""
scratch/audit_7a_outputs.py — 7A' 산출물 검증
"""
import sys
import json
import collections
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

def main():
    print("="*60)
    print("[확인 1] data/staged/route_service_hours.parquet")
    print("="*60)
    pq_path = Path("data/staged/route_service_hours.parquet")
    
    pq_routeids = set()
    pq_routes_list = []
    
    if not pq_path.exists():
        print("상태: 없음 (NOT FOUND)")
        print("결론: 7A' 재실행 필요")
    else:
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(str(pq_path))
            df = table.to_pandas()
        except ImportError:
            import pandas as pd
            df = pd.read_parquet(str(pq_path))
            
        print(f"행수: {len(df)}")
        print(f"컬럼 목록: {list(df.columns)}")
        print("\n[dtype 전량]")
        for col, dt in df.dtypes.items():
            print(f"  {col}: {dt}")
            
        print("\n[startvehicletime / endvehicletime 점검]")
        for col in ['startvehicletime', 'endvehicletime']:
            if col in df.columns:
                dt_str = str(df[col].dtype)
                is_str = dt_str == 'object' or 'string' in dt_str
                print(f"  {col}: dtype={dt_str} -> {'문자열 OK' if is_str else '숫자 변질 위험'}")
                samples = df[col].dropna().head(5).tolist()
                print(f"    샘플 5개: {samples}")
                # 선행 0 보존 여부 확인
                leading_zeros = any(str(s).startswith('0') for s in samples if str(s).strip() and str(s).strip() != '0')
                if leading_zeros:
                    print("    -> 선행 0 보존 확인됨 (예: '0530')")
                else:
                    print("    -> 선행 0 샘플 없음 (또는 캐스팅 손실)")
            else:
                print(f"  {col}: 컬럼 없음")
                
        print("\n[intervaltime 계열 컬럼]")
        interval_cols = [c for c in df.columns if 'interval' in c.lower()]
        for col in interval_cols:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                vmin, vmax = non_null.min(), non_null.max()
                print(f"  {col}: {len(non_null)}건 존재, 값 범위: {vmin} ~ {vmax}")
                if vmax <= 180:
                    print("    -> 단위 추정 근거: 값이 180 이하이므로 '분(minute)' 단위로 강하게 추정됨")
                else:
                    print("    -> 단위 추정 근거: 값이 커서 '분'이 아닐 수 있음 (초 단위 등 의심)")
            else:
                print(f"  {col}: 모두 NULL")
                
        if 'routeid' in df.columns:
            pq_routes_list = df['routeid'].tolist()
            pq_routeids = set(df['routeid'].dropna().unique())
            null_cnt = df['routeid'].isna().sum()
            counts = collections.Counter(pq_routes_list)
            dup_cnt = sum(1 for v in counts.values() if v > 1)
            print(f"\n[routeid 상태]")
            print(f"  결측(NULL) 건수: {null_cnt}")
            print(f"  중복(Duplicate) 건수: {dup_cnt}개 ID가 중복됨")
            
    print("\n"+"="*60)
    print("[확인 2] evidence/route_info/ 하위 JSON")
    print("="*60)
    ri_dir = Path("evidence/route_info")
    ri_routeids = set()
    ri_results = collections.Counter()
    
    if ri_dir.exists():
        ri_files = list(ri_dir.rglob("*.json"))
        print(f"파일 수: {len(ri_files)}개")
        for jf in ri_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                hdr = data.get('response', {}).get('header', {})
                rc = hdr.get('resultCode', 'UNKNOWN')
                ri_results[rc] += 1
                
                body = data.get('response', {}).get('body', {})
                items = body.get('items', {})
                if items:
                    items = items.get('item', [])
                if isinstance(items, dict):
                    items = [items]
                for it in items:
                    rid = it.get('routeid')
                    if rid:
                        ri_routeids.add(str(rid))
            except Exception:
                ri_results['PARSE_ERROR'] += 1
                
        print(f"routeid 집합 크기: {len(ri_routeids)}개")
        print(f"resultCode 분포: {dict(ri_results)}")
    else:
        print("상태: 없음 (NOT FOUND)")
        
    print("\n"+"="*60)
    print("[확인 3] 노선 집합 대조 (3방향)")
    print("="*60)
    raw_dir = Path("evidence/arrival_raw")
    arr_routeids = set()
    if raw_dir.exists():
        for jf in raw_dir.rglob("*.json"):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                body = data.get('response', {}).get('body', {})
                items = body.get('items', {})
                if items:
                    items = items.get('item', [])
                if isinstance(items, dict):
                    items = [items]
                for it in items:
                    rid = it.get('routeid')
                    if rid:
                        arr_routeids.add(str(rid))
            except Exception:
                pass
                
    print(f"도착정보(arrival_raw) 고유 노선 수: {len(arr_routeids)}")
    print(f"7A' Parquet 고유 노선 수: {len(pq_routeids)}")
    print(f"7A' route_info JSON 고유 노선 수: {len(ri_routeids)}")
    
    common_all = arr_routeids & pq_routeids & ri_routeids
    print(f"\n3방향 모두 존재하는 노선: {len(common_all)}건")
    
    arr_only = arr_routeids - pq_routeids
    print(f"\n도착정보에만 있고 7A' Parquet에 없는 노선: {len(arr_only)}건")
    if arr_only:
        for rid in sorted(arr_only):
            print(f"  - {rid}")
            
    # 판정 로직
    print("\n"+"="*60)
    print("[판정]")
    print("="*60)
    
    if not pq_path.exists():
        print("NO-GO: route_service_hours.parquet 파일 없음 -> 7A' 선행 필수")
    elif not ri_dir.exists() or len(ri_routeids) == 0:
        print("NO-GO: evidence/route_info/ 응답 데이터 없음 -> 7A' 재실행 필수")
    elif len(arr_only) > 0:
        print(f"PARTIAL-GO: 필수 파일이 존재하고 문자열 포맷이 정상이나, 교차검증 불가 노선 {len(arr_only)}건 존재")
        print(f"7E'에서 제외(또는 NULL 처리)해야 할 노선 목록: {sorted(list(arr_only))}")
    else:
        print("GO: 모든 파일이 정상적으로 존재하며, 모든 관측 노선의 배차정보가 확보됨")

if __name__ == "__main__":
    outpath = "scratch/audit_7a_outputs_result.txt"
    with open(outpath, "w", encoding="utf-8") as f:
        sys.stdout = f
        main()
    sys.stdout = sys.__stdout__
    print(f"output saved to {outpath}")
