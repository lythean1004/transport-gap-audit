"""Arrival slots management and nominal slot snapping for 7D collection."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Seoul")
WINDOWS = (("07:00", "09:00"), ("17:00", "19:00"))
SLOT_MINUTES = 5


def build_slot_labels() -> tuple[str, ...]:
    """
    각 모니터링 윈도우를 SLOT_MINUTES(5분) 간격으로 분할한 HHMM 슬롯 라벨 튜플을 생성한다.
    윈도우의 종료 시각(09:00, 19:00)은 포함하지 않는다. (07:00~08:55, 17:00~18:55)
    정확히 48개의 라벨이 반환된다.
    """
    labels: list[str] = []
    dummy_date = datetime(2026, 1, 1)

    for start_str, end_str in WINDOWS:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))

        cur_dt = dummy_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end_dt = dummy_date.replace(hour=eh, minute=em, second=0, microsecond=0)

        while cur_dt < end_dt:
            labels.append(f"{cur_dt.hour:02d}{cur_dt.minute:02d}")
            cur_dt += timedelta(minutes=SLOT_MINUTES)

    return tuple(labels)


# 모듈 로딩 시 1회 캐시
_CACHED_LABELS: tuple[str, ...] = build_slot_labels()
_CACHED_LABEL_SET: frozenset[str] = frozenset(_CACHED_LABELS)


def snap_to_slot(dt: datetime) -> str | None:
    """
    tz-aware datetime을 Asia/Seoul로 변환 후, 해당 시각이 속한 명목 슬롯 라벨(HHMM)을 반환한다.
    내림(floor) 방식으로 매핑하며, 윈도우 외 시각이면 None을 반환한다.
    naive datetime 전달 시 ValueError를 발생시킨다.
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("dt must be a timezone-aware datetime.")

    dt_kst = dt.astimezone(TZ)
    floor_minute = (dt_kst.minute // SLOT_MINUTES) * SLOT_MINUTES
    candidate = f"{dt_kst.hour:02d}{floor_minute:02d}"

    if candidate in _CACHED_LABEL_SET:
        return candidate
    return None


if __name__ == "__main__":
    labels = build_slot_labels()
    print(f"len(build_slot_labels()): {len(labels)}")
    print(f"first 3: {labels[:3]}, last 3: {labels[-3:]}")
    print(f"'0900' in labels: {'0900' in labels}, '1900' in labels: {'1900' in labels}")

    test_inputs = [
        datetime.fromisoformat("2026-09-10T07:00:00+09:00"),
        datetime.fromisoformat("2026-09-10T07:03:59+09:00"),
        datetime.fromisoformat("2026-09-10T07:05:00+09:00"),
        datetime.fromisoformat("2026-09-10T08:59:59+09:00"),
        datetime.fromisoformat("2026-09-10T09:00:00+09:00"),
        datetime.fromisoformat("2026-09-10T12:00:00+09:00"),
        datetime.fromisoformat("2026-09-10T17:00:00+09:00"),
        datetime.fromisoformat("2026-09-10T18:59:59+09:00"),
        datetime.fromisoformat("2026-09-10T19:00:00+09:00"),
    ]

    print("--- snap_to_slot results ---")
    for t_in in test_inputs:
        res = snap_to_slot(t_in)
        print(f"{t_in.isoformat()} -> {res}")

    # naive datetime 테스트
    try:
        snap_to_slot(datetime(2026, 9, 10, 7, 3, 59))
        print("naive test: NO_ERROR")
    except ValueError:
        print("naive test: ValueError OK")

    # round-trip 테스트
    mismatch_count = 0
    ref_date = datetime(2026, 9, 10, tzinfo=TZ)
    for lbl in labels:
        h = int(lbl[:2])
        m = int(lbl[2:])
        slot_dt = ref_date.replace(hour=h, minute=m, second=0, microsecond=0)
        snapped = snap_to_slot(slot_dt)
        if snapped != lbl:
            mismatch_count += 1
    print(f"round-trip mismatch count: {mismatch_count}")