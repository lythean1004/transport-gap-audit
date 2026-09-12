"""HTTP attempt counter and budget guard for 7D arrival collection."""

DAILY_APPROVED = 10000  # getSttnAcctoArvlPrearngeInfoList 승인 트래픽
WARN_AT = 4000
HARD_STOP = 5000


class BudgetGuard:
    """HTTP 요청 시도를 계측하고 일일 한도 초과를 방어하는 순수 카운터."""

    def __init__(self, warn_at: int = WARN_AT, hard_stop: int = HARD_STOP):
        self.warn_at = warn_at
        self.hard_stop = hard_stop
        self.count = 0
        self.warned = False

    def record_attempt(self) -> int:
        """호출 1건마다 count를 1 증가시키고 현재 count를 반환한다 (재시도 포함 전수 계측)."""
        self.count += 1
        return self.count

    def check(self) -> str:
        """현재 계측치에 따른 예산 상태 판정 ("STOP", "WARN", "OK")."""
        if self.count >= self.hard_stop:
            return "STOP"
        if self.count >= self.warn_at:
            return "WARN"
        return "OK"

    def should_stop(self) -> bool:
        """하드 스탑 임계치 도달 여부."""
        return self.check() == "STOP"

    def slot_log(self, slot_hhmm: str) -> str:
        """슬롯마다 기록할 한 줄 예산 로그 문자열을 생성한다."""
        st = self.check()
        msg = f"[budget] slot={slot_hhmm} count={self.count}/{self.hard_stop} (approved={DAILY_APPROVED}) status={st}"
        if st == "WARN":
            if not self.warned:
                self.warned = True
                msg += " *** WARN ***"
        return msg


def preflight(stops: int, slots_per_day: int = 48, days: int = 3, hard_stop: int = HARD_STOP) -> dict:
    """
    모니터링 시작 전 계획된 총 호출 수 산출 및 일일 하드 스탑 초과 여부를 사전 계산한다.
    """
    calls_per_day = stops * slots_per_day
    total = calls_per_day * days
    allowed = calls_per_day <= hard_stop
    return {
        "stops": stops,
        "slots_per_day": slots_per_day,
        "calls_per_day": calls_per_day,
        "days": days,
        "total": total,
        "allowed": allowed,
    }


def format_preflight(d: dict) -> str:
    """사전 점검 결과를 여러 줄 문자열로 포맷팅한다."""
    lines = [
        f"stops: {d['stops']}",
        f"slots_per_day: {d['slots_per_day']}",
        f"calls_per_day: {d['calls_per_day']}",
        f"total: {d['total']}",
    ]
    if not d.get("allowed", False):
        lines.append("REFUSE: calls_per_day가 한도를 초과합니다. 정류소 수를 줄이세요.")
    return "\n".join(lines)


if __name__ == "__main__":
    # 1) preflight(stops=1)
    p1 = preflight(stops=1)
    print("1. preflight(stops=1):", p1)
    print("--- format_preflight(stops=1) ---")
    print(format_preflight(p1))

    # 2) preflight(stops=104)
    p104 = preflight(stops=104)
    print(f"\n2. preflight(stops=104): calls_per_day={p104['calls_per_day']}, allowed={p104['allowed']}")

    # 3) preflight(stops=105)
    p105 = preflight(stops=105)
    print(f"3. preflight(stops=105): calls_per_day={p105['calls_per_day']}, allowed={p105['allowed']}")

    # 4) BudgetGuard 3999회 호출 -> check() == 'OK'
    bg = BudgetGuard()
    for _ in range(3999):
        bg.record_attempt()
    print(f"\n4. count=3999 check: {bg.check()}")

    # 5) 1회 더 호출(4000) -> check() == 'WARN', slot_log("0700") 출력
    bg.record_attempt()
    print(f"5. count=4000 check: {bg.check()}")
    print("   slot_log('0700'):", bg.slot_log("0700"))

    # 6) 999회 더 호출(4999) -> check() == 'WARN', should_stop() == False
    for _ in range(999):
        bg.record_attempt()
    print(f"6. count=4999 check: {bg.check()}, should_stop: {bg.should_stop()}")

    # 7) 1회 더 호출(5000) -> check() == 'STOP', should_stop() == True
    bg.record_attempt()
    print(f"7. count=5000 check: {bg.check()}, should_stop: {bg.should_stop()}")

    # 8) slot_log("1855") 출력
    print("8. slot_log('1855'):", bg.slot_log("1855"))