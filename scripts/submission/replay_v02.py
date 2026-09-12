"""발견한 scratch 배차 추정 코드를 읽기 전용으로 재현하고 선택 민감도를 기록."""
import importlib.util, hashlib, json
from scripts.submission.audit import ROOT, write_csv
from scripts.submission.review_v02 import OUT, AUDIT

def run():
    import pandas as pd
    script=ROOT/'scratch/calc_headway_v7.py'
    spec=importlib.util.spec_from_file_location('archived_headway',script)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    ledger,raw,pub,stats=m.load_data()
    cleaned,same,near,dedup=m.process_ledger(ledger)
    routes=sorted(raw.routeid.unique())
    published=set(pub.routeid.astype(str))
    missing_published=sorted(set(routes)-published)
    old=pd.read_parquet(ROOT/'data/staged/headway_observed.parquet')
    historical_dates=sorted(old.obs_date.astype(str).unique())
    all_dates=sorted(ledger.obs_date.astype(str).unique())
    results=[];replayed=None
    for zero in [False,True]:
        ts=m.build_timeseries(cleaned,raw,routes,deduplicated_slots=dedup,zero_fill=zero)
        ev,_=m.detect_events_v2(ts)
        for selection,exclude in [('published_routes',missing_published),('all_observed_routes',[])]:
            metrics=m.aggregate_metrics(ev,ts,routes_to_exclude=exclude)
            for period,dates in [('archived_three_day_selection',historical_dates),('all_observed_days',all_dates)]:
                sub=metrics[metrics.obs_date.isin(dates)].copy()
                gaps=ev[(ev.obs_date.isin(dates))&(~ev.routeid.isin(exclude))].gap_min.dropna()
                results.append({'period':period,'dates':';'.join(dates),'route_selection':selection,'excluded_routes':';'.join(exclude),'empty_response_zero_sensitivity':zero,'groups_with_detected_events':len(sub),'insufficient_groups':int(sub.insufficient_observation.sum()),'event_gap_count':len(gaps),'pooled_proxy_gap_median_minutes':float(gaps.median()) if len(gaps) else None,'pooled_proxy_gap_p25':float(gaps.quantile(.25)) if len(gaps) else None,'pooled_proxy_gap_p75':float(gaps.quantile(.75)) if len(gaps) else None,'meaning':'prediction_reset_proxy_not_vehicle_headway'})
                if not zero and selection=='published_routes' and period=='archived_three_day_selection':
                    replayed=sub.copy();replayed['analysis_window']='본안3일'
                if not zero and period=='all_observed_days' and selection=='all_observed_routes':sub.to_csv(OUT/'prediction_proxy_all_days_v02.csv',index=False,encoding='utf-8-sig')
    keys=['routeid','obs_date','window'];cols=list(old.columns)
    a=old.sort_values(keys).reset_index(drop=True);b=replayed[cols].sort_values(keys).reset_index(drop=True)
    # Parquet의 NaN과 중간 계산의 pd.NA를 같은 결측으로 비교한다.
    for col in cols:
        if col not in keys+['analysis_window','insufficient_observation']:
            a[col]=pd.to_numeric(a[col],errors='raise').astype('Float64')
            b[col]=pd.to_numeric(b[col],errors='raise').astype('Float64')
    try:pd.testing.assert_frame_equal(a,b,check_dtype=False);match=True;error=''
    except AssertionError as e:match=False;error=str(e)[:1000]
    write_csv(OUT/'prediction_proxy_sensitivity_v02.csv',results)
    summary={'generator_path':script.relative_to(ROOT).as_posix(),'generator_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'archived_rows':len(old),'replayed_rows':len(b),'all_columns_equal':match,'difference':error,'missing_published_routes':missing_published,'all_observation_days':all_dates,'api_calls':0,'interpretation':'Reproduction verifies lineage, not validity as actual vehicle headways.'}
    (AUDIT/'headway_lineage_v02.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':run()
