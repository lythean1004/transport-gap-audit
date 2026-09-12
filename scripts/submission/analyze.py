"""저장된 자료만으로 제출용 표를 재산출한다. 외부 API를 호출하지 않는다."""
import json
import hashlib
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from scripts.submission.audit import ROOT, OUT, AUDIT, read_csv, write_csv, date_bounds


def analyze():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = read_csv(ROOT/'data/curated/source_registry.csv')
    by_id = {r['source_id']: r for r in registry}
    legacy = read_csv(ROOT/'data/curated/occupancy_operation_gap.csv')
    gaps = []
    for r in legacy:
        occ = by_id[r['occupancy_source_id']]
        act = by_id.get(r['operation_source_id'])
        lo, hi = datetime.fromisoformat(occ['event_date_lower']).date(), datetime.fromisoformat(occ['event_date_upper']).date()
        endpoint = date_bounds(act['event_date']) if act else None
        semantic = 'candidate_requires_human_review'
        if '본격' in occ['exact_excerpt']:
            semantic = 'excluded_first_occupancy_not_established'
        if endpoint is None:
            semantic = 'excluded_operation_absence_not_established'
        gaps.append({'development':r['development'],'facility':r['line_name'],'occupancy_source_id':occ['source_id'],'operation_source_id':act['source_id'] if act else '', 'occupancy_lower':str(lo),'occupancy_upper':str(hi),'operation_date':str(endpoint[0]) if endpoint else '', 'candidate_gap_min':(endpoint[0]-hi).days if endpoint else '', 'candidate_gap_max':(endpoint[1]-lo).days if endpoint else '', 'publication_status':semantic,'occupancy_url':occ['source_url'],'operation_url':act['source_url'] if act else ''})
    write_csv(OUT/'facility_gap_candidates.csv',gaps)
    promises=[]
    for r in read_csv(ROOT/'data/curated/promise_linkage.csv'):
        p=by_id[r['promise_source_id']]; a=by_id.get(r['actual_source_id'])
        pb=date_bounds(p['event_date']); ab=date_bounds(a['event_date']) if a else None
        kind='candidate_same_facility'
        if '준공 예정' in p['exact_excerpt']: kind='excluded_completion_vs_operation'
        if not ab: kind='operation_not_established'
        promises.append({'development':r['development'],'promise_source_id':p['source_id'],'operation_source_id':a['source_id'] if a else '', 'promise_date':p['event_date'],'promise_lower':str(pb[0]) if pb else '', 'promise_upper':str(pb[1]) if pb else '', 'operation_date':str(ab[0]) if ab else '', 'delay_min_days':(ab[0]-pb[1]).days if ab and pb else '', 'delay_max_days':(ab[1]-pb[0]).days if ab and pb else '', 'interpretation':kind,'review_status':'needs_human'})
    write_csv(OUT/'promise_comparison.csv',promises)
    ledger=read_csv(ROOT/'evidence/arrival_ledger.csv')
    grouped=defaultdict(list)
    for r in ledger: grouped[r['obs_date']].append(r)
    daily=[]; raw_rows=[]; problems=[]
    for day, rows in sorted(grouped.items()):
        seen={}; success=[]; routes=set(); item_count=0; empty=0; mismatch=0
        for r in rows:
            if r['outcome'] not in {'ok_empty','ok_with_items'}: continue
            key=(r['slot_hhmm'],r['citycode'],r['nodeid'])
            seen[key]=r
        for r in seen.values():
            p=ROOT/r['raw_path']
            if not p.exists():problems.append({'day':day,'issue':'missing_raw','path':r['raw_path']});continue
            data=json.loads(p.read_text(encoding='utf-8-sig'));response=data['response'];code=str(response['header']['resultCode'])
            items=response['body'].get('items') or {};items=items.get('item',[]) if isinstance(items,dict) else items
            if isinstance(items,dict):items=[items]
            if code!='00':problems.append({'day':day,'issue':'non_00_success','path':r['raw_path']});continue
            if len(items)!=int(r['item_count']):mismatch+=1
            empty+=not bool(items);item_count+=len(items)
            success.append(r)
            for item in items:
                routes.add(str(item['routeid']))
                raw_rows.append({'obs_date':day,'slot_hhmm':r['slot_hhmm'],'called_at_kst':r['called_at_kst'],'nodeid':str(item['nodeid']),'routeid':str(item['routeid']),'arrtime_sec':item['arrtime'],'vehicletp':item['vehicletp']})
        # 120초 규칙은 실제 운행 간격이 아닌 수집시각 근접성의 민감도 검사다.
        ordered=sorted(success,key=lambda x:x['called_at_kst']);near=0
        for a,b in zip(ordered,ordered[1:]):
            if (datetime.fromisoformat(b['called_at_kst'])-datetime.fromisoformat(a['called_at_kst'])).total_seconds()<120:near+=1
        daily.append({'obs_date':day,'planned_slots':48,'ledger_rows':len(rows),'successful_unique_slots':len(success),'missing_slots':48-len(success),'empty_slots':empty,'with_items_slots':len(success)-empty,'api_error_attempts':sum(r['outcome']=='api_error' for r in rows),'near_timestamp_pairs_120s':near,'response_items':item_count,'distinct_routes':len(routes),'item_count_mismatches':mismatch})
    write_csv(OUT/'observation_daily.csv',daily)
    write_csv(OUT/'arrival_items.csv',raw_rows)
    write_csv(OUT/'observation_issues.csv',problems,['day','issue','path'])
    from src.metrics.day123_full_refresh import day1_issues, is_target_active
    qa=[]
    for r in registry:
        if is_target_active(r):
            issues=day1_issues(r)
            qa.append({'source_id':r['source_id'],'required_fields_pass':str(not issues),'issues':';'.join(issues)})
    write_csv(OUT/'evidence_qa_recomputed.csv',qa)
    qa_issues=Counter(i for r in qa for i in r['issues'].split(';') if i)
    write_csv(OUT/'evidence_quality_issues.csv',[{'issue':k,'rows':v} for k,v in qa_issues.most_common()])
    import polars as pl
    profiles={}
    for name in ['kapt_basic','bldg_title','route_service_hours','headway_observed','tago_stops_full','tago_stops_nearby']:
        df=pl.read_parquet(ROOT/f'data/staged/{name}.parquet');profiles[name]={'rows':df.height,'columns':df.width}
    cross=read_csv(ROOT/'exports/approval_crosscheck.csv')
    raw_files=list((ROOT/'evidence/arrival_raw').rglob('*.json'))
    pdfs=read_csv(ROOT/'data/curated/pdf_processing_coverage.csv')
    summary={'registry_rows':len(registry),'active_target_rows':len(qa),'required_fields_pass':sum(r['required_fields_pass']=='True' for r in qa),'human_verified_event_rows':sum(r['review_status']=='human_verified' for r in registry),'review_status':dict(Counter(r['review_status'] for r in registry)),'pdf_files':len(pdfs),'unique_pdf_hashes':len({r['sha256'] for r in pdfs}),'ledger_rows':len(ledger),'raw_json_files':len(raw_files),'parsed_items':len(raw_rows),'distinct_observed_routes':len({r['routeid'] for r in raw_rows}),'observed_stops':len({r['nodeid'] for r in raw_rows}),'period_start':min(grouped),'period_end':max(grouped),'crosscheck_rows':len(cross),'approval_crosscheck':dict(Counter(r['date_match_status'] for r in cross)),'parquet_profiles':profiles,'network_api_calls_this_run':0}
    (OUT/'analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    write_csv(OUT/'analysis_inputs.csv',[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [ROOT/'data/curated/source_registry.csv',ROOT/'evidence/arrival_ledger.csv',*raw_files]])
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':analyze()
