# [1] 로그 파싱
- 정규식: ^====\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\s+====$
- 파싱불가 헤더 의심 라인: 0건
- 헤더 총 개수: 234개
- 최초 시각: 2026-09-04 08:20:52.830000+09:00
- 최종 시각: 2026-09-10 19:00:01.570000+09:00
- 블록 본문 분류: {'기타': 13, '정상 수집': 212, '파이썬 예외': 9}

# [2] 일자별 분해표
| obs_date | 로그 헤더 수 | 원장 행수 | 원장 고유 슬롯 | 차이 |
|---|---|---|---|---|
| 2026-09-04 | 37 | 30 | 30 | 7 |
| 2026-09-07 | 50 | 45 | 44 | 5 |
| 2026-09-08 | 50 | 49 | 48 | 1 |
| 2026-09-09 | 50 | 48 | 48 | 2 |
| 2026-09-10 | 47 | 43 | 43 | 4 |
**결론**: 총 헤더 234, 원장 행 215, 실측 차이 합계 19. (과거 209/192/17 대비 증감: 25/23/2)

# [3] 헤더-원장 매칭
- (a) 로그·원장 모두 존재 (정상): 213건
- (b) 로그에만 존재: 21건
  - [2026-09-04 08:21:11.110000+09:00] (정상 수집) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-04 08:23:43.230000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-04 08:25:01.800000+09:00] (정상 수집) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-04 09:00:05.830000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-04 17:15:02.220000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-04 17:55:02.320000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-04 19:00:34.070000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-07 07:40:02.310000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-07 08:00:01.960000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-07 08:55:02.110000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-07 09:00:02.420000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-07 17:55:02.780000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-07 19:00:02.220000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-08 09:00:02.090000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-08 19:00:02.660000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-09 09:00:01.970000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-09 19:00:02.130000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-10 07:50:01.340000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-10 09:00:01.470000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
  - [2026-09-10 18:15:01.700000+09:00] (파이썬 예외) 본문:
      Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "src\collectors\arrival_snapshot.py", line 421, in <module>
      main()
      ... (생략)
  - [2026-09-10 19:00:01.570000+09:00] (기타) 본문:
      === PREFLIGHT CHECK ===
      stops: 1
      slots_per_day: 48
      calls_per_day: 48
      total: 144
      ... (생략)
- (c) 원장에만 존재: 2건
  - [2026-09-07 18:45:14.351828+09:00] slot=1845
  - [2026-09-08 17:50:04.828302+09:00] slot=1745
**검산**: True (매칭+로그only=234 vs 헤더234, 매칭+원장only=215 vs 원장215)

# [4] 단발 드롭아웃별 로그 구간 추출
전체 결측 슬롯: 27건
단발 드롭아웃: 8건

### 2026-09-04 1715 결측 (±10분 구간)
- 직전 실행: 2026-09-04 17:10:02.920000+09:00 / 직후 실행: 2026-09-04 17:20:02.210000+09:00
  ==== 2026-09-04 17:05:02.16 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 9 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1705 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '1705', '31130', 'GGB222001318') outcome=ok_with_items items=25
  
  [sweep] pending_retry=0
  
  [budget] slot=1705 count=10/5000 (approved=10000) status=OK
  ==== 2026-09-04 17:10:02.92 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 10 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1710 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '1710', '31130', 'GGB222001318') outcome=ok_with_items items=25
  
  [sweep] pending_retry=0
  
  [budget] slot=1710 count=11/5000 (approved=10000) status=OK
  ==== 2026-09-04 17:15:02.22 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 11 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1715 stops=1 dry_run=False
  ==== 2026-09-04 17:20:02.21 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 11 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1720 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '1720', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1720 count=12/5000 (approved=10000) status=OK

### 2026-09-04 1755 결측 (±10분 구간)
- 직전 실행: 2026-09-04 17:50:03.050000+09:00 / 직후 실행: 2026-09-04 18:00:02.150000+09:00
  ==== 2026-09-04 17:45:02.44 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 16 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1745 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '1745', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1745 count=17/5000 (approved=10000) status=OK
  ==== 2026-09-04 17:50:03.05 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 17 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1750 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '1750', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1750 count=18/5000 (approved=10000) status=OK
  ==== 2026-09-04 17:55:02.32 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 18 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1755 stops=1 dry_run=False
  ==== 2026-09-04 18:00:02.15 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 18 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=1800 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '1800', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1800 count=19/5000 (approved=10000) status=OK

### 2026-09-07 0740 결측 (±10분 구간)
- 직전 실행: 2026-09-07 07:35:01.910000+09:00 / 직후 실행: 2026-09-07 07:45:01.820000+09:00
  ==== 2026-09-07  7:30:02.01 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 6 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0730 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0730', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0730 count=7/5000 (approved=10000) status=OK
  ==== 2026-09-07  7:35:01.91 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 7 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0735 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0735', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0735 count=8/5000 (approved=10000) status=OK
  ==== 2026-09-07  7:40:02.31 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 8 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0740 stops=1 dry_run=False
  ==== 2026-09-07  7:45:01.82 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 8 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0745 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0745', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0745 count=9/5000 (approved=10000) status=OK

### 2026-09-07 0800 결측 (±10분 구간)
- 직전 실행: 2026-09-07 07:55:01.990000+09:00 / 직후 실행: 2026-09-07 08:05:01.900000+09:00
  ==== 2026-09-07  7:50:01.90 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 9 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0750 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0750', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0750 count=10/5000 (approved=10000) status=OK
  ==== 2026-09-07  7:55:01.99 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 10 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0755 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0755', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0755 count=11/5000 (approved=10000) status=OK
  ==== 2026-09-07  8:00:01.96 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 11 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0800 stops=1 dry_run=False
  ==== 2026-09-07  8:05:01.90 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 11 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0805 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0805', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0805 count=12/5000 (approved=10000) status=OK

### 2026-09-07 0855 결측 (±10분 구간)
- 직전 실행: 2026-09-07 08:50:02.190000+09:00 / 직후 실행: 2026-09-07 17:00:03.090000+09:00
  ==== 2026-09-07  8:45:02.34 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 19 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0845 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0845', '31130', 'GGB222001318') outcome=ok_with_items items=25
  
  [sweep] pending_retry=0
  
  [budget] slot=0845 count=20/5000 (approved=10000) status=OK
  ==== 2026-09-07  8:50:02.19 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 20 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0850 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '0850', '31130', 'GGB222001318') outcome=ok_with_items items=25
  
  [sweep] pending_retry=0
  
  [budget] slot=0850 count=21/5000 (approved=10000) status=OK
  ==== 2026-09-07  8:55:02.11 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 21 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=0855 stops=1 dry_run=False
  ==== 2026-09-07  9:00:02.42 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 21 attempts today (obs_date=2026-09-07)
  [INFO] ���� �ð�(2026-09-07T09:00:03.205100+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### 2026-09-07 1755 결측 (±10분 구간)
- 직전 실행: 2026-09-07 17:50:02.740000+09:00 / 직후 실행: 2026-09-07 18:00:02.280000+09:00
  ==== 2026-09-07 17:45:02.27 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 30 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1745 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '1745', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1745 count=31/5000 (approved=10000) status=OK
  ==== 2026-09-07 17:50:02.74 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 31 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1750 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '1750', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1750 count=32/5000 (approved=10000) status=OK
  ==== 2026-09-07 17:55:02.78 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 32 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1755 stops=1 dry_run=False
  ==== 2026-09-07 18:00:02.28 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 32 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1800 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '1800', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1800 count=33/5000 (approved=10000) status=OK

### 2026-09-10 0750 결측 (±10분 구간)
- 직전 실행: 2026-09-10 07:45:01.290000+09:00 / 직후 실행: 2026-09-10 07:55:01.300000+09:00
  ==== 2026-09-10  7:40:01.65 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 5 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=0740 stops=1 dry_run=False
  [CALLED] key=('2026-09-10', '0740', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0740 count=6/5000 (approved=10000) status=OK
  ==== 2026-09-10  7:45:01.29 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 6 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=0745 stops=1 dry_run=False
  [CALLED] key=('2026-09-10', '0745', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0745 count=7/5000 (approved=10000) status=OK
  ==== 2026-09-10  7:50:01.34 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 7 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=0750 stops=1 dry_run=False
  ==== 2026-09-10  7:55:01.30 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 7 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=0755 stops=1 dry_run=False
  [CALLED] key=('2026-09-10', '0755', '31130', 'GGB222001318') outcome=ok_with_items items=26
  
  [sweep] pending_retry=0
  
  [budget] slot=0755 count=8/5000 (approved=10000) status=OK

### 2026-09-10 1815 결측 (±10분 구간)
- 직전 실행: 2026-09-10 18:10:01.780000+09:00 / 직후 실행: 2026-09-10 18:20:01.880000+09:00
  ==== 2026-09-10 18:05:01.78 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 33 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=1805 stops=1 dry_run=False
  [CALLED] key=('2026-09-10', '1805', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1805 count=34/5000 (approved=10000) status=OK
  ==== 2026-09-10 18:10:01.78 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 34 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=1810 stops=1 dry_run=False
  [CALLED] key=('2026-09-10', '1810', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1810 count=35/5000 (approved=10000) status=OK
  ==== 2026-09-10 18:15:01.70 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 262, in run_collection
  outcome, res_code, res_msg, it_count, _ = parse_response(text, status_code)
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 86, in parse_response
  items_container = body.get("items", {})
  ^^^^^^^^
  AttributeError: 'str' object has no attribute 'get'
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 35 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=1815 stops=1 dry_run=False
  ==== 2026-09-10 18:20:01.88 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 35 attempts today (obs_date=2026-09-10)
  
  [START] obs_date=2026-09-10 slot_hhmm=1820 stops=1 dry_run=False
  [CALLED] key=('2026-09-10', '1820', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1820 count=36/5000 (approved=10000) status=OK

# [5] 원인 후보 판별
- 슬롯 실행 간격: min=18.3s, p50=300.0s, p90=300.6s, max=404.1s
- 300초(슬롯 간격) 근접 여부: max가 300에 얼마나 가까운지 확인 -> 404.1초

| date | slot | 원인 후보 | 증거 |
|---|---|---|---|
| 2026-09-04 | 1715 | 프로세스 실패 (유력) | 로그 내 에러 발견 |
| 2026-09-04 | 1755 | 프로세스 실패 (유력) | 로그 내 에러 발견 |
| 2026-09-07 | 0740 | 프로세스 실패 (유력) | 로그 내 에러 발견 |
| 2026-09-07 | 0800 | 프로세스 실패 (유력) | 로그 내 에러 발견 |
| 2026-09-07 | 0855 | 프로세스 실패 (유력) | 로그 내 에러 발견 |
| 2026-09-07 | 1755 | 프로세스 실패 (유력) | 로그 내 에러 발견 |
| 2026-09-10 | 0750 | 프로세스 실패 (유력) | 로그 내 에러 발견 |
| 2026-09-10 | 1815 | 프로세스 실패 (유력) | 로그 내 에러 발견 |

# [6] 재발 여부 및 확장 영향
- 09-10 결측 패턴: 09-04/07과 동일 단발(0750) 등 발견 → **재발 진행 중**
- 09-10 PM 수집분 원장 기록: 23건 (오후 커버리지 95.8%)
- **판정**: 09-10 PM 정상 수집 확인 → 분석 창은 09-07~09-10 **4일**이다.
- 정류소 확장 한계 (선형 가정, p90=7.266초): 300초 / 7.266초 = 41개 정류소
- 결론: 확장 가능 (안전 한도 초과 위험 낮음)