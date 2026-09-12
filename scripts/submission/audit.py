"""원본을 변경하지 않는 제출 감사·날짜 구간 계산. 비밀값은 출력하지 않는다."""
from __future__ import annotations
import calendar
import csv
import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'docs/submission_audit'
OUT = ROOT / 'exports/submission_v1'
EXCLUDED_DIRS = {'.git', '.venv', '__pycache__', '.pytest_cache', '.agents', '.codex'}
TOKEN_PATTERN = re.compile(r'(?:serviceKey|TAGO_SERVICE_KEY|DATA_GO_KR_SERVICE_KEY|api_key|consumer_secret|access_token|password)[\s\"\x27]*[:=][\s\"\x27]*([A-Za-z0-9%_+/=.-]{16,})', re.I)


def date_bounds(value):
    value = str(value or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        try:
            d = date.fromisoformat(value)
            return d, d
        except ValueError:
            return None
    match = re.fullmatch(r'(\d{4})-H([12])', value)
    if match:
        y, h = map(int, match.groups())
        return date(y, 1 if h == 1 else 7, 1), date(y, 6, 30) if h == 1 else date(y, 12, 31)
    match = re.fullmatch(r'(\d{4})', value)
    if match:
        y = int(value)
        return date(y, 1, 1), date(y, 12, 31)
    match = re.fullmatch(r'(\d{4})(?:-|년\s*)(\d{1,2})월?', value)
    if match:
        y, m = map(int, match.groups())
    else:
        match = re.fullmatch(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{2})', value)
        if not match:
            return None
        m = list(calendar.month_abbr).index(match[1])
        y = 2000 + int(match[2])
    if not 1 <= m <= 12:
        return None
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def gap_bounds(start, end):
    a, b = date_bounds(start), date_bounds(end)
    if a is None or b is None:
        return None
    return (b[0] - a[1]).days, (b[1] - a[0]).days


def secret_findings(text, known):
    found = []
    for i, line in enumerate(text.splitlines(), 1):
        if any(k and len(k) >= 12 and k in line for k in known):
            found.append({'line': i, 'kind': 'known_secret'})
        elif TOKEN_PATTERN.search(line):
            found.append({'line': i, 'kind': 'credential_pattern_review'})
        elif re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN .*PRIVATE KEY-----)', line):
            found.append({'line': i, 'kind': 'private_credential'})
    return found


def known_secrets():
    import os
    values = [v for k, v in os.environ.items() if re.search('KEY|SECRET|TOKEN|PASSWORD', k, re.I) and len(v) >= 12]
    env = ROOT / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.split('=', 1)
                v = v.strip().strip('\"\x27')
                if re.search('KEY|SECRET|TOKEN|PASSWORD', k, re.I) and len(v) >= 12:
                    values.append(v)
    return list(set(values))


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]) if rows else fields or ['status'])
        w.writeheader()
        w.writerows(rows)


def logical_text(p):
    if p.suffix.lower() in {'.docx', '.xlsx', '.zip'}:
        with zipfile.ZipFile(p) as z:
            return '\n'.join(z.read(n).decode('utf-8', errors='replace') for n in z.namelist() if n.endswith(('.xml','.py','.txt','.md','.json','.csv','.env')))
    if p.suffix.lower() == '.pdf':
        import fitz
        with fitz.open(p) as d:
            return '\n'.join(page.get_text() for page in d)
    if p.suffix.lower() == '.parquet':
        import polars as pl
        return pl.read_parquet(p).write_csv()
    return p.read_bytes().decode('utf-8', errors='replace')


def run_inventory():
    AUDIT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    known = known_secrets()
    inventory, findings, profiles = [], [], []
    for p in ROOT.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(x in EXCLUDED_DIRS or x.startswith('.pytest_tmp') for x in rel.parts) or rel.parts[0] in {'qa','tmp','scratch','exports'} or rel.parts[:2] == ('docs','submission_audit'):
            continue
        raw = p.read_bytes()
        row = {'path': rel.as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        inventory.append(row)
        if p.name.startswith('.env') and p.name != '.env.example':
            findings.append({'path': rel.as_posix(), 'line': 0, 'kind': 'private_environment_excluded'})
            continue
        try:
            content = logical_text(p)
            findings.extend(dict(path=rel.as_posix(), **f) for f in secret_findings(content, known))
            if p.suffix == '.csv':
                rows = read_csv(p)
                profiles.append({'path': rel.as_posix(), 'rows': len(rows), 'columns': len(rows[0]) if rows else 0, 'exact_duplicate_rows': len(rows)-len({json.dumps(r,sort_keys=True) for r in rows}), 'mock_marker_count': content.count('MOCK_')})
            elif p.suffix == '.parquet':
                import polars as pl
                df = pl.read_parquet(p)
                profiles.append({'path': rel.as_posix(), 'rows': df.height, 'columns': df.width, 'exact_duplicate_rows': df.height-df.unique().height, 'mock_marker_count': content.count('MOCK_')})
        except Exception as e:
            findings.append({'path': rel.as_posix(), 'line': 0, 'kind': 'scan_error_' + type(e).__name__})
    history = []
    proc = subprocess.run(['git','rev-list','--objects','--all'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
    for line in proc.stdout.splitlines():
        oid, _, name = line.partition(' ')
        kind = subprocess.run(['git','cat-file','-t',oid],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        if kind != 'blob':
            continue
        raw = subprocess.run(['git','cat-file','blob',oid],cwd=ROOT,capture_output=True,check=True).stdout
        for f in secret_findings(raw.decode('utf-8',errors='replace'),known):
            history.append(dict(object=oid,path=name,**f))
    write_csv(AUDIT/'file_inventory.csv',inventory)
    write_csv(AUDIT/'data_profiles.csv',profiles)
    write_csv(AUDIT/'secret_findings.csv',findings, ['path','line','kind'])
    write_csv(AUDIT/'history_secret_findings.csv',history,['object','path','line','kind'])
    summary={'files':len(inventory),'bytes':sum(r['bytes'] for r in inventory),'secret_findings':dict(Counter(r['kind'] for r in findings)),'history_findings':dict(Counter(r['kind'] for r in history))}
    (AUDIT/'inventory_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == '__main__':
    run_inventory()
