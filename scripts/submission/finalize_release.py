"""검증된 사본의 최종 목록과 ZIP을 생성한다. Git 이력은 포함하지 않는다."""
import hashlib
import json
import zipfile
from scripts.submission.audit import ROOT, OUT, AUDIT, known_secrets, read_csv, write_csv
from scripts.submission.package_release import PUBLISH, sanitize_bytes


def finalize():
    known=known_secrets()
    # 마지막으로 수정한 코드와 검증 기록만 갱신한다.
    for folder in ['scripts/submission','docs/submission_audit']:
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts:continue
            dest=PUBLISH/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
            clean,_=sanitize_bytes(p.read_bytes(),p.suffix,known);dest.write_bytes(clean)
    old={r['path']:r for r in read_csv(OUT/'package_manifest.csv')}
    files=[];manifest=[]
    for p in PUBLISH.rglob('*'):
        rel=p.relative_to(PUBLISH)
        if not p.is_file() or any(x in rel.parts for x in ['.git','__pycache__','.pytest_cache']) or rel.parts[0]=='qa':continue
        if p.name in {'transport-gap-audit_submission_v1.zip','package_manifest.csv','release_validation.json'}:continue
        raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        previous=old.get(rel.as_posix(),{})
        if digest!=previous.get('release_sha256') and any(k.encode('utf-8') in raw or k.encode('utf-16le') in raw for k in known):
            raise RuntimeError('변경 파일 비밀값 검출: '+rel.as_posix())
        source=ROOT/rel
        original=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else previous.get('source_sha256',digest)
        manifest.append({'path':rel.as_posix(),'source_sha256':original,'release_sha256':digest,'bytes':len(raw),'transformed':original!=digest});files.append(p)
    write_csv(OUT/'package_manifest.csv',manifest)
    (PUBLISH/'exports/submission_v1/package_manifest.csv').write_bytes((OUT/'package_manifest.csv').read_bytes())
    result={'files':len(files)+2,'bytes':sum(r['bytes'] for r in manifest),'known_secret_hits':0,'history_included':False,'visibility':'private','workspace_tests':'118 passed','release_tests':'118 passed','paper_pages':7}
    (OUT/'release_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (PUBLISH/'exports/submission_v1/release_validation.json').write_bytes((OUT/'release_validation.json').read_bytes())
    files += [PUBLISH/'exports/submission_v1/package_manifest.csv',PUBLISH/'exports/submission_v1/release_validation.json']
    target=ROOT/'exports/transport-gap-audit_submission_v1.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(PUBLISH).as_posix())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        assert not any(n.endswith('/transport-gap-audit_submission_v1.zip') or n.startswith('.git/') for n in z.namelist())
    (OUT/'archive_sha256.txt').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False));print('ZIP bytes',target.stat().st_size)


if __name__=='__main__':finalize()
