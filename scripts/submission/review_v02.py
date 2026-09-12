"""사용자 검수대장을 원문 버전에 결합하는 V02 사건 감사."""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from scripts.submission.audit import ROOT, read_csv, write_csv

OUT=ROOT/'exports/submission_v02'
AUDIT=ROOT/'docs/submission_audit_v02'
# 사건 검증 게이트의 신규 버전. 정류소 G1~G6(v2.3)과 별개다.
GATE_CODE_VERSION='v3.1-resolution-import'
ALIASES={'Dongtan2':'화성 동탄2','Gimpo Hangang':'김포 한강','Wirye':'위례','Namyangju Dasan':'남양주 다산','Hanam Misa':'하남 미사'}


def normalized_development(value):
    return ALIASES.get(value,value).replace(' ','')


def normalized_path(value):
    value=str(value or '').replace('\\','/')
    for marker in ['data/','evidence/']:
        offset=value.find(marker)
        if offset>=0:return value[offset:]
    return value


def match_review(review, sources):
    matches=[s for s in sources if s.get('cand_id','')==review.get('candidate_id','')
             and s.get('sha256')==review.get('sha256')
             and normalized_path(s.get('local_path'))==normalized_path(review.get('local_path'))]
    if len(matches)>1:
        matches=[s for s in matches if normalized_development(s.get('development',''))==normalized_development(review.get('development',''))]
    return matches[0] if len(matches)==1 else None


def apply_review(source, review, review_hash, line):
    row=deepcopy(source)
    row.update(review_input_status=review.get('review_status',''),review_input_sha256=review_hash,
               review_input_row=str(line),review_input_path='evidence/candidate_registry.csv',
               review_import_status='blocked_document_hash',verified_by='',verified_at='',
               verification_provenance='user_supplied_review_registry',gate_code_version=GATE_CODE_VERSION)
    path=ROOT/normalized_path(review.get('local_path',''))
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=review.get('sha256'):
        return row
    for key in ['event_type','event_date','date_precision','review_status']:
        row[key]=review.get(key,'')
    row['reviewed_development']=ALIASES.get(review.get('development',''),review.get('development',''))
    row['development_name_conflict']=str(normalized_development(row.get('development',''))!=normalized_development(row['reviewed_development']))
    # 1대1로 연결하되 지구 의미가 다르면 원문 대조 필요로 남긴다.
    row['event_date_lower']=review.get('date_lower_bound','')
    row['event_date_upper']=review.get('date_upper_bound','')
    row['event_date_normalized']=row['event_date_lower'] if row['event_date_lower']==row['event_date_upper'] else ''
    row['review_import_status']='applied'
    return row


def review_bounds(row):
    try:
        lo=date.fromisoformat(row['event_date_lower']);hi=date.fromisoformat(row['event_date_upper'])
        return (lo,hi) if lo<=hi else None
    except (ValueError,KeyError,TypeError):return None


def merge_resolution(row, final, file_hash):
    result=deepcopy(row)
    status='human_verified' if final.get('review_status')=='verified' else final.get('review_status')
    if row.get('source_id')!=final.get('source_id') or row.get('sha256')!=final.get('sha256') or status!=row.get('review_status'):
        result['resolution_import_status']='blocked_identity_or_status';return result
    # 축약 검수대장의 날짜·사건 유형은 보존하고 최종 대장의 증거·이력 필드를 결합한다.
    protected={'source_id','sha256','local_path','review_status','event_type','event_date','date_precision','event_date_lower','event_date_upper','event_date_normalized'}
    for k,v in final.items():
        if k not in protected:result[k]=v
    result.update(resolution_import_status='applied',resolution_input_path='data/source_registry_verified_final_resolution.csv',resolution_input_sha256=file_hash,resolution_event_type=final.get('event_type',''))
    result['verified_by']=final.get('human_verifier','')
    result['verified_at']=final.get('human_verified_at','')
    result['verification_provenance']='user_supplied_candidate_and_resolution_registries'
    return result


def structural_issues(row):
    from src.metrics.day123_full_refresh import day1_issues
    probe=dict(row)
    if probe.get('event_type')=='occupancy_start':probe['event_type']='occupancy_first_actual'
    issues=day1_issues(probe)
    if row.get('event_type') not in {'plan_confirmation',''} and review_bounds(row) is None:issues.append('missing_or_invalid_date_bounds')
    if row.get('development_name_conflict')=='True':issues.append('development_name_conflict')
    return sorted(set(issues))


def run():
    OUT.mkdir(parents=True,exist_ok=True);AUDIT.mkdir(parents=True,exist_ok=True)
    path=ROOT/'evidence/candidate_registry.csv';reviews=read_csv(path)
    sources=read_csv(ROOT/'data/curated/source_registry.csv')
    review_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    updated={s['source_id']:deepcopy(s) for s in sources};mapping=[];changes=[];used=set()
    for line,review in enumerate(reviews,2):
        source=match_review(review,sources)
        if source is None or source['source_id'] in used:
            mapping.append({'review_row':line,'candidate_id':review['candidate_id'],'source_id':'','status':'unresolved','input_review_status':review['review_status']});continue
        used.add(source['source_id']);row=apply_review(source,review,review_hash,line);updated[source['source_id']]=row
        mapping.append({'review_row':line,'candidate_id':review['candidate_id'],'source_id':source['source_id'],'status':row['review_import_status'],'input_review_status':review['review_status']})
        for key in ['review_status','event_type','event_date','date_precision','event_date_lower','event_date_upper']:
            if source.get(key,'')!=row.get(key,''):changes.append({'source_id':source['source_id'],'field':key,'before':source.get(key,''),'after':row.get(key,''),'review_row':line})
    resolution_path=ROOT/'data/source_registry_verified_final_resolution.csv'
    resolution_hash=hashlib.sha256(resolution_path.read_bytes()).hexdigest()
    resolution={r['source_id']:r for r in read_csv(resolution_path)}
    for sid,row in updated.items():
        if sid not in resolution:continue
        merged=merge_resolution(row,resolution[sid],resolution_hash)
        for key in resolution[sid]:
            if row.get(key,'')!=merged.get(key,''):
                changes.append({'source_id':sid,'field':key,'before':row.get(key,''),'after':merged.get(key,''),'review_row':'resolution:'+str(list(resolution).index(sid)+2)})
        updated[sid]=merged
    rows=list(updated.values());fields=list(dict.fromkeys(k for row in rows for k in row))
    rows=[{k:row.get(k,'') for k in fields} for row in rows]
    qa=[]
    for row in rows:
        issues=structural_issues(row)
        qa.append({'source_id':row['source_id'],'review_status':row['review_status'],'event_type':row['event_type'],
                   'structural_pass':not issues,'issues':';'.join(issues),'review_import_status':row['review_import_status']})
    write_csv(OUT/'source_registry_v02.csv',rows,fields)
    write_csv(AUDIT/'review_mapping_v02.csv',mapping)
    write_csv(AUDIT/'review_changes_v02.csv',changes)
    write_csv(OUT/'evidence_qa_v02.csv',qa)
    qa_by={r['source_id']:r for r in qa}
    queue=[]
    for row in rows:
        q=qa_by[row['source_id']]
        if row['review_status']=='human_verified' and not q['structural_pass']:
            action='supplement_evidence_fields_keep_human_review'
        elif row['review_status']=='needs_human':action='human_review_pending'
        elif row['review_status']=='duplicate':action='excluded_duplicate_target_not_recorded'
        elif row['review_status']=='rejected':action='excluded_by_user_review'
        else:continue
        queue.append({'source_id':row['source_id'],'candidate_id':row['cand_id'],'review_status':row['review_status'],'action':action,'issues':q['issues'],'review_input_row':row['review_input_row'],'page_or_section':row['page_or_section'],'source_url':row['source_url'],'local_path':row['local_path']})
    write_csv(OUT/'review_queue_v02.csv',queue)
    by={r['source_id']:r for r in rows};gaps=[];gate=[];promises=[]
    for old in read_csv(ROOT/'data/curated/occupancy_operation_gap.csv'):
        occ=by[old['occupancy_source_id']];act=by.get(old['operation_source_id']);ob=review_bounds(occ);ab=review_bounds(act) if act else None
        reasons=[]
        if occ['review_status']!='human_verified' or not act or act['review_status']!='human_verified':reasons.append('pair_not_both_human_verified')
        if not ob or not ab:reasons.append('date_bound_missing')
        if '본격' in occ['exact_excerpt'] or occ.get('contradiction_flag')=='TRUE':reasons.append('first_occupancy_not_established')
        if act and act['event_type']!='actual_operation':reasons.append('operation_type_changed')
        gaps.append({'development':old['development'],'facility':old['line_name'],'occupancy_source_id':occ['source_id'],'operation_source_id':act['source_id'] if act else '',
                     'occupancy_lower':str(ob[0]) if ob else '', 'occupancy_upper':str(ob[1]) if ob else '', 'operation_date':str(ab[0]) if ab else '',
                     'gap_days_min':(ab[0]-ob[1]).days if ab and ob else '', 'gap_days_max':(ab[1]-ob[0]).days if ab and ob else '',
                     'comparison_status':'reviewed_date_comparison' if not reasons else 'withheld', 'blockers':';'.join(reasons),
                     'occupancy_review_status':occ['review_status'],'operation_review_status':act['review_status'] if act else '',
                     'source_field_issues':qa_by[occ['source_id']]['issues']+';'+(qa_by[act['source_id']]['issues'] if act else ''),
                     'interpretation':'reviewed_occupancy_start_to_selected_facility_not_total_service_absence'})
    for old in read_csv(ROOT/'data/curated/promise_linkage.csv'):
        pr=by[old['promise_source_id']];act=by.get(old['actual_source_id']);pb=review_bounds(pr);ab=review_bounds(act) if act else None
        reasons=[]
        if pr['review_status']!='human_verified' or not act or act['review_status']!='human_verified':reasons.append('pair_not_both_human_verified')
        if pr['event_type']!='promise_date':reasons.append('not_operation_promise_event')
        if not ab or not pb:reasons.append('date_bound_missing')
        if '준공 예정' in pr['exact_excerpt']:reasons.append('completion_not_operation')
        if act and (pr['mode']!=act['mode'] or pr['line_name']!=act['line_name']):reasons.append('mode_or_line_mismatch')
        promises.append({'development':old['development'],'promise_source_id':pr['source_id'],'operation_source_id':act['source_id'] if act else '',
                         'promise_date':pr['event_date'],'reviewed_event_type':pr['event_type'],'promise_review_status':pr['review_status'],
                         'operation_date':str(ab[0]) if ab else '', 'delay_min_days':(ab[0]-pb[1]).days if ab and pb else '',
                         'delay_max_days':(ab[1]-pb[0]).days if ab and pb else '', 'comparison_status':'reviewed_date_comparison' if not reasons else 'withheld','blockers':';'.join(reasons)})
    # 검수 완료 사실과 엄격한 지표 준비 여부를 분리해 계산한다. 고정 FAIL을 사용하지 않는다.
    for gap in gaps:
        dev=gap['development'];promise=next(p for p in promises if p['development']==dev)
        rr=[r for r in rows if r['development']==dev and r['review_status']=='human_verified']
        types={r['event_type'] for r in rr};triple={'occupancy_start','promise_date','actual_operation'}.issubset(types)
        ids=[gap['occupancy_source_id'],gap['operation_source_id'],promise['promise_source_id']]
        issues=sorted(set(i for sid in ids if sid for i in qa_by[sid]['issues'].split(';') if i))
        reasons=[]
        if not triple:reasons.append('verified_event_types_incomplete')
        if gap['comparison_status']!='reviewed_date_comparison':reasons.append('occupancy_operation_comparison_withheld')
        if promise['comparison_status']!='reviewed_date_comparison':reasons.append('promise_comparison_withheld')
        if issues:reasons.append('selected_source_fields_incomplete')
        gate.append({'development':dev,'human_verified_source_rows':len(rr),'has_verified_event_types':triple,
                     'gate_result':'PASS' if not reasons else 'NEEDS_EVIDENCE','blockers':';'.join(reasons),'source_field_issues':';'.join(issues),'GATE_CODE_VERSION':GATE_CODE_VERSION})
    write_csv(OUT/'facility_gap_v02.csv',gaps);write_csv(OUT/'promise_comparison_v02.csv',promises);write_csv(OUT/'evidence_gate_v02.csv',gate)
    human=[r for r in rows if r['review_status']=='human_verified'];hq=[q for q in qa if q['review_status']=='human_verified']
    summary={'version':'V02','review_registry_sha256':review_hash,'review_input_rows':len(reviews),'matched_rows':len(used),
             'applied_rows':sum(m['status']=='applied' for m in mapping),'review_status_counts':dict(Counter(r['review_status'] for r in rows)),
             'human_verified_unique_document_hashes':len({r['sha256'] for r in human}),
             'human_verified_structural_pass':sum(q['structural_pass'] for q in hq),'human_verified_structural_issues':sum(not q['structural_pass'] for q in hq),
             'all_structural_pass':sum(q['structural_pass'] for q in qa),'changes_by_field':dict(Counter(c['field'] for c in changes)),
             'human_event_types':dict(Counter(r['event_type'] for r in human)),
             'event_types_all':dict(Counter(r['event_type'] for r in rows)), 'gate_version':GATE_CODE_VERSION,
             'gate_results':dict(Counter(g['gate_result'] for g in gate)), 'human_review_timestamp_provided':sum(bool(r.get('verified_at')) for r in human),
             'resolution_registry_sha256':resolution_hash,'resolution_applied_rows':sum(r.get('resolution_import_status')=='applied' for r in rows),
             'imported_at':datetime.now(timezone.utc).isoformat(),'api_calls':0}
    (OUT/'review_summary_v02.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':run()
