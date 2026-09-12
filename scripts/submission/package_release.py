"""비공개 배포 사본을 생성한다. 원본·과거 Git 이력·비밀파일은 수정하지 않는다."""
import hashlib
import csv
import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from scripts.submission.audit import ROOT, OUT, AUDIT, known_secrets, TOKEN_PATTERN, write_csv, logical_text

PUBLISH = ROOT/'qa/submission_v1/publish'
PRIVATE_NAMES = ('신청서','재학증명서','데이터관리','genspark와 검증한내용')
TEXT_SUFFIXES = {'.py','.md','.txt','.csv','.json','.yaml','.yml','.toml','.html','.htm','.ps1','.sql','.gitignore'}


def sanitize_bytes(raw, suffix, known, relative_paths=True):
    changed=False
    for secret in known:
        for codec in ['utf-8','utf-16le']:
            old=secret.encode(codec)
            if old in raw:
                raw=raw.replace(old,'REDACTED'.encode(codec));changed=True
    if not relative_paths and suffix.lower() not in {'.html','.htm'}:
        return raw,changed
    if suffix.lower() in TEXT_SUFFIXES:
        try:t=raw.decode('utf-8-sig')
        except UnicodeDecodeError:return raw,changed
        # HTML에 내장된 외부 서비스 키도 배포 사본에서 제거한다.
        if suffix.lower() in {'.html','.htm'}:
            t=TOKEN_PATTERN.sub(lambda m:m.group(0).replace(m.group(1),'REDACTED'),t)
        if relative_paths:
            if suffix.lower()=='.csv':
                reader=csv.DictReader(io.StringIO(t));rows=list(reader)
                for row in rows:
                    for key,value in row.items():
                        if isinstance(value,str) and str(ROOT) in value:
                            row[key]=value.replace(str(ROOT)+'\\','').replace('\\','/')
                stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=reader.fieldnames);writer.writeheader();writer.writerows(rows);t=stream.getvalue()
            for base in [str(ROOT),str(ROOT).replace('\\','\\\\'),ROOT.as_posix()]:
                t=t.replace(base+'\\\\','').replace(base+'\\','').replace(base+'/','')
        new=t.encode('utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8')
        changed=changed or new!=raw;raw=new
    return raw,changed


def package():
    PUBLISH.mkdir(parents=True,exist_ok=True)
    known=known_secrets();manifest=[];excluded=[]
    folders=['src','tests','scripts','tools','app','config','docs','data','evidence']
    paths=[p for folder in folders for p in (ROOT/folder).rglob('*') if p.is_file()]
    paths += [p for p in ROOT.iterdir() if p.is_file() and (p.suffix=='.py' or p.name in {'README.md','AGENTS.md','requirements.txt','pyproject.toml','.env.example','.gitignore','manual_overrides.csv','bldg_query_plan.csv'})]
    paths += [p for p in (ROOT/'exports').rglob('*') if p.is_file() and 'submission_v1' not in p.parts and p.name!='transport-gap-audit_submission_v1.zip']
    paths += [p for p in OUT.rglob('*') if p.is_file()]
    print('Packaging source files',len(paths),flush=True)
    for p in paths:
        rel=p.relative_to(ROOT)
        if '__pycache__' in rel.parts or p.suffix in {'.pyc','.log'} or '.egg-info' in str(rel) or any(x in p.name for x in PRIVATE_NAMES):continue
        if p.name.startswith('pytest_') or p.name in {'package_manifest.csv','release_validation.json'}:continue
        if p.name=='.gitignore' and rel.parts[0]=='exports':continue
        raw=p.read_bytes()
        # 원자료는 바이트 보존. 원장의 키 제거와 다른 구조화 파일의 경로 이식은 파생본 처리.
        is_raw=rel.parts[:2] in [('data','raw'),('evidence','documents'),('evidence','arrival_raw')]
        cleaned,changed=sanitize_bytes(raw,p.suffix,known,relative_paths=not is_raw)
        dst=PUBLISH/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(cleaned)
        manifest.append({'path':rel.as_posix(),'source_sha256':hashlib.sha256(raw).hexdigest(),'release_sha256':hashlib.sha256(cleaned).hexdigest(),'bytes':len(cleaned),'transformed':changed})
        if len(manifest)%1000==0:print('Copied',len(manifest),flush=True)
    base=Path('C:/Users/parkd/Downloads/교통문제 데이터 분석 공모전_1022')
    for p in base.iterdir():
        if not p.is_file() or p.name.startswith('~$'):continue
        if any(x in p.name for x in PRIVATE_NAMES):
            excluded.append({'file':p.name,'reason':'private_admin_or_unrelated_reference'});continue
        raw=p.read_bytes()
        # 압축 문서는 논리 내용에 비밀값이 있으면 배포하지 않는다.
        if p.suffix in {'.docx','.xlsx','.zip'}:
            t=logical_text(p)
            if any(k in t for k in known):excluded.append({'file':p.name,'reason':'secret_in_office_or_archive'});continue
        elif any(k.encode('utf-8') in raw for k in known):
            excluded.append({'file':p.name,'reason':'secret_in_attachment'});continue
        dst=PUBLISH/'docs/submission_audit/prior_references'/p.name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
        manifest.append({'path':dst.relative_to(PUBLISH).as_posix(),'source_sha256':hashlib.sha256(raw).hexdigest(),'release_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'transformed':False})
    # 연구 패키지에서는 승인된 데이터·산출물을 추적하고 로컬 비밀정보만 제외한다.
    (PUBLISH/'.gitignore').write_text('.env\n.env.*\n!.env.example\n.venv/\n__pycache__/\n*.py[cod]\n.pytest_cache/\nqa/\n.streamlit/secrets.toml\n*.log\n',encoding='utf-8')
    write_csv(AUDIT/'excluded_files.csv',excluded,['file','reason'])
    write_csv(PUBLISH/'docs/submission_audit/excluded_files.csv',excluded,['file','reason'])
    # 변환된 원문의 참조 해시는 배포본 해시로 연결한다. 원본 해시는 패키지 목록에 보존한다.
    hash_map={r['source_sha256']:r['release_sha256'] for r in manifest if r['source_sha256']!=r['release_sha256'] and r['path'].endswith(('.html','.htm'))}
    for row in manifest:
        p=PUBLISH/row['path']
        if p.suffix not in {'.csv','.json'}:continue
        try:t=p.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:continue
        old=t
        for a,b in hash_map.items():t=t.replace(a,b)
        if t!=old:p.write_text(t,encoding='utf-8-sig');row['transformed']=True
    print('Sanitized copies and remapped references',flush=True)
    # 최종 사본 기준으로 무결성 목록을 재계산한다.
    for row in manifest:
        row['release_sha256']=hashlib.sha256((PUBLISH/row['path']).read_bytes()).hexdigest()
        row['bytes']=(PUBLISH/row['path']).stat().st_size
    write_csv(OUT/'package_manifest.csv',manifest)
    shutil.copy2(OUT/'package_manifest.csv',PUBLISH/'exports/submission_v1/package_manifest.csv')
    hits=[]
    for p in PUBLISH.rglob('*'):
        rel=p.relative_to(PUBLISH)
        if not p.is_file() or any(x in rel.parts for x in ['.git','__pycache__','.pytest_cache']) or rel.parts[0]=='qa':continue
        raw=p.read_bytes()
        if any(k.encode('utf-8') in raw or k.encode('utf-16le') in raw for k in known):hits.append(p.relative_to(PUBLISH).as_posix())
    if hits:raise RuntimeError('배포 비밀값 검사 실패: '+str(hits))
    print('Known-secret scan passed',flush=True)
    result={'files':len(manifest),'bytes':sum(r['bytes'] for r in manifest),'known_secret_hits':len(hits),'excluded_attachments':len(excluded),'history_included':False,'visibility':'private'}
    (OUT/'release_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(OUT/'release_validation.json',PUBLISH/'exports/submission_v1/release_validation.json')
    target=ROOT/'exports/transport-gap-audit_submission_v1.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PUBLISH.rglob('*'):
            rel=p.relative_to(PUBLISH)
            if p.is_file() and not any(x in rel.parts for x in ['.git','__pycache__','.pytest_cache']) and rel.parts[0]!='qa':z.write(p,rel.as_posix())
    with zipfile.ZipFile(target) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC 검증 실패')
    print(json.dumps(result,ensure_ascii=False));print('ZIP bytes',target.stat().st_size)


if __name__=='__main__':package()
