import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import json

log_file = Path(r'C:\Users\parkd\.gemini\antigravity\brain\fa5287e3-4423-40ca-bde8-2d20101c86a3\.system_generated\logs\transcript.jsonl')
if log_file.exists():
    with open(log_file, encoding='utf-8', errors='ignore') as f:
        for idx, line in enumerate(f):
            data = json.loads(line)
            content = str(data.get('content', ''))
            if '-1.4%p' in content or '12.5%' in content:
                t = data.get('type')
                print(f'Line {idx} ({t}):')
                for l in content.split('\n'):
                    if any(x in l for x in ['-1.4%p', '12.5%', '-5.6%p']):
                        print('  ', l.strip()[:150])
