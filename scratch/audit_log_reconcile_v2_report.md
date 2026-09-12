# [1] 미이행분 출력 (P2 보완)

## 단발 드롭아웃 8건 로그 전문 (±10분)

### 2026-09-04 1715 결측
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

### 2026-09-04 1755 결측
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

### 2026-09-07 0740 결측
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

### 2026-09-07 0800 결측
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

### 2026-09-07 0855 결측
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

### 2026-09-07 1755 결측
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

### 2026-09-10 0750 결측
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

### 2026-09-10 1815 결측
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

## (b) 로그전용 21건 본문 전문
- 분류 집계: {'정상': 2, '판별불가': 11, '슬롯 실패': 8}

### [2026-09-04 08:21:11.110000+09:00] (정상)
  ==== 2026-09-04  8:21:11.11 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 0 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=0820 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '0820', '31130', 'GGB222001318') outcome=ok_with_items items=25
  
  [sweep] pending_retry=0
  
  [budget] slot=0820 count=1/5000 (approved=10000) status=OK

### [2026-09-04 08:23:43.230000+09:00] (판별불가)
  ==== 2026-09-04  8:23:43.23 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 1 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=0820 stops=1 dry_run=False
  [SKIP] key=('2026-09-04', '0820', '31130', 'GGB222001318') reason=DONE
  
  [sweep] pending_retry=0
  
  [budget] slot=0820 count=1/5000 (approved=10000) status=OK

### [2026-09-04 08:25:01.800000+09:00] (정상)
  ==== 2026-09-04  8:25:01.80 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 1 attempts today (obs_date=2026-09-04)
  
  [START] obs_date=2026-09-04 slot_hhmm=0825 stops=1 dry_run=False
  [CALLED] key=('2026-09-04', '0825', '31130', 'GGB222001318') outcome=ok_with_items items=25
  
  [sweep] pending_retry=0
  
  [budget] slot=0825 count=2/5000 (approved=10000) status=OK

### [2026-09-04 09:00:05.830000+09:00] (판별불가)
  ==== 2026-09-04  9:00:05.83 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 8 attempts today (obs_date=2026-09-04)
  [INFO] ���� �ð�(2026-09-04T09:00:12.306815+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-04 17:15:02.220000+09:00] (슬롯 실패)
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

### [2026-09-04 17:55:02.320000+09:00] (슬롯 실패)
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

### [2026-09-04 19:00:34.070000+09:00] (판별불가)
  ==== 2026-09-04 19:00:34.07 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 30 attempts today (obs_date=2026-09-04)
  [INFO] ���� �ð�(2026-09-04T19:01:02.084018+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-07 07:40:02.310000+09:00] (슬롯 실패)
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

### [2026-09-07 08:00:01.960000+09:00] (슬롯 실패)
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

### [2026-09-07 08:55:02.110000+09:00] (슬롯 실패)
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

### [2026-09-07 09:00:02.420000+09:00] (판별불가)
  ==== 2026-09-07  9:00:02.42 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 21 attempts today (obs_date=2026-09-07)
  [INFO] ���� �ð�(2026-09-07T09:00:03.205100+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-07 17:55:02.780000+09:00] (슬롯 실패)
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

### [2026-09-07 19:00:02.220000+09:00] (판별불가)
  ==== 2026-09-07 19:00:02.22 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 45 attempts today (obs_date=2026-09-07)
  [INFO] ���� �ð�(2026-09-07T19:00:03.013113+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-08 09:00:02.090000+09:00] (판별불가)
  ==== 2026-09-08  9:00:02.09 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 24 attempts today (obs_date=2026-09-08)
  [INFO] ���� �ð�(2026-09-08T09:00:02.887492+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-08 19:00:02.660000+09:00] (판별불가)
  ==== 2026-09-08 19:00:02.66 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 49 attempts today (obs_date=2026-09-08)
  [INFO] ���� �ð�(2026-09-08T19:00:03.665805+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-09 09:00:01.970000+09:00] (판별불가)
  ==== 2026-09-09  9:00:01.97 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 24 attempts today (obs_date=2026-09-09)
  [INFO] ���� �ð�(2026-09-09T09:00:03.589057+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-09 19:00:02.130000+09:00] (판별불가)
  ==== 2026-09-09 19:00:02.13 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 48 attempts today (obs_date=2026-09-09)
  [INFO] ���� �ð�(2026-09-09T19:00:03.045576+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-10 07:50:01.340000+09:00] (슬롯 실패)
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

### [2026-09-10 09:00:01.470000+09:00] (판별불가)
  ==== 2026-09-10  9:00:01.47 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 20 attempts today (obs_date=2026-09-10)
  [INFO] ���� �ð�(2026-09-10T09:00:02.075285+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

### [2026-09-10 18:15:01.700000+09:00] (슬롯 실패)
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

### [2026-09-10 19:00:01.570000+09:00] (판별불가)
  ==== 2026-09-10 19:00:01.57 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 43 attempts today (obs_date=2026-09-10)
  [INFO] ���� �ð�(2026-09-10T19:00:02.681766+09:00)�� ���� â ���Դϴ�. ���� �����մϴ�.

## (c) 원장전용 2건 원장 행 및 인접 로그

### 원장 행: {'obs_date': '2026-09-07', 'slot_hhmm': '1845', 'citycode': '31130', 'nodeid': 'GGB222001318', 'outcome': 'ok_with_items', 'retry_count': '1', 'called_at_kst': '2026-09-07T18:45:14.351828+09:00', 'http_status': '200', 'result_code': '00', 'result_msg': 'NORMAL SERVICE.', 'item_count': '24', 'raw_path': 'evidence/arrival_raw/2026-09-07/31130_GGB222001318_1845.json', 'schema_version': 'v1'}
- 인접 로그 (±10분):
  ==== 2026-09-07 18:40:02.77 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 40 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1840 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '1840', '31130', 'GGB222001318') outcome=ok_with_items items=25
  
  [sweep] pending_retry=0
  
  [budget] slot=1840 count=41/5000 (approved=10000) status=OK
  ==== 2026-09-07 18:45:02.50 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 41 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1845 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '1845', '31130', 'GGB222001318') outcome=api_error items=0
  
  [sweep] pending_retry=1
  [SWEEP CALLED] key=('2026-09-07', '1845', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [budget] slot=1845 count=43/5000 (approved=10000) status=OK
  ==== 2026-09-07 18:50:02.17 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 43 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1850 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '1850', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1850 count=44/5000 (approved=10000) status=OK
  ==== 2026-09-07 18:55:02.54 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 44 attempts today (obs_date=2026-09-07)
  
  [START] obs_date=2026-09-07 slot_hhmm=1855 stops=1 dry_run=False
  [CALLED] key=('2026-09-07', '1855', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1855 count=45/5000 (approved=10000) status=OK

### 원장 행: {'obs_date': '2026-09-08', 'slot_hhmm': '1745', 'citycode': '31130', 'nodeid': 'GGB222001318', 'outcome': 'ok_with_items', 'retry_count': '1', 'called_at_kst': '2026-09-08T17:50:04.828302+09:00', 'http_status': '200', 'result_code': '00', 'result_msg': 'NORMAL SERVICE.', 'item_count': '24', 'raw_path': 'evidence/arrival_raw/2026-09-08/31130_GGB222001318_1745.json', 'schema_version': 'v1'}
- 인접 로그 (±10분):
  ==== 2026-09-08 17:45:03.36 ====
  Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "src\collectors\arrival_snapshot.py", line 421, in <module>
  main()
  File "src\collectors\arrival_snapshot.py", line 408, in main
  exit_code = run_collection(
  ^^^^^^^^^^^^^^^
  File "src\collectors\arrival_snapshot.py", line 366, in run_collection
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
  [budget] restored from ledger: 33 attempts today (obs_date=2026-09-08)
  
  [START] obs_date=2026-09-08 slot_hhmm=1745 stops=1 dry_run=False
  [CALLED] key=('2026-09-08', '1745', '31130', 'GGB222001318') outcome=api_error items=0
  
  [sweep] pending_retry=1
  ==== 2026-09-08 17:50:02.43 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 34 attempts today (obs_date=2026-09-08)
  
  [START] obs_date=2026-09-08 slot_hhmm=1750 stops=1 dry_run=False
  [CALLED] key=('2026-09-08', '1750', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=1
  [SWEEP CALLED] key=('2026-09-08', '1745', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [budget] slot=1750 count=36/5000 (approved=10000) status=OK
  ==== 2026-09-08 17:55:03.43 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 36 attempts today (obs_date=2026-09-08)
  
  [START] obs_date=2026-09-08 slot_hhmm=1755 stops=1 dry_run=False
  [CALLED] key=('2026-09-08', '1755', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1755 count=37/5000 (approved=10000) status=OK
  ==== 2026-09-08 18:00:02.77 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
  calls_per_day: 48
  total: 144
  [budget] restored from ledger: 37 attempts today (obs_date=2026-09-08)
  
  [START] obs_date=2026-09-08 slot_hhmm=1800 stops=1 dry_run=False
  [CALLED] key=('2026-09-08', '1800', '31130', 'GGB222001318') outcome=ok_with_items items=24
  
  [sweep] pending_retry=0
  
  [budget] slot=1800 count=38/5000 (approved=10000) status=OK

# [2] 정보성 결측 검증

## 단발 결측 8건 직전/직후 item_count
| date | slot | prev_slot | prev_items | next_slot | next_items |
|---|---|---|---|---|---|
| 2026-09-04 | 1715 | 1710 | 25 | 1720 | 24 |
| 2026-09-04 | 1755 | 1750 | 24 | 1800 | 24 |
| 2026-09-07 | 0740 | 0735 | 26 | 0745 | 26 |
| 2026-09-07 | 0800 | 0755 | 26 | 0805 | 26 |
| 2026-09-07 | 0855 | 0850 | 25 | 1700 | 25 |
| 2026-09-07 | 1755 | 1750 | 24 | 1800 | 24 |
| 2026-09-10 | 0750 | 0745 | 26 | 0755 | 26 |
| 2026-09-10 | 1815 | 1810 | 24 | 1820 | 24 |

## ok_empty 발생 건 직전/직후 item_count
| date | slot | prev_slot | prev_items | next_slot | next_items |
|---|---|---|---|---|---|
| 2026-09-04 | 1735 | 1730 | 24 | 1740 | 24 |
| 2026-09-09 | 1805 | 1800 | 24 | 1810 | 24 |
| 2026-09-10 | 1715 | 1710 | 25 | 1720 | 25 |
| 2026-09-10 | 1755 | 1750 | 24 | 1800 | 24 |

## item_count 분포 비교
- 전체 성공 슬롯: mean=25.0, median=25.0 (n=209)
- 결측 인접 슬롯: mean=24.9, median=25.0 (n=16)
- ok_empty 인접: mean=24.2, median=24.0 (n=8)

## 발생 시간대 히스토그램 (결측 + ok_empty)
- 07시: ** (2건)
- 08시: ** (2건)
- 17시: ****** (6건)
- 18시: ** (2건)

**결론**: 무작위 결측 유력 또는 판별불가

# [3] 슬롯 실행 소요시간 실측
- 측정불가 (elapsed_ms 컬럼 없음)

## 헤더 간격 min (18.3초) 사례
[2026-09-04 08:20:52.830000+09:00] ==== 2026-09-04  8:20:52.83 ====
  '"__PY__"'��(��) ���� �Ǵ� �ܺ� ����, ������ �� �ִ� ���α׷�, �Ǵ�
  ��ġ ������ �ƴմϴ�.
...
[2026-09-04 08:21:11.110000+09:00] ==== 2026-09-04  8:21:11.11 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
...

## 헤더 간격 max (404.1초) 사례
[2026-09-04 08:30:03.430000+09:00] ==== 2026-09-04  8:30:03.43 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
...
[2026-09-04 08:36:47.500000+09:00] ==== 2026-09-04  8:36:47.50 ====
  === PREFLIGHT CHECK ===
  stops: 1
  slots_per_day: 48
...

# [4] 커버리지 재산출
| date | 고유 슬롯 수 | 고유/48 | 실효 슬롯 | 실효/48 | >=90% 충족 |
|---|---|---|---|---|---|
| 2026-09-04 | 30 | 62.5% | 30 | 62.5% | 미충족 |
| 2026-09-07 | 44 | 91.7% | 44 | 91.7% | 충족 |
| 2026-09-08 | 48 | 100.0% | 47 | 97.9% | 충족 |
| 2026-09-09 | 48 | 100.0% | 48 | 100.0% | 충족 |
| 2026-09-10 | 43 | 89.6% | 43 | 89.6% | 미충족 |

### 사람이 결정할 사항
1. 결측 원인이 API 응답값 파싱(AttributeError)으로 확인된 바, 이를 0 또는 빈 배열로 정상 처리하도록 코드 보완할지 여부
2. 정보성 결측 분석 결과에 따라, 0건 응답이 실질적 '운행 없음(ok_empty)'으로 간주되는 경우 과거 결측된 슬롯들을 0으로 임퓨테이션할지 여부