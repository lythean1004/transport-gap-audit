from scripts.submission.windows_v02 import window_label, timestamp_offset


def test_peak_windows_exclude_endpoints():
    assert window_label('0700')=='AM'
    assert window_label('0855')=='AM'
    assert window_label('0900')=='outside'
    assert window_label('1700')=='PM'
    assert window_label('1900')=='outside'


def test_retry_timestamp_is_not_rewritten_as_nominal_slot():
    row={'obs_date':'2026-09-08','slot_hhmm':'1745','called_at_kst':'2026-09-08T17:50:04+09:00'}
    assert timestamp_offset(row)==304


def test_sweep_calls_are_included_in_log_reconciliation():
    from scripts.submission.windows_v02 import parse_call_log
    text="[CALLED] key=('2026-09-11', '1700', '31130', 'N') outcome=api_error items=0\n[SWEEP CALLED] key=('2026-09-11', '1700', '31130', 'N') outcome=ok_empty items=0"
    assert len(parse_call_log(text))==2
