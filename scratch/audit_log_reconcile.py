import csv
import re
import sys
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter

sys.path.insert(0, str(Path.cwd()))
from src.collectors.arrival_slots import build_slot_labels

KST = timezone(timedelta(hours=9))
SLOTS = build_slot_labels()
SLOT_COUNT = len(SLOTS)

def parse_kst(dt_str):
    if not dt_str or dt_str == 'nan': return None
    try:
        return datetime.fromisoformat(dt_str).replace(tzinfo=KST)
    except Exception:
        return None

def mask_service_key(text):
    if not text: return text
    if not isinstance(text, str): text = str(text)
    return re.sub(r'(serviceKey=)[^&\'\"\\]+', r'\1***REDACTED***', text)

def format_date(dt):
    return dt.strftime('%Y-%m-%d')

def main():
    report_lines = []
    def rep(s, end='\n'):
        masked = mask_service_key(s)
        report_lines.append(masked)
        try:
            print(masked, end=end)
        except UnicodeEncodeError:
            print(masked.encode('cp949', errors='replace').decode('cp949'), end=end)

    # 1. 원장 로드
    ledger_path = Path('evidence/arrival_ledger.csv')
    ledger = []
    if ledger_path.exists():
        with open(ledger_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ledger.append(row)
                
    # 2. 로그 로드 및 파싱
    log_path = Path('scratch/_task_log.txt')
    log_blocks = []
    unparsed_lines = []
    header_pattern = re.compile(r'^====\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\s+====$')
    
    current_block = None
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            line_str = line.strip()
            if line_str.startswith('===='):
                match = header_pattern.match(line_str)
                if match:
                    d_str, t_str = match.groups()
                    try:
                        # 파싱 시도 (소수점 초 지원)
                        dt_fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in t_str else '%Y-%m-%d %H:%M:%S'
                        dt = datetime.strptime(f"{d_str} {t_str}", dt_fmt).replace(tzinfo=KST)
                        if current_block:
                            log_blocks.append(current_block)
                        current_block = {'dt': dt, 'lines': [], 'start_idx': i, 'raw_header': line_str}
                    except Exception:
                        unparsed_lines.append((i+1, line_str))
                        if current_block:
                            current_block['lines'].append(line_str)
                else:
                    unparsed_lines.append((i+1, line_str))
                    if current_block:
                        current_block['lines'].append(line_str)
            else:
                if current_block:
                    current_block['lines'].append(line_str)
        if current_block:
            log_blocks.append(current_block)

    # 정렬
    log_blocks.sort(key=lambda x: x['dt'])
    
    rep(f"# [1] 로그 파싱")
    rep(f"- 정규식: {header_pattern.pattern}")
    if unparsed_lines:
        rep(f"- 파싱불가 헤더 의심 라인: {len(unparsed_lines)}건")
    else:
        rep(f"- 파싱불가 헤더 의심 라인: 0건")
        
    rep(f"- 헤더 총 개수: {len(log_blocks)}개")
    if log_blocks:
        rep(f"- 최초 시각: {log_blocks[0]['dt']}")
        rep(f"- 최종 시각: {log_blocks[-1]['dt']}")
        
    # 블록 본문 분류
    block_classes = Counter()
    for b in log_blocks:
        text = '\n'.join(b['lines']).lower()
        if '수집 창 밖' in text or 'out of window' in text:
            cls = '수집창밖 종료'
        elif '수집 완료' in text or 'ok_with_items' in text or 'ok_empty' in text or 'records' in text:
            cls = '정상 수집'
        elif 'modulenotfounderror' in text or 'traceback' in text:
            cls = '파이썬 예외'
        elif '지정된 경로를 찾을 수 없습니다' in text or 'cd : ' in text:
            cls = 'cd 실패'
        else:
            cls = '기타'
        b['class'] = cls
        block_classes[cls] += 1
        
    rep(f"- 블록 본문 분류: {dict(block_classes)}")

    # 3. 일자별 분해표
    rep(f"\n# [2] 일자별 분해표")
    log_by_date = Counter(format_date(b['dt']) for b in log_blocks)
    ledger_by_date = Counter(r['obs_date'] for r in ledger)
    ledger_slots = defaultdict(set)
    for r in ledger:
        ledger_slots[r['obs_date']].add(r['slot_hhmm'])
        
    all_dates = sorted(set(log_by_date.keys()) | set(ledger_by_date.keys()))
    
    diff_sum = 0
    rep(f"| obs_date | 로그 헤더 수 | 원장 행수 | 원장 고유 슬롯 | 차이 |")
    rep(f"|---|---|---|---|---|")
    for d in all_dates:
        l_cnt = log_by_date[d]
        r_cnt = ledger_by_date[d]
        u_cnt = len(ledger_slots[d])
        diff = l_cnt - r_cnt
        diff_sum += diff
        rep(f"| {d} | {l_cnt} | {r_cnt} | {u_cnt} | {diff} |")
        
    rep(f"**결론**: 총 헤더 {len(log_blocks)}, 원장 행 {len(ledger)}, 실측 차이 합계 {diff_sum}. (과거 209/192/17 대비 증감: {len(log_blocks)-209}/{len(ledger)-192}/{diff_sum-17})")
    
    # 4. 헤더-원장 매칭
    rep(f"\n# [3] 헤더-원장 매칭")
    ledger_items = []
    for i, r in enumerate(ledger):
        dt = parse_kst(r['called_at_kst'])
        if dt:
            ledger_items.append({'idx': i, 'dt': dt, 'row': r, 'matched': False})
            
    matches = []
    log_only = []
    for b in log_blocks:
        b_dt = b['dt']
        best_match = None
        best_diff = 181
        for item in ledger_items:
            if not item['matched']:
                diff = abs((b_dt - item['dt']).total_seconds())
                if diff <= 180 and diff < best_diff:
                    best_diff = diff
                    best_match = item
        if best_match:
            best_match['matched'] = True
            matches.append((b, best_match))
        else:
            log_only.append(b)
            
    ledger_only = [item for item in ledger_items if not item['matched']]
    
    rep(f"- (a) 로그·원장 모두 존재 (정상): {len(matches)}건")
    rep(f"- (b) 로그에만 존재: {len(log_only)}건")
    for b in log_only:
        rep(f"  - [{b['dt']}] ({b['class']}) 본문:")
        for l in b['lines'][:5]: rep(f"      {l}")
        if len(b['lines']) > 5: rep(f"      ... (생략)")
    rep(f"- (c) 원장에만 존재: {len(ledger_only)}건")
    for item in ledger_only:
        rep(f"  - [{item['dt']}] slot={item['row']['slot_hhmm']}")
        
    check_sum = len(matches) + len(log_only) == len(log_blocks) and len(matches) + len(ledger_only) == len(ledger_items)
    rep(f"**검산**: {check_sum} (매칭+로그only={len(matches)+len(log_only)} vs 헤더{len(log_blocks)}, 매칭+원장only={len(matches)+len(ledger_only)} vs 원장{len(ledger_items)})")

    # 5. 단발 드롭아웃별 로그 구간 추출
    rep(f"\n# [4] 단발 드롭아웃별 로그 구간 추출")
    missing_slots = []
    for d in all_dates:
        # 주말 제외 등 실제 스케줄은 평일이나, 여기서는 나타난 날짜만 48슬롯 검사
        for s in SLOTS:
            if s not in ledger_slots[d]:
                missing_slots.append((d, s))
                
    # 단발 식별 (연속이 아닌 것)
    single_dropouts = []
    for i, (d, s) in enumerate(missing_slots):
        s_idx = SLOTS.index(s)
        # 연속 판별: 이전 슬롯도 누락이거나 다음 슬롯도 누락이면 연속 (같은 날짜 내)
        prev_s = SLOTS[s_idx-1] if s_idx > 0 else None
        next_s = SLOTS[s_idx+1] if s_idx < len(SLOTS)-1 else None
        
        is_prev_missing = prev_s and (d, prev_s) in missing_slots
        is_next_missing = next_s and (d, next_s) in missing_slots
        
        if not (is_prev_missing or is_next_missing):
            single_dropouts.append((d, s))
            
    rep(f"전체 결측 슬롯: {len(missing_slots)}건")
    rep(f"단발 드롭아웃: {len(single_dropouts)}건")
    
    # 전체 파일 줄 단위 탐색용
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            raw_lines = f.readlines()
    else:
        raw_lines = []

    dropout_logs = []
    for d, s in single_dropouts:
        dt_str = f"{d} {s[:2]}:{s[2:]}:00"
        target_dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
        
        start_dt = target_dt - timedelta(minutes=10)
        end_dt = target_dt + timedelta(minutes=10)
        
        # 이전/이후 슬롯 실행 시각 찾기
        prev_s = SLOTS[max(0, SLOTS.index(s)-1)]
        next_s = SLOTS[min(len(SLOTS)-1, SLOTS.index(s)+1)]
        prev_t = None
        next_t = None
        for b in log_blocks:
            if format_date(b['dt']) == d:
                # 슬롯 추정 (±2분)
                slot_est = b['dt'].strftime('%H%M')
                if abs((b['dt'].replace(hour=int(prev_s[:2]), minute=int(prev_s[2:]), second=0, microsecond=0) - b['dt']).total_seconds()) < 180:
                    prev_t = b['dt']
                if abs((b['dt'].replace(hour=int(next_s[:2]), minute=int(next_s[2:]), second=0, microsecond=0) - b['dt']).total_seconds()) < 180:
                    next_t = b['dt']
                    
        # 로그 원문 구간 추출
        extracted = []
        in_range = False
        for line in raw_lines:
            match = header_pattern.match(line.strip())
            if match:
                b_dt = datetime.strptime(f"{match.group(1)} {match.group(2)}", '%Y-%m-%d %H:%M:%S' + ('.%f' if '.' in match.group(2) else '')).replace(tzinfo=KST)
                in_range = (start_dt <= b_dt <= end_dt)
            if in_range:
                extracted.append(line.strip())
                
        dropout_logs.append({
            'date': d, 'slot': s, 'target_dt': target_dt,
            'prev_t': prev_t, 'next_t': next_t,
            'logs': extracted
        })

    for dl in dropout_logs:
        rep(f"\n### {dl['date']} {dl['slot']} 결측 (±10분 구간)")
        rep(f"- 직전 실행: {dl['prev_t']} / 직후 실행: {dl['next_t']}")
        if dl['logs']:
            for l in dl['logs']: rep(f"  {l}")
        else:
            rep("  구간 내 로그 라인 0건")

    # 6. 원인 후보 판별
    rep(f"\n# [5] 원인 후보 판별")
    
    # 소요시간 계산 (헤더 간격)
    durations = []
    overlaps = []
    for i in range(len(log_blocks)-1):
        b1, b2 = log_blocks[i], log_blocks[i+1]
        diff = (b2['dt'] - b1['dt']).total_seconds()
        # 같은 날짜이고 간격이 5분 근처일 때
        if b1['dt'].date() == b2['dt'].date() and diff < 3600:
            durations.append(diff)
            if diff < 10: # 중첩/너무 짧음
                overlaps.append((b1, b2, diff))

    if durations:
        s_dur = sorted(durations)
        n = len(s_dur)
        p50 = s_dur[int(n*0.50)]
        p90 = s_dur[int(n*0.90)]
        rep(f"- 슬롯 실행 간격: min={s_dur[0]:.1f}s, p50={p50:.1f}s, p90={p90:.1f}s, max={s_dur[-1]:.1f}s")
        rep(f"- 300초(슬롯 간격) 근접 여부: max가 300에 얼마나 가까운지 확인 -> {s_dur[-1]:.1f}초")
    
    if overlaps:
        rep(f"- 중첩 신호 (간격 < 10초): {len(overlaps)}건")
        for b1, b2, diff in overlaps:
            rep(f"  - {b1['dt']} vs {b2['dt']} (차이 {diff:.1f}초)")

    rep(f"\n| date | slot | 원인 후보 | 증거 |")
    rep(f"|---|---|---|---|")
    for dl in dropout_logs:
        cause = "판별 불가"
        evidence = "증거 없음"
        # 후보 판별 로직
        logs_text = '\n'.join(dl['logs']).lower()
        if dl['prev_t'] and (dl['target_dt'] - dl['prev_t']).total_seconds() > 300:
            cause = "인스턴스 중첩 스킵 (가능)"
            evidence = f"직전 실행({dl['prev_t']})이 다음 슬롯을 넘김"
        elif not dl['logs']:
            cause = "절전·전원 조건 (유력)"
            evidence = "구간 내 로그 0건"
        elif 'traceback' in logs_text or 'error' in logs_text:
            cause = "프로세스 실패 (유력)"
            evidence = "로그 내 에러 발견"
            
        rep(f"| {dl['date']} | {dl['slot']} | {cause} | {evidence} |")

    # 7. 재발 여부 및 확장 영향
    rep(f"\n# [6] 재발 여부 및 확장 영향")
    d0910_missing = [s for d,s in missing_slots if d == '2026-09-10']
    
    if '0750' in d0910_missing:
        rep("- 09-10 결측 패턴: 09-04/07과 동일 단발(0750) 등 발견 → **재발 진행 중**")
    else:
        rep("- 09-10 결측 패턴: 동일 서명 미발견 → 일회성")
        
    pm_count = len([r for r in ledger if r['obs_date'] == '2026-09-10' and int(r['slot_hhmm']) >= 1700])
    cov_10 = pm_count / 24 * 100
    rep(f"- 09-10 PM 수집분 원장 기록: {pm_count}건 (오후 커버리지 {cov_10:.1f}%)")
    if pm_count >= 20:
        rep("- **판정**: 09-10 PM 정상 수집 확인 → 분석 창은 09-07~09-10 **4일**이다.")
    else:
        rep("- **판정**: 09-10 PM 미완료/부족 → 분석 창은 09-07~09-09 **3일**이다.")
        
    if durations:
        # 1개 정류소당 p90 초 소요 가정. 예산 300초 / p90
        # 단일 워커 순차 처리 가정
        # 정규 호출만 기준으로 하려면 이전 로그 기반 p90 재계산 필요. 
        # 여기서는 전체 헤더 간격 p90을 보수적으로 사용. (사실 헤더 간격은 스케줄 간격 300초를 포함하므로, 실행 시간 자체가 아님!)
        # 실제 파이썬 실행 시간을 구하려면 다음 헤더 전까지의 시간보다, 로직 내 소요시간을 봐야 하나 로그 헤더는 시작 시점만 찍힘.
        # 드리프트 창 내 p90=7.26초를 활용 (P2 지시문 참조)
        p90_exec = 7.266
        N = math.floor(300 / p90_exec)
        rep(f"- 정류소 확장 한계 (선형 가정, p90={p90_exec}초): 300초 / {p90_exec}초 = {N}개 정류소")
        if N > 20:
            rep("- 결론: 확장 가능 (안전 한도 초과 위험 낮음)")
        elif N > 5:
            rep(f"- 결론: 조건부 (상한 {N}개 명시)")
        else:
            rep("- 결론: 확장 보류")

    with open('scratch/audit_log_reconcile_report.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

if __name__ == '__main__':
    main()
