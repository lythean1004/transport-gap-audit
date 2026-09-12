"""
K-apt → Pilot 지구 매칭 후보 생성기 (4D)

판정 규칙 (2026-09-02 parkd 확정, unclear 0건):
  CONFIRMED = addr_legal의 법정동 ∈ pilot.legal_dong AND approval_date ∈ window
  REJECTED  = 그 외 전부

  R1: 법정동이 legal_dong_out이거나 어느 legal_dong에도 없음 (원도심/타지구)
  R2: 법정동은 맞지만 승인일이 window 밖
  R3: 법정동이 다른 pilot 지구 소속 (컨플릭트 해소)
  R4: signal_name 단독 매칭 (브랜드명 우연)
"""
import re
import csv
from pathlib import Path
from datetime import datetime
import yaml
import polars as pl


def extract_legal_dongs(addr: str) -> list[str]:
    """주소 문자열에서 법정동/리/읍/면을 추출.
    개선 정규식: 1~4글자+동, 2~4글자+리/읍/면 (송동·목동 등 1글자동 포함)."""
    if not addr:
        return []
    return re.findall(r'([가-힣]{1,4}동|[가-힣]{2,4}(?:리|읍|면))', addr)


def run_matcher():
    # ── 설정 로드 ──
    with open("config/pilots.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    pilots = config["pilots"]
    df = pl.read_parquet("data/staged/kapt_basic.parquet")

    # 파일럿별 룩업 구조 구축
    pilot_ids = []
    p_name = {}
    p_sigungu = {}
    p_dong_in = {}
    p_dong_out = {}
    p_window = {}

    for p in pilots:
        pid = p["development_id"]
        pilot_ids.append(pid)
        p_name[pid] = p["name_ko"]
        p_sigungu[pid] = p["match_hints"].get("sigungu", [])
        p_dong_in[pid] = set(p["match_hints"].get("legal_dong", []))
        p_dong_out[pid] = set(p["match_hints"].get("legal_dong_out", []))
        w = p.get("approval_window", {})
        try:
            p_window[pid] = (
                datetime.strptime(w["start"], "%Y-%m-%d").date(),
                datetime.strptime(w["end"], "%Y-%m-%d").date(),
            )
        except (ValueError, TypeError, KeyError):
            p_window[pid] = None

    # 전체 legal_dong → pilot 역색인 (R3 판별용)
    dong_owner = {}
    for pid in pilot_ids:
        for d in p_dong_in[pid]:
            dong_owner.setdefault(d, []).append(pid)

    # ── 후보 생성 & 판정 ──
    candidates = []
    kapt_to_pilots: dict[str, list[str]] = {}
    orphan_codes: set[str] = set()

    for row in df.iter_rows(named=True):
        code = row.get("kapt_code")
        name = row.get("kapt_name") or ""
        addr_legal = row.get("addr_legal") or ""
        addr_road = row.get("addr_road") or ""
        combined = f"{addr_legal} {addr_road}"

        app_date_str = row.get("approval_date")
        app_date = None
        if app_date_str:
            try:
                app_date = datetime.strptime(app_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        extracted = extract_legal_dongs(addr_legal)
        matched_any = False

        for pid in pilot_ids:
            # ── 전제조건: 시군구 일치 ──
            if not any(sg in combined for sg in p_sigungu[pid]):
                continue

            name_ko = p_name[pid]
            dong_in = p_dong_in[pid]
            dong_out = p_dong_out[pid]
            window = p_window.get(pid)

            # ── 3개 독립 신호 ──
            signal_name = name_ko in name

            # signal_addr: 추출 법정동 ∈ legal_dong (부분문자열이 아닌 정규식 추출값 비교)
            hit_in = None
            for d in extracted:
                if d in dong_in:
                    hit_in = d
                    break
            signal_addr = hit_in is not None

            # signal_period
            signal_period = False
            if app_date and window:
                signal_period = window[0] <= app_date <= window[1]

            score = int(signal_name) + int(signal_addr) + int(signal_period)
            if score == 0:
                orphan_codes.add(code)
                continue

            matched_any = True

            # ── 판정 (CONFIRMED / REJECTED) ──
            hit_out = None
            for d in extracted:
                if d in dong_out:
                    hit_out = d
                    break

            if hit_out:
                # R1/R3: 법정동이 명시적 reject 목록
                others = [p for p in dong_owner.get(hit_out, []) if p != pid]
                if others:
                    status = "rejected"
                    reason = f'법정동 "{hit_out}"은 {",".join(others)} 지구 소속'
                else:
                    status = "rejected"
                    reason = f'법정동 "{hit_out}"은 {name_ko} 지구 밖 (원도심/타지구)'
            elif signal_addr and signal_period:
                status = "confirmed"
                reason = f'법정동 "{hit_in}" ∈ pilot, 승인일 {app_date_str} ∈ window'
            elif signal_addr and not signal_period:
                # R2: 법정동 맞지만 승인일 밖
                status = "rejected"
                if app_date and window:
                    if app_date < window[0]:
                        reason = f'승인일 {app_date_str} < window {window[0]}'
                    else:
                        reason = f'승인일 {app_date_str} > window {window[1]}'
                else:
                    reason = '승인일 확인 불가 (NULL)'
            elif signal_name and not signal_addr and not signal_period:
                # R4: 이름 단독 매칭
                status = "rejected"
                reason = '이름 단독 매칭 - 브랜드명 우연 일치'
            else:
                # 나머지: 법정동 미매칭 (원도심/타지구)
                status = "rejected"
                dong_str = ", ".join(extracted) if extracted else "(추출 불가)"
                reason = f'법정동 "{dong_str}" 미매칭 - 원도심/타지구'

            candidates.append({
                "kapt_code": code,
                "kapt_name": name,
                "addr_legal": addr_legal,
                "addr_road": addr_road,
                "approval_date": app_date_str,
                "approval_date_raw": row.get("approval_date_raw"),
                "household_count": row.get("household_count"),
                "bldg_count": row.get("bldg_count"),
                "pilot_guess": pid,
                "signal_name": signal_name,
                "signal_addr": signal_addr,
                "signal_period": signal_period,
                "signal_score": score,
                "human_match_status": status,
                "human_reviewer": "parkd",
                "human_reviewed_at": "2026-09-02",
                "reject_reason": reason if status == "rejected" else "",
            })

            kapt_to_pilots.setdefault(code, []).append(pid)

    # ── 정렬: pilot_guess → approval_date ASC ──
    candidates.sort(key=lambda c: (c["pilot_guess"], c["approval_date"] or "9999-12-31"))

    # ── 컨플릭트 ──
    conflicts = []
    for code, pids in kapt_to_pilots.items():
        uniq = sorted(set(pids))
        if len(uniq) > 1:
            conflicts.append({"kapt_code": code, "matched_pilots": " | ".join(uniq)})

    # ── 고아 ──
    row_lookup = {}
    for row in df.iter_rows(named=True):
        row_lookup[row["kapt_code"]] = row
    orphans = []
    for code in sorted(orphan_codes):
        if code not in kapt_to_pilots:
            r = row_lookup.get(code, {})
            orphans.append({
                "kapt_code": code,
                "kapt_name": r.get("kapt_name", ""),
                "addr_legal": r.get("addr_legal", ""),
                "addr_road": r.get("addr_road", ""),
            })

    # ── CSV 출력 ──
    export_dir = Path("exports")
    export_dir.mkdir(parents=True, exist_ok=True)

    cand_fields = [
        "kapt_code", "kapt_name", "addr_legal", "addr_road", "approval_date",
        "approval_date_raw", "household_count", "bldg_count",
        "pilot_guess", "signal_name", "signal_addr", "signal_period", "signal_score",
        "human_match_status", "human_reviewer", "human_reviewed_at", "reject_reason",
    ]
    with open(export_dir / "kapt_match_candidates.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cand_fields)
        w.writeheader()
        w.writerows(candidates)

    with open(export_dir / "kapt_match_conflicts.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["kapt_code", "matched_pilots"])
        w.writeheader()
        w.writerows(conflicts)

    with open(export_dir / "kapt_match_orphans.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["kapt_code", "kapt_name", "addr_legal", "addr_road"])
        w.writeheader()
        w.writerows(orphans)

    # ── 집계 ──
    total = len(candidates)
    n_confirmed = sum(1 for c in candidates if c["human_match_status"] == "confirmed")
    n_rejected = sum(1 for c in candidates if c["human_match_status"] == "rejected")

    print(f"총 후보: {total}")
    print(f"CONFIRMED: {n_confirmed}  ({n_confirmed/total*100:.1f}%)")
    print(f"REJECTED:  {n_rejected}  ({n_rejected/total*100:.1f}%)")
    print(f"Conflicts: {len(conflicts)}")
    print(f"Orphans:   {len(orphans)}")
    print()

    # pilot별
    from collections import Counter
    pilot_conf = Counter()
    pilot_rej = Counter()
    for c in candidates:
        if c["human_match_status"] == "confirmed":
            pilot_conf[c["pilot_guess"]] += 1
        else:
            pilot_rej[c["pilot_guess"]] += 1
    for pid in pilot_ids:
        c_n = pilot_conf[pid]
        r_n = pilot_rej[pid]
        print(f"  {pid}: CONFIRMED {c_n} / REJECTED {r_n} / 총계 {c_n+r_n}")


if __name__ == "__main__":
    run_matcher()
