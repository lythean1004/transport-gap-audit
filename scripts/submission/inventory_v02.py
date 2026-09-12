"""전수 파일 목록. 기계 판독과 사람의 의미 검토를 구분한다."""
from pathlib import Path
from collections import Counter
import hashlib, json, io, zipfile, csv, os, re
from scripts.submission.audit import ROOT, write_csv, known_secrets, secret_findings

AUDIT=ROOT/'docs/submission_audit_v02'
DOWNLOAD=Path('C:/Users/parkd/Downloads/교통문제 데이터 분석 공모전_1022')
TEXT={'.py','.md','.txt','.csv','.psv','.bak','.example','.json','.jsonl','.yaml','.yml','.toml','.html','.htm','.ps1','.sql','.log','.xml','.ini','.cfg','.bat','.gitignore'}

def disposition(rel):
    parts=Path(rel).parts
    if '.git' in parts:return 'git_metadata_history_audited_separately'
    if Path(rel).name.startswith('~$'):return 'generated_or_runtime'
    if any(p in {'.venv','__pycache__','.pytest_cache'} or p.startswith('.pytest_tmp') for p in parts) or parts[0]=='qa':return 'generated_or_runtime'
    if 'transport-gap-audit_submission_v1' in parts or str(rel).endswith(('transport-gap-audit_submission_v1.zip','transport-gap-audit_submission_v02.zip')):return 'previous_release_copy'
    if str(rel).replace('\\','/').startswith('docs/submission_audit_v02/'):return 'current_audit_output'
    if Path(rel).name=='.env' or any(s in Path(rel).name for s in ['신청서','재학증명서','데이터관리']):return 'private_admin_or_secret'
    return 'research_content'

def read_content(path):
    result={'read_status':'read_failed','text_chars':0,'archive_members':[],'text':''}
    try:
        raw=path.read_bytes();suffix=path.suffix.lower();text=''
        if suffix in TEXT or path.name in {'.env','.gitignore'}:
            for codec in ['utf-8-sig','utf-16','cp949']:
                try:text=raw.decode(codec);break
                except UnicodeError:continue
            else:text=raw.decode('utf-8',errors='replace')
            result['read_status']='text_read'
        elif suffix in {'.zip','.docx','.xlsx','.hwpx'}:
            texts=[]
            def walk(blob,prefix='',depth=0):
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    for item in z.infolist():
                        if item.is_dir():continue
                        name=prefix+item.filename;result['archive_members'].append(name)
                        content=z.read(item)
                        if item.filename.lower().endswith('.zip') and depth<5:walk(content,name+'!',depth+1)
                        elif Path(item.filename).suffix.lower() in TEXT or item.filename.endswith('.env'):
                            if item.filename.endswith('.xml'):
                                import xml.etree.ElementTree as ET
                                texts.append(name+'\n'+' '.join(ET.fromstring(content).itertext()))
                            else:texts.append(name+'\n'+content.decode('utf-8',errors='replace'))
            walk(raw);text='\n'.join(texts);result['read_status']='archive_members_read'
        elif suffix=='.pdf':
            import fitz
            with fitz.open(path) as d:
                text='\n'.join(p.get_text() for p in d);result['pages']=len(d)
            result['read_status']='pdf_text_read' if text.strip() else 'visual_review_required'
        elif suffix=='.parquet':
            import polars as pl
            df=pl.read_parquet(path);result.update(rows=df.height,columns=df.width)
            text=df.write_csv();result['read_status']='all_table_rows_read'
        elif suffix=='.hwp':
            import olefile,zlib,struct
            with olefile.OleFileIO(str(path)) as ole:
                header=ole.openstream('FileHeader').read();compressed=bool(struct.unpack_from('<I',header,36)[0]&1)
                chunks=[]
                for stream in ole.listdir():
                    if stream[0]=='BodyText':
                        body=ole.openstream(stream).read()
                        if compressed:body=zlib.decompress(body,-15)
                        pos=0
                        while pos+4<=len(body):
                            rec=struct.unpack_from('<I',body,pos)[0];pos+=4;tag=rec&1023;size=rec>>20
                            if size==4095:size=struct.unpack_from('<I',body,pos)[0];pos+=4
                            if tag==67:chunks.append(body[pos:pos+size].decode('utf-16le',errors='replace'))
                            pos+=size
                text='\n'.join(chunks)
            result['read_status']='hwp_text_read' if text.strip() else 'visual_review_required'
        elif suffix in {'.png','.jpg','.jpeg','.gif','.webp'}:
            from PIL import Image
            with Image.open(path) as im:im.load();result['image_size']=str(im.size)
            result['read_status']='image_decoded_visual_review_pending'
        else:result['read_status']='binary_read_semantics_pending'
        result.update(text_chars=len(text),text=text)
    except Exception as exc:result['error_type']=type(exc).__name__
    return result

def run():
    AUDIT.mkdir(parents=True,exist_ok=True)
    rows=[];signals=[];members=[];errors=[];known=known_secrets();cache={}
    for label,base in [('project',ROOT),('provided_download',DOWNLOAD)]:
        def onerror(e):errors.append({'scope':label,'path':str(e.filename),'error_type':type(e).__name__})
        for folder,dirs,files in os.walk(base,onerror=onerror,followlinks=False):
            for name in files:
                p=Path(folder)/name;rel=p.relative_to(base).as_posix();category=disposition(rel)
                row={'scope':label,'path':rel,'category':category,'bytes':'','sha256':'','duplicate_of':'','read_status':'not_content_read','text_chars':0,'semantic_review':'pending' if category=='research_content' else 'excluded_with_reason'}
                try:
                    row['bytes']=p.stat().st_size
                    if category in {'generated_or_runtime','git_metadata_history_audited_separately','previous_release_copy','current_audit_output'}:
                        rows.append(row);continue
                    raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest();row['sha256']=digest
                    if digest in cache:result,first=cache[digest];row['duplicate_of']=first
                    else:result=read_content(p);cache[digest]=(result,label+'/'+rel)
                    row.update(read_status=result['read_status'],text_chars=result['text_chars'])
                    text=result['text']
                    for member in result['archive_members']:members.append({'scope':label,'archive':rel,'member':member})
                    if category=='research_content':
                        flags=[]
                        if re.search(r'human_verified|verified_by|verified_at|manual_override|수동|검수|검증완료',text,re.I):flags.append('review_or_override')
                        if p.suffix=='.py' and re.search(r'(?i)mock|random|hardcod|human_verified.{0,15}0|gate_result.{0,15}FAIL',text):flags.append('code_assumption_review')
                        if secret_findings(text,known):flags.append('credential_review_no_values_logged')
                        if flags:signals.append({'scope':label,'path':rel,'flags':';'.join(flags),'duplicate_of':row['duplicate_of']})
                except Exception as exc:row['read_status']='read_failed';errors.append({'scope':label,'path':rel,'error_type':type(exc).__name__})
                rows.append(row)
    write_csv(AUDIT/'all_files_v02.csv',rows)
    write_csv(AUDIT/'archive_members_v02.csv',members)
    write_csv(AUDIT/'priority_content_review_v02.csv',signals)
    write_csv(AUDIT/'inventory_errors_v02.csv',errors,['scope','path','error_type'])
    summary={'inventory_rows':len(rows),'category_counts':dict(Counter(r['category'] for r in rows)),'read_status_counts':dict(Counter(r['read_status'] for r in rows)),'priority_files':len(signals),'archive_members':len(members),'filesystem_errors':len(errors),'statement':'Byte reads and machine parsing do not establish semantic completeness. Exclusions and pending visual reviews are explicit.'}
    (AUDIT/'inventory_summary_v02.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':run()
