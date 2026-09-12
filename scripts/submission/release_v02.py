"""정제된 V01 Git 체크아웃에 V02 배포 파일을 추가하고 검증 ZIP을 만든다."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from scripts.submission.audit import ROOT,known_secrets,write_csv,read_csv,secret_findings
from scripts.submission.package_release import PUBLISH,sanitize_bytes,PRIVATE_NAMES
from scripts.submission.inventory_v02 import read_content
from scripts.submission.review_v02 import OUT,AUDIT

def allowed(rel):
    p=Path(rel)
    if any(x in {'.git','.venv','__pycache__','.pytest_cache','qa','.agents','.codex'} or x.startswith('.pytest_tmp') for x in p.parts):return False
    if p.name.startswith('~$') or p.suffix in {'.pyc','.log'} or '.egg-info' in str(p):return False
    if p.name.startswith('.env') and p.name!='.env.example':return False
    if p.name=='secrets.toml' or any(x in p.name for x in PRIVATE_NAMES):return False
    if p.name.startswith('transport-gap-audit_submission_') and p.suffix=='.zip':return False
    return True

def stage():
    known=known_secrets();excluded=[];manifest=[];folders=['src','tests','scripts','tools','app','config','docs','data','evidence','scratch','tmp','exports']
    paths=[p for folder in folders for p in (ROOT/folder).rglob('*') if p.is_file()]
    paths += [p for p in ROOT.iterdir() if p.is_file()]
    for p in paths:
        rel=p.relative_to(ROOT)
        if not allowed(rel):excluded.append({'path':rel.as_posix(),'reason':'private_runtime_or_generated_archive'});continue
        if rel.parts[:2] in [('exports','submission_v1'),('docs','submission_audit')]:continue
        if p.name in {'package_manifest_v02.csv','release_validation_v02.json','archive_sha256_v02.txt'}:continue
        raw=p.read_bytes()
        dst=PUBLISH/rel
        if p.suffix.lower() in {'.docx','.xlsx','.zip','.hwpx','.hwp','.pdf'}:
            logical=read_content(p)['text']
            if any(k in logical for k in known):excluded.append({'path':rel.as_posix(),'reason':'credential_inside_document_archive'});continue
        is_raw=rel.parts[:2] in [('data','raw'),('evidence','documents'),('evidence','arrival_raw')]
        clean,_=sanitize_bytes(raw,p.suffix,known,relative_paths=not is_raw)
        # 배포 추적 규칙은 원본 작업공간의 scratch/data 제외 규칙과 분리한다.
        if rel.as_posix()=='.gitignore':clean=dst.read_bytes() if dst.exists() else b'.env\n.env.*\n!.env.example\n.venv/\n__pycache__/\n*.py[cod]\n.pytest_cache/\nqa/\n.streamlit/secrets.toml\n*.log\n'
        dst=PUBLISH/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists() or dst.read_bytes()!=clean:dst.write_bytes(clean)
        manifest.append({'path':rel.as_posix(),'source_sha256':hashlib.sha256(raw).hexdigest(),'release_sha256':hashlib.sha256(clean).hexdigest(),'bytes':len(clean),'transformed':raw!=clean})
    # 정제된 HTML 원문에 대한 경로/해시 연결을 배포 사본에서 유지한다.
    mapping={r['source_sha256']:r['release_sha256'] for r in manifest if r['transformed'] and r['path'].endswith(('.html','.htm'))}
    for r in manifest:
        p=PUBLISH/r['path']
        if p.suffix not in {'.csv','.json'}:continue
        try:text=p.read_text(encoding='utf-8-sig')
        except UnicodeError:continue
        before=text
        for a,b in mapping.items():text=text.replace(a,b)
        if text!=before:p.write_text(text,encoding='utf-8-sig')
    write_csv(AUDIT/'release_exclusions_v02.csv',excluded,['path','reason'])
    (PUBLISH/'docs/submission_audit_v02/release_exclusions_v02.csv').write_bytes((AUDIT/'release_exclusions_v02.csv').read_bytes())
    print('V02 배포 준비 파일',len(manifest),'제외',len(excluded))

def finalize(make_archive=True):
    known=known_secrets();files=[];manifest=[];flags=[]
    for p in PUBLISH.rglob('*'):
        rel=p.relative_to(PUBLISH)
        if not p.is_file() or not allowed(rel):continue
        if p.name in {'package_manifest_v02.csv','release_validation_v02.json','archive_sha256_v02.txt'}:continue
        raw=p.read_bytes()
        if any(k.encode('utf-8') in raw or k.encode('utf-16le') in raw for k in known):raise RuntimeError('비밀값 검출: '+rel.as_posix())
        if p.suffix.lower() in {'.docx','.xlsx','.zip','.hwpx','.hwp','.pdf'}:
            text=read_content(p)['text']
            if any(k in text for k in known):raise RuntimeError('압축/문서 비밀값 검출: '+rel.as_posix())
        elif p.suffix.lower() in {'.py','.md','.txt','.log','.json','.csv','.ps1','.bat','.cmd','.yaml','.toml'}:
            text=raw.decode('utf-8',errors='replace')
            for hit in secret_findings(text,known):flags.append({'path':rel.as_posix(),**hit})
        source=ROOT/rel;original=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else ''
        manifest.append({'path':rel.as_posix(),'source_sha256':original,'release_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'transformed':original!=hashlib.sha256(raw).hexdigest() if original else 'prior_reference'});files.append(p)
    write_csv(AUDIT/'release_pattern_review_v02.csv',flags,['path','line','kind'])
    resolved_path=AUDIT/'release_pattern_resolution_v02.csv'
    resolved=read_csv(resolved_path) if resolved_path.exists() else []
    approvals={(r['path'],str(r['line']),r['kind'],r.get('file_sha256','')) for r in resolved if r.get('actual_credential')=='False'}
    unresolved=[r for r in flags if (r['path'],str(r['line']),r['kind'],hashlib.sha256((PUBLISH/r['path']).read_bytes()).hexdigest()) not in approvals]
    if make_archive and unresolved:raise RuntimeError('문맥 검토가 필요한 자격증명 패턴: '+str(len(unresolved)))
    write_csv(OUT/'package_manifest_v02.csv',manifest)
    validation={'files_before_manifests':len(files),'known_secret_hits':0,'credential_pattern_candidates':len(flags),'unresolved_credential_patterns':len(unresolved),'git_history_in_zip':False,'visibility':'private','paper_pages':None,'tests':'see docs/submission_audit_v02/pytest_final.txt'}
    import fitz
    with fitz.open(OUT/'교통데이터공모전_논문_V02.pdf') as doc:validation['paper_pages']=len(doc)
    (OUT/'release_validation_v02.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    if not make_archive:
        print(json.dumps(validation,ensure_ascii=False));return
    for name in ['package_manifest_v02.csv','release_validation_v02.json']:
        p=PUBLISH/'exports/submission_v02'/name;p.write_bytes((OUT/name).read_bytes());files.append(p)
    target=ROOT/'exports/transport-gap-audit_submission_v02.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(PUBLISH).as_posix())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        assert not any(n.startswith('.git/') or Path(n).name.startswith('transport-gap-audit_submission_') and n.endswith('.zip') for n in z.namelist())
    (OUT/'archive_sha256_v02.txt').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='utf-8')
    print(json.dumps(validation,ensure_ascii=False));print('ZIP bytes',target.stat().st_size)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',action='store_true');parser.add_argument('--finalize',action='store_true');parser.add_argument('--scan',action='store_true');args=parser.parse_args()
    if args.stage:stage()
    if args.finalize:finalize()
    elif args.scan:finalize(make_archive=False)
