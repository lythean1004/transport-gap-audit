"""실제 저장 API 응답의 첨두시간별 원장·파일·실제 호출시각 대조."""
from datetime import datetime
from collections import Counter
import hashlib,json,re,ast
from scripts.submission.audit import ROOT,read_csv,write_csv
from scripts.submission.review_v02 import OUT,AUDIT
from src.collectors.arrival_slots import WINDOWS,build_slot_labels

def window_label(slot):
    slot=str(slot).zfill(4)
    for label,(start,end) in zip(['AM','PM'],WINDOWS):
        if start.replace(':','')<=slot<end.replace(':',''):return label
    return 'outside'

def timestamp_offset(row):
    s=row['slot_hhmm'].zfill(4)
    nominal=datetime.fromisoformat(row['obs_date']+'T'+s[:2]+':'+s[2:]+':00+09:00')
    return (datetime.fromisoformat(row['called_at_kst'])-nominal).total_seconds()

def parse_call_log(text):
    return [(ast.literal_eval(key),outcome,int(items)) for key,outcome,items in re.findall(r'\[(?:SWEEP )?CALLED\] key=(\([^\n]+?\)) outcome=(\S+) items=(\d+)',text)]

def run():
    rows=read_csv(ROOT/'evidence/arrival_ledger.csv');last={}
    for r in rows:last[(r['obs_date'],r['slot_hhmm'],r['citycode'],r['nodeid'])]=r
    files=[];schema=Counter();days=sorted({r['obs_date'] for r in rows})
    for r in last.values():
        if r['outcome'] not in {'ok_empty','ok_with_items'}:continue
        p=ROOT/r['raw_path'];raw=p.read_bytes();response=json.loads(raw)['response'];items=response['body'].get('items') or {};items=items.get('item',[]) if isinstance(items,dict) else items
        if isinstance(items,dict):items=[items]
        for item in items:schema[tuple(sorted(item))]+=1
        files.append({'obs_date':r['obs_date'],'nominal_slot':r['slot_hhmm'],'window':window_label(r['slot_hhmm']),'called_at_kst':r['called_at_kst'],'offset_seconds':timestamp_offset(r),'outcome':r['outcome'],'result_code':str(response['header']['resultCode']),'items':len(items),'ledger_item_count_matches':len(items)==int(r['item_count']),'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),'data_kind':'stored_live_api_response','measurement':'arrival_prediction_at_actual_request_time'})
    windows=[]
    for day in days:
        for label in ['AM','PM']:
            f=[x for x in files if x['obs_date']==day and x['window']==label];rr=[x for x in rows if x['obs_date']==day and window_label(x['slot_hhmm'])==label];expected=sum(window_label(x)==label for x in build_slot_labels())
            windows.append({'obs_date':day,'window':label,'planned_slots':expected,'stored_success_files':len(f),'with_items':sum(x['items']>0 for x in f),'ok_empty':sum(x['items']==0 for x in f),'missing_success_slots':expected-len(f),'response_items':sum(x['items'] for x in f),'api_error_attempts':sum(x['outcome']=='api_error' for x in rr),'first_called_at':min((x['called_at_kst'] for x in f),default=''),'last_called_at':max((x['called_at_kst'] for x in f),default=''),'offset_at_least_5_minutes':sum(x['offset_seconds']>=300 for x in f)})
    write_csv(OUT/'actual_collection_windows_v02.csv',windows)
    write_csv(OUT/'actual_collection_files_v02.csv',files)
    log=ROOT/'scratch/_task_log.txt'
    text=log.read_bytes().decode('utf-8',errors='replace')
    calls=parse_call_log(text)
    ledger_calls=Counter(((r['obs_date'],r['slot_hhmm'],r['citycode'],r['nodeid']),r['outcome'],int(r['item_count'])) for r in rows)
    log_calls=Counter(calls)
    summary={'data_kind':'stored_live_api_response','raw_files':len(files),'response_items':sum(x['items'] for x in files),'item_count_mismatches':sum(not x['ledger_item_count_matches'] for x in files),'response_schemas':[{'fields':list(k),'items':v} for k,v in schema.items()],'task_log_path':log.relative_to(ROOT).as_posix(),'task_log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'log_called_markers':len(re.findall(r'\[CALLED\]',text)),'batch_file_linkage':'pending_user_provided_batch_path','note':'원자료는 실제 시각의 API 응답이다. 실제 차량 통과시각을 직접 측정한 데이터와는 구분한다. 예약 작업은 조회만 하고 등록/수정하지 않았다.'}
    summary.update(log_sweep_called_markers=len(re.findall(r'\[SWEEP CALLED\]',text)),log_total_calls=len(calls),log_ledger_records_equal=log_calls==ledger_calls,log_only_records=sum((log_calls-ledger_calls).values()),ledger_only_records=sum((ledger_calls-log_calls).values()))
    batch=AUDIT/'batch_reference/run_arrival_snapshot.bat'
    if batch.exists():
        bt=batch.read_text(encoding='utf-8-sig')
        linked='-m src.collectors.arrival_snapshot' in bt and 'scratch\\_task_log.txt' in bt
        summary.update(batch_file_linkage='confirmed_against_user_provided_batch' if linked else 'batch_command_requires_review',batch_reference_path=batch.relative_to(ROOT).as_posix(),batch_sha256=hashlib.sha256(batch.read_bytes()).hexdigest(),batch_collector_module='src.collectors.arrival_snapshot' if linked else '',batch_executed_this_audit=False)
    (AUDIT/'actual_collection_provenance_v02.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':run()
