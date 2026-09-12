"""선행조건 검사 스크립트 — 읽기 전용, 생성·호출 금지"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path.cwd()))

def main():
    # ── [필수1] route_service_hours.parquet ──
    print("=" * 60)
    print("[필수1] data/staged/route_service_hours.parquet")
    print("=" * 60)
    pq_path = Path("data/staged/route_service_hours.parquet")
    if not pq_path.exists():
        print("상태: NOT FOUND")
    else:
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(str(pq_path))
            df = table.to_pandas()
        except ImportError:
            import pandas as pd
            df = pd.read_parquet(str(pq_path))

        print(f"행수: {len(df)}")
        print(f"실제 컬럼 ({len(df.columns)}개): {list(df.columns)}")

        expected = [
            'citycode', 'routeid', 'routeno', 'routetp',
            'startnodenm', 'endnodenm',
            'startvehicletime', 'endvehicletime',
            'intervaltime', 'intervalsattime', 'intervalsuntime',
            'fetched_at_kst', 'fetched_at_utc', 'raw_path',
        ]
        missing = [c for c in expected if c not in df.columns]
        extra = [c for c in df.columns if c not in expected]
        print(f"기대 컬럼 누락: {missing if missing else '없음'}")
        print(f"추가 컬럼: {extra if extra else '없음'}")

        # dtype 검사 — startvehicletime / endvehicletime
        for col in ['startvehicletime', 'endvehicletime']:
            if col in df.columns:
                dt = str(df[col].dtype)
                is_str = dt == 'object' or 'str' in dt
                null_pct = df[col].isna().mean() * 100
                print(f"\n  {col}:")
                print(f"    dtype = {dt}  →  {'문자열 OK' if is_str else '*** 치명 결함: 정수형 ***'}")
                print(f"    비어있음 = {df[col].isna().sum()}건 ({null_pct:.1f}%)")
                # 샘플
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    samples = non_null.head(5).tolist()
                    print(f"    샘플값: {samples}")
                    # 값 유형 세부 확인
                    types_found = set(type(v).__name__ for v in non_null.tolist())
                    print(f"    값 Python 타입: {types_found}")

        # intervaltime 분석
        if 'intervaltime' in df.columns:
            it = df['intervaltime']
            null_pct = it.isna().mean() * 100
            print(f"\n  intervaltime:")
            print(f"    dtype = {it.dtype}")
            print(f"    비어있음 = {it.isna().sum()}건 ({null_pct:.1f}%)")
            non_null = it.dropna()
            if len(non_null) > 0:
                print(f"    값 분포:")
                vc = non_null.value_counts().head(10)
                for v, c in vc.items():
                    print(f"      {v}: {c}건")

        # intervalsattime / intervalsuntime
        for col in ['intervalsattime', 'intervalsuntime']:
            if col in df.columns:
                null_pct = df[col].isna().mean() * 100
                print(f"\n  {col}: dtype={df[col].dtype}, 비어있음={df[col].isna().sum()}건 ({null_pct:.1f}%)")

        # 차량 식별자 컬럼 확인
        vehicle_cols = [c for c in df.columns if any(kw in c.lower() for kw in
                        ['vehicle', 'veh', 'bus', 'plate', 'carno', 'car_no'])]
        if vehicle_cols:
            print(f"\n  차량 식별자 성격 컬럼: {vehicle_cols}")
        else:
            print(f"\n  차량 식별자 성격 컬럼: 없음 (AGENTS.md 기재와 일치: '차량 식별자 필드 없음')")

        # routeid 집합
        pq_routeids = set(df['routeid'].dropna().unique()) if 'routeid' in df.columns else set()
        print(f"\n  고유 routeid 수: {len(pq_routeids)}")

    # ── [필수2] evidence/route_info/ ──
    print("\n" + "=" * 60)
    print("[필수2] evidence/route_info/")
    print("=" * 60)
    ri_dir = Path("evidence/route_info")
    if not ri_dir.exists():
        print("상태: NOT FOUND")
        ri_routeids = set()
    else:
        ri_files = sorted(ri_dir.glob("*.json"))
        print(f"JSON 파일 수: {len(ri_files)}")
        ri_routeids = set()
        for jf in ri_files:
            print(f"  {jf.name}")
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                body = data.get('response', {}).get('body', {})
                items = body.get('items', {})
                if items:
                    items = items.get('item', [])
                if isinstance(items, dict):
                    items = [items]
                if isinstance(items, list):
                    for it in items:
                        rid = it.get('routeid')
                        if rid:
                            ri_routeids.add(str(rid))
            except Exception as e:
                print(f"    파싱 오류: {e}")
        print(f"route_info JSON에서 추출된 고유 routeid 수: {len(ri_routeids)}")
        if ri_routeids:
            for rid in sorted(ri_routeids):
                print(f"    {rid}")

    # ── [대조] 관측 원장 raw JSON에서 distinct (routeid, routeno) ──
    print("\n" + "=" * 60)
    print("[대조] 관측 raw JSON → distinct (routeid, routeno)")
    print("=" * 60)
    raw_dir = Path("evidence/arrival_raw")
    obs_routes = set()   # (routeid, routeno)
    obs_routeids = set()
    file_count = 0
    parse_errors = 0

    if raw_dir.exists():
        raw_files = list(raw_dir.rglob("*.json"))
        file_count = len(raw_files)
        for rf in raw_files:
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                body = data.get('response', {}).get('body', {})
                items = body.get('items', {})
                if items:
                    items = items.get('item', [])
                if isinstance(items, dict):
                    items = [items]
                if isinstance(items, list):
                    for it in items:
                        rid = it.get('routeid')
                        rno = it.get('routeno')
                        if rid:
                            obs_routes.add((str(rid), str(rno) if rno else ''))
                            obs_routeids.add(str(rid))
            except Exception:
                parse_errors += 1
    else:
        print("evidence/arrival_raw NOT FOUND")

    print(f"파싱한 raw JSON: {file_count}개 (오류 {parse_errors}건)")
    print(f"관측된 distinct (routeid, routeno): {len(obs_routes)}쌍")
    print(f"관측된 distinct routeid: {len(obs_routeids)}개")

    if obs_routes:
        print("\n관측 노선 전체 목록:")
        for rid, rno in sorted(obs_routes):
            print(f"  routeid={rid}, routeno={rno}")

    # 집합 대조
    if pq_path.exists():
        both = obs_routeids & pq_routeids
        obs_only = obs_routeids - pq_routeids
        pq_only = pq_routeids - obs_routeids
        print(f"\n[집합 대조 결과]")
        print(f"  양쪽 모두 존재: {len(both)}건")
        print(f"  관측에만 존재 (배차 교차검증 불가): {len(obs_only)}건")
        if obs_only:
            for rid in sorted(obs_only):
                rno_list = [rno for r, rno in obs_routes if r == rid]
                print(f"    routeid={rid} (routeno={','.join(rno_list)})")
        print(f"  parquet에만 존재 (관측 미등장): {len(pq_only)}건")
        if pq_only:
            for rid in sorted(pq_only):
                print(f"    routeid={rid}")
    else:
        print("[집합 대조] route_service_hours.parquet 부재로 대조 불가")

    # ── [참고1] docs/tago_route_api_findings.md ──
    print("\n" + "=" * 60)
    print("[참고1] docs/tago_route_api_findings.md")
    print("=" * 60)
    findings_path = Path("docs/tago_route_api_findings.md")
    if findings_path.exists():
        print(f"존재: YES ({findings_path.stat().st_size} bytes)")
        with open(findings_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        headings = [l.strip() for l in lines if l.strip().startswith('#')]
        print("목차:")
        for h in headings:
            print(f"  {h}")
    else:
        print("상태: NOT FOUND")

    # ── [참고2] data/staged/tago_arrival.parquet ──
    print("\n" + "=" * 60)
    print("[참고2] data/staged/tago_arrival.parquet")
    print("=" * 60)
    arr_pq = Path("data/staged/tago_arrival.parquet")
    if arr_pq.exists():
        print(f"존재: YES ({arr_pq.stat().st_size} bytes)")
    else:
        print("상태: NOT FOUND")
        print("→ 7E′ 입력으로 원장 CSV + raw JSON에서 대체 구성이 필요함")

    # ── 판정 ──
    print("\n" + "=" * 60)
    print("[판정]")
    print("=" * 60)

    if not pq_path.exists():
        print(f"NO-GO: 필수1 부재 → 7A′ 선행 필요")
        print(f"  관측 distinct routeid 수: {len(obs_routeids)}")
        print(f"  필요한 호출 수: ({len(obs_routeids)}, 상한 20) = {min(len(obs_routeids), 20)}")
    else:
        # startvehicletime dtype 확인
        import pandas as pd
        df = pd.read_parquet(str(pq_path))
        svt_dtype = str(df['startvehicletime'].dtype) if 'startvehicletime' in df.columns else 'N/A'
        is_str = svt_dtype == 'object' or 'str' in svt_dtype
        coverage = len(both) / len(obs_routeids) * 100 if obs_routeids else 0

        if not is_str:
            print(f"NO-GO: startvehicletime dtype={svt_dtype} (정수형 치명 결함)")
        elif coverage >= 80:
            print(f"GO: 필수1·2 존재, startvehicletime 문자열, "
                  f"관측 노선 커버율 {len(both)}/{len(obs_routeids)}={coverage:.0f}%")
        else:
            print(f"부분 GO: 필수1 존재하나 커버율 {coverage:.0f}%")
            if obs_only:
                print(f"  교차검증 불가 노선 {len(obs_only)}건")


if __name__ == "__main__":
    outpath = "scratch/prereq_check_output.txt"
    with open(outpath, "w", encoding="utf-8") as f:
        sys.stdout = f
        main()
    sys.stdout = sys.__stdout__
    print("output saved to " + outpath)
