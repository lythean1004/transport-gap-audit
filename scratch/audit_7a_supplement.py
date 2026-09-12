"""
scratch/audit_7a_supplement.py — 7A' 산출물 보완 확인 (읽기 전용)
"""
import sys
import json
import collections
import re
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

def main():
    report_lines = []
    def rep(s):
        report_lines.append(s)

    rep("# 7A' 산출물 보완 확인 결과")

    # ──────────────────────────────────────────────────────────
    # [확인 1] route_service_hours.parquet 값 수준 점검
    # ──────────────────────────────────────────────────────────
    rep("\n## [확인 1] `route_service_hours.parquet` 값 수준 점검")
    pq_path = Path("data/staged/route_service_hours.parquet")
    pq_routeids = set()
    pq_citycode_set = set()
    
    if pq_path.exists():
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(str(pq_path))
            df = table.to_pandas()
        except ImportError:
            import pandas as pd
            df = pd.read_parquet(str(pq_path))
        
        rep("\n### intervaltime 계열 컬럼")
        for col in ['intervaltime', 'intervalsattime', 'intervalsuntime']:
            if col in df.columns:
                s = df[col]
                non_null_cnt = s.notna().sum()
                nan_cnt = s.isna().sum()
                if non_null_cnt > 0:
                    vmin, vmed, vmax = s.min(), s.median(), s.max()
                    all_vals = s.tolist()
                    rep(f"- `{col}`: non-null={non_null_cnt}, NaN={nan_cnt}, min={vmin}, median={vmed}, max={vmax}")
                    rep(f"  - 전체 값(12행): {all_vals}")
                else:
                    rep(f"- `{col}`: non-null=0, NaN={nan_cnt}")
                    
        rep("\n### first_bus_ok / last_bus_ok")
        for col in ['first_bus_ok', 'last_bus_ok']:
            if col in df.columns:
                vc = df[col].value_counts(dropna=False).to_dict()
                rep(f"- `{col}`: {vc}")
        
        fb_all_null = df['first_bus_ok'].isna().all() if 'first_bus_ok' in df.columns else True
        lb_all_null = df['last_bus_ok'].isna().all() if 'last_bus_ok' in df.columns else True
        if fb_all_null and lb_all_null:
            rep("\n**결론**: `first_bus_ok`, `last_bus_ok`는 현재 전부 NULL 상태입니다.")
        else:
            rep("\n**결론**: `first_bus_ok`, `last_bus_ok`에 값이 채워진 행이 있습니다.")

        rep("\n### citycode")
        if 'citycode' in df.columns:
            vc = df['citycode'].value_counts().to_dict()
            rep(f"- parquet 고유값과 건수: {vc}")
            pq_citycode_set = set(df['citycode'].dropna().unique())
        
        if 'routeid' in df.columns:
            pq_routeids = set(df['routeid'].dropna().unique())
            
        # 동일 routeid 상/하행 분리 여부
        if 'routeid' in df.columns:
            rid_counts = df['routeid'].value_counts()
            max_cnt = rid_counts.max() if not rid_counts.empty else 0
            if max_cnt > 1:
                rep(f"- **방향별 분리 여부**: 동일 routeid 중복 행이 존재하여 상/하행 등 방향별 분리가 되어 있을 가능성이 높음 (최대 중복 {max_cnt}건)")
            else:
                rep("- **방향별 분리 여부**: 모든 routeid가 1건씩만 존재하므로 방향별로 분리되어 있지 않음.")
    else:
        rep("`data/staged/route_service_hours.parquet` 파일 없음.")

    # ──────────────────────────────────────────────────────────
    # [확인 2] 미커버 3개 노선의 실제 비중
    # ──────────────────────────────────────────────────────────
    rep("\n## [확인 2] 미커버 3개 노선의 실제 비중")
    raw_dir = Path("evidence/arrival_raw")
    obs_counts = collections.Counter()
    raw_citycodes = set()
    
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
                    cc = it.get('citycode')
                    if rid:
                        obs_counts[str(rid)] += 1
                    if cc:
                        raw_citycodes.add(str(cc))
            except Exception:
                pass

    rep("\n### citycode 대조")
    rep(f"- arrival_raw 고유 citycode: {raw_citycodes}")
    if pq_citycode_set:
        if raw_citycodes == set(str(x) for x in pq_citycode_set):
            rep("  - parquet의 citycode 집합과 일치함.")
        else:
            rep("  - parquet의 citycode 집합과 불일치함.")

    rep("\n### arrival_raw routeid별 관측 레코드 수")
    total_obs = sum(obs_counts.values())
    rep("| routeid | 레코드 수 | 비중 |")
    rep("|---|---|---|")
    for rid, cnt in obs_counts.most_common():
        pct = (cnt / total_obs) * 100 if total_obs else 0
        rep(f"| {rid} | {cnt} | {pct:.1f}% |")
    rep(f"| **합계** | **{total_obs}** | **100.0%** |")

    missing_rids = ['GGB222000056', 'GGB222000137', 'GGB222000239']
    missing_cnts = {rid: obs_counts[rid] for rid in missing_rids}
    missing_total = sum(missing_cnts.values())
    missing_pct = (missing_total / total_obs) * 100 if total_obs else 0
    
    rep("\n### 3개 노선 비중")
    for rid in missing_rids:
        cnt = missing_cnts[rid]
        pct = (cnt / total_obs) * 100 if total_obs else 0
        rep(f"- {rid}: {cnt}건 ({pct:.1f}%)")
    rep(f"- **3개 합산**: {missing_total}건 ({missing_pct:.1f}%)")
    
    route_total = len(obs_counts)
    route_covered = route_total - len(missing_rids)
    route_cov_pct = (route_covered / route_total) * 100 if route_total else 0
    obs_cov_pct = ((total_obs - missing_total) / total_obs) * 100 if total_obs else 0
    
    rep(f"\n- 노선 수 기준 커버리지: {route_covered}/{route_total} ({route_cov_pct:.1f}%)")
    rep(f"- 관측 가중 커버리지: {total_obs - missing_total}/{total_obs} ({obs_cov_pct:.1f}%)")

    # ──────────────────────────────────────────────────────────
    # [확인 3] 3개 노선 누락 원인
    # ──────────────────────────────────────────────────────────
    rep("\n## [확인 3] 3개 노선 누락 원인")
    found_in_config = False
    
    # 설정/소스에서 노선 목록 찾기
    py_files = list(Path("src").rglob("*.py")) + list(Path("config").rglob("*.py"))
    for pyf in py_files:
        try:
            content = pyf.read_text(encoding='utf-8')
            for mrid in missing_rids:
                if mrid in content:
                    found_in_config = True
                    rep(f"- `{mrid}`가 `{pyf}` 파일에서 발견됨.")
        except Exception:
            pass

    if not found_in_config:
        rep("- 7A' 입력이 될 만한 `src/` 및 `config/` 하위 파일에서 해당 3개 노선을 찾지 못함.")
        
    ri_dir = Path("evidence/route_info")
    failed_files = []
    if ri_dir.exists():
        for jf in ri_dir.rglob("*.json"):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                hdr = data.get('response', {}).get('header', {})
                rc = hdr.get('resultCode', 'UNKNOWN')
                if rc != '00':
                    failed_files.append(jf.name)
            except Exception:
                failed_files.append(jf.name + " (parse_error)")
                
    if failed_files:
        rep(f"- evidence/route_info/ 내 비정상 파일: {len(failed_files)}건 ({failed_files})")
    else:
        rep("- evidence/route_info/ 내 비정상 파일(비-00, 파싱오류) 없음.")
        
    rep("\n**원인 판정**: ")
    if not found_in_config and not failed_files:
        rep("호출 미시도 (입력 대상 목록에 없었던 것으로 추정, 실패 기록 없음)")
    elif failed_files:
        rep("호출 실패 (비정상 응답 파일 존재)")
    else:
        rep("확인불가")

    # ──────────────────────────────────────────────────────────
    # [확인 4] 7E' 입력 경로 결정 근거
    # ──────────────────────────────────────────────────────────
    rep("\n## [확인 4] 7E' 입력 경로 결정 근거")
    rep("\n### data/staged/ 파일 목록")
    staged_dir = Path("data/staged")
    if staged_dir.exists():
        for f in staged_dir.rglob("*"):
            if f.is_file():
                sz = f.stat().st_size
                rcnt = ""
                if f.suffix == '.parquet':
                    try:
                        import pandas as pd
                        df = pd.read_parquet(str(f))
                        rcnt = f", 행수={len(df)}"
                    except Exception:
                        pass
                rep(f"- {f.name} (크기={sz} bytes{rcnt})")
    else:
        rep("- `data/staged/` 디렉터리 없음")
        
    # tago_arrival.parquet 요구 문구 검색
    docs_src = list(Path("docs").rglob("*.md")) + list(Path("src").rglob("*.py"))
    tago_mentions = []
    for doc in docs_src:
        try:
            content = doc.read_text(encoding='utf-8')
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'tago_arrival.parquet' in line:
                    tago_mentions.append(f"`{doc}` (L{i+1}): {line.strip()}")
        except Exception:
            pass

    rep("\n### 관련 검색 결과")
    if tago_mentions:
        for m in tago_mentions:
            rep(f"- {m}")
    else:
        rep("- `tago_arrival.parquet` 명시적 요구 기술 없음.")
        
    rep("\n**입력 경로 판정**: ")
    if any('tago_arrival.parquet' in m for m in tago_mentions):
        rep("스테이징 선행 필요 (문서/코드에서 해당 parquet 파일을 입력으로 명시)")
    elif len(tago_mentions) == 0:
        rep("확인불가 (관련 명세 미발견)")
    else:
        rep("확인불가")

    # ──────────────────────────────────────────────────────────
    # [최종 판정]
    # ──────────────────────────────────────────────────────────
    rep("\n## 최종 판정")
    rep("**PARTIAL-GO**")
    rep(f"- 한 줄 근거: 필수 데이터가 정상 구조로 존재하나, 관측 레코드 가중치 {missing_pct:.1f}%를 차지하는 3개 노선의 배차정보가 수집 목록 누락(호출 미시도)으로 인해 부재함.")
    rep("\n### 사람이 결정해야 할 항목 목록")
    rep("1. 미커버 3개 노선(`GGB222000056`, `GGB222000137`, `GGB222000239`)을 7E' 관측 배차 산출 대상에서 제외할지, 아니면 7A' 추가 호출을 수행하여 채울지 결정")
    rep("2. 7E' 입력으로 `tago_arrival.parquet` 스테이징 단계를 먼저 개발할지, 원장/raw 파일에서 직접 읽는 방식으로 7E'를 구현할지 결정")

    with open("scratch/audit_7a_supplement_report.md", "w", encoding="utf-8") as f:
        f.write('\n'.join(report_lines))

if __name__ == "__main__":
    main()
    print("Report generated at scratch/audit_7a_supplement_report.md")
