"""원문 재대조 주석을 계산 로직과 분리해 적용한다. 검수대장 원본은 보존한다."""
import hashlib,json,re
from pathlib import Path
from datetime import date
from scripts.submission.audit import ROOT,read_csv,write_csv
from scripts.submission.review_v02 import OUT,AUDIT,review_bounds
from scripts.submission.inventory_v02 import read_content

def compare_document_date(record,text,digest):
    norm=lambda s:re.sub(r'\s+','',s)
    if digest!=record['sha256'] or norm(record['anchor']) not in norm(text):return None
    lo,hi=date.fromisoformat(record['lower']),date.fromisoformat(record['upper'])
    return (lo,hi) if lo<=hi else None

def run():
    by={r['source_id']:r for r in read_csv(OUT/'source_registry_v02.csv')}
    annotations=read_csv(AUDIT/'document_date_annotations_v02.csv')
    checked={};checks=[]
    for r in annotations:
        p=ROOT/r['path'];text=read_content(p)['text'];bounds=compare_document_date(r,text,hashlib.sha256(p.read_bytes()).hexdigest())
        checks.append(dict(r,anchor_and_hash_match=bool(bounds)))
        if bounds:checked[r['source_id']]=(r,bounds)
    write_csv(OUT/'document_date_checks_v02.csv',checks)
    comparisons=[]
    for gap in read_csv(OUT/'facility_gap_v02.csv'):
        sid=gap['occupancy_source_id'];r,bounds=checked.get(sid,({},None));act=by.get(gap['operation_source_id']);ab=review_bounds(act) if act else None
        comparisons.append({'development':gap['development'],'facility':gap['facility'],'occupancy_source_id':sid,'operation_source_id':gap['operation_source_id'],'reviewer_lower':gap['occupancy_lower'],'reviewer_upper':gap['occupancy_upper'],'document_lower':str(bounds[0]) if bounds else '', 'document_upper':str(bounds[1]) if bounds else '', 'operation_date':str(ab[0]) if ab else '', 'document_gap_min':(ab[0]-bounds[1]).days if bounds and ab else '', 'document_gap_max':(ab[1]-bounds[0]).days if bounds and ab else '', 'status':'document_announced_start_comparison' if bounds and ab else 'withheld','date_conflict':bool(bounds and (str(bounds[0])!=gap['occupancy_lower'] or str(bounds[1])!=gap['occupancy_upper'])),'qualification':r.get('qualification',gap['blockers'])})
    write_csv(OUT/'facility_document_comparison_v02.csv',comparisons)
    forward=[]
    for old in read_csv(ROOT/'data/curated/forward_monitoring.csv'):
        occ=by[old['first_planned_block_source_id']];promise=by[old['promise_source_id']];ob,pb=review_bounds(occ),review_bounds(promise)
        if not pb:relation='target_date_missing'
        elif not ob:relation='occupancy_date_missing'
        elif pb[1]<ob[0]:relation='planned_target_before_planned_occupancy'
        elif pb[0]>ob[1]:relation='planned_target_after_planned_occupancy'
        else:relation='overlapping_or_ambiguous_period'
        forward.append(dict(old,monitoring_status='future_plan_not_observed_outcome',timing_relation=relation,occupancy_review_status=occ['review_status'],promise_review_status=promise['review_status']))
    write_csv(OUT/'forward_monitoring_v02.csv',forward)
    print('원문 날짜 대조',len(checks),'일치',sum(r['anchor_and_hash_match'] for r in checks))

if __name__=='__main__':run()
