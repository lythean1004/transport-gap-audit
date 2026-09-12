"""저장 원자료에서 V02 표·검수 결합·배차 계보를 재현한다. 외부 호출 없음."""
import json,shutil,hashlib
from scripts.submission.audit import ROOT,read_csv,write_csv
from scripts.submission.review_v02 import OUT,run as review
from scripts.submission.claims_v02 import run as claims
from scripts.submission.replay_v02 import run as replay
from scripts.submission.windows_v02 import run as windows

def run():
    import scripts.submission.analyze as legacy
    legacy.OUT=ROOT/'qa/submission_v02/recomputed_v01_schema'
    legacy.analyze()
    review();claims();replay();windows()
    for name in ['observation_daily.csv','arrival_items.csv','observation_issues.csv','analysis_inputs.csv']:
        shutil.copyfile(legacy.OUT/name,OUT/name)
    s=json.loads((legacy.OUT/'analysis_summary.json').read_text(encoding='utf-8'))
    r=json.loads((OUT/'review_summary_v02.json').read_text(encoding='utf-8'))
    for key in ['active_target_rows','required_fields_pass','human_verified_event_rows','review_status']:s.pop(key,None)
    s.update(human_verified_event_rows=r['review_status_counts']['human_verified'],review_status=r['review_status_counts'],review_summary=r,version='V02')
    (OUT/'analysis_summary_v02.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
    inputs={r['path'] for r in read_csv(OUT/'analysis_inputs.csv')}
    inputs.update(['evidence/candidate_registry.csv','data/source_registry_verified_final_resolution.csv','docs/submission_audit_v02/document_date_annotations_v02.csv','docs/submission_audit_v02/batch_reference/run_arrival_snapshot.bat','scratch/calc_headway_v7.py','scratch/_task_log.txt','data/curated/occupancy_operation_gap.csv','data/curated/promise_linkage.csv','data/curated/forward_monitoring.csv'])
    for row in read_csv(OUT/'source_registry_v02.csv'):
        for key in ['local_path','local_text_path','raw_pdf_path','attachment_local_path']:
            p=ROOT/row.get(key,'')
            if p.is_file():inputs.add(p.relative_to(ROOT).as_posix())
    inputs.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'data/staged').glob('*.parquet'))
    write_csv(OUT/'analysis_inputs_v02.csv',[{'path':name,'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()} for name in sorted(inputs)])

if __name__=='__main__':run()
