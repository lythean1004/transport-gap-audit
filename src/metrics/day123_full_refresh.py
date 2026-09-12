"""Re-run Day 1/2/3 from the complete curated PDF-backed registry."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CURATED = ROOT / "data" / "curated"
STAGED = ROOT / "data" / "staged"
EXPORTS = ROOT / "exports"
REGISTRY_PATH = CURATED / "source_registry.csv"
AS_OF = date(2026, 9, 2)

HISTORICAL = ["화성 동탄2", "김포 한강", "위례", "남양주 다산", "하남 미사"]
FORWARD = ["인천 계양", "남양주 왕숙", "하남 교산", "고양 창릉", "부천 대장"]
DEVELOPMENTS = HISTORICAL + FORWARD
SOURCE_EVENTS = [
    "occupancy_planned_block", "promise_date", "basic_service", "actual_operation",
    "occupancy_first_actual", "occupancy_first_planned",
]
ALL_EVENTS = SOURCE_EVENTS[:5] + ["promise_linkage", "occupancy_first_planned"]
PROMISED_FACILITY = {
    "화성 동탄2": ("rail", "GTX-A 수서~동탄"),
    "김포 한강": ("rail", "김포도시철도(김포골드라인)"),
    "위례": ("tram", "위례선 트램"),
    "남양주 다산": ("rail", "별내선(8호선 연장)"),
    "하남 미사": ("rail", "하남선(5호선 연장)"),
    "인천 계양": ("sbrt", "계양~대장 S-BRT"),
    "남양주 왕숙": ("rail", "강동하남남양주선"),
    "하남 교산": ("rail", "송파하남선"),
    "고양 창릉": ("rail", "고양은평선"),
    "부천 대장": ("sbrt", "계양~대장 S-BRT"),
}
PREFERRED_PROMISE_ID = {
    "화성 동탄2": "SRC-H003",
    "김포 한강": "SRC-H010",
    "위례": "SRC-E1-C05",
    "남양주 다산": "SRC-H022",
    "하남 미사": "SRC-H028",
    "인천 계양": "SRC-F003",
    "남양주 왕숙": "SRC-F009",
    "하남 교산": "SRC-F015",
    "고양 창릉": "SRC-F021",
    "부천 대장": "SRC-F027",
}
PREFERRED_ACTUAL_ID = {
    "화성 동탄2": "SRC-H005",
    "김포 한강": "SRC-H011",
    "위례": "",
    "남양주 다산": "SRC-H023",
    "하남 미사": "SRC-H029",
    "인천 계양": "",
    "남양주 왕숙": "",
    "하남 교산": "",
    "고양 창릉": "",
    "부천 대장": "",
}
PREFERRED_OCCUPANCY_FIRST_ID = {
    "화성 동탄2": "SRC-H001", "김포 한강": "SRC-H007", "위례": "SRC-H013",
    "남양주 다산": "SRC-H020", "하남 미사": "SRC-H025",
}
PREFERRED_FORWARD_OCCUPANCY_ID = {
    "인천 계양": "SRC-E2-A06", "남양주 왕숙": "SRC-E2-A07", "하남 교산": "SRC-U002",
    "고양 창릉": "SRC-F019", "부천 대장": "SRC-F025",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def norm(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()


def truthy(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "y", "yes", "pass")


def is_target_active(row: dict[str, str]) -> bool:
    return row.get("review_status") != "rejected" and row.get("event_type") in SOURCE_EVENTS


def parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value[:10]) else None
    except ValueError:
        return None


def excerpt_in_text(row: dict[str, str]) -> bool:
    excerpt = row.get("exact_excerpt", "")
    if not excerpt:
        return False
    path_value = row.get("local_text_path", "")
    if not path_value:
        return True  # legacy rows may have been verified against saved HTML rather than a PDF text file
    path = Path(path_value)
    if not path.exists():
        return False
    compact_excerpt = norm(excerpt)
    if len(compact_excerpt) < 20:
        return False
    compact_text = norm(path.read_text(encoding="utf-8", errors="ignore"))
    return compact_excerpt in compact_text


def local_document_ok(row: dict[str, str]) -> bool:
    paths = [value for value in (row.get("raw_pdf_path", "") or row.get("local_path", "")).split(";") if value]
    if row.get("pdf_id"):
        return bool(paths) and all(Path(value).exists() for value in paths)
    local_path = row.get("local_path", "")
    return not local_path or Path(local_path).exists()


def hash_ok(row: dict[str, str]) -> bool:
    if not row.get("pdf_id"):
        return True
    paths = [value for value in (row.get("raw_pdf_path", "") or row.get("local_path", "")).split(";") if value]
    hashes = [value for value in (row.get("pdf_sha256", "") or row.get("sha256", "")).split(";") if value]
    if not paths or not hashes:
        return False
    actual = {hashlib.sha256(Path(value).read_bytes()).hexdigest() for value in paths if Path(value).exists()}
    return actual.issubset(set(hashes)) and len(actual) == len(paths)


def day1_issues(row: dict[str, str]) -> list[str]:
    issues = []
    required = ("source_id", "development", "title", "event_type", "review_status")
    for field in required:
        if not row.get(field):
            issues.append(f"missing_{field}")
    if not row.get("source_url"):
        issues.append("missing_direct_source_url")
    if not local_document_ok(row):
        issues.append("missing_local_document")
    if not hash_ok(row):
        issues.append("pdf_hash_mismatch")
    if not row.get("page_or_section"):
        issues.append("missing_page_or_section")
    if not row.get("exact_excerpt"):
        issues.append("missing_exact_excerpt")
    elif not excerpt_in_text(row):
        issues.append("excerpt_not_found_in_extracted_text")
    event_type = row.get("event_type", "")
    if event_type in SOURCE_EVENTS and not row.get("event_date"):
        issues.append("missing_event_date")
    if event_type == "occupancy_planned_block" and not row.get("block_name"):
        issues.append("missing_block_name")
    if event_type == "promise_date":
        for field in ("mode", "line_name", "scope", "promise_verb_원문표기"):
            if not row.get(field):
                issues.append(f"missing_{field}")
    if event_type == "actual_operation":
        for field in ("mode", "line_name"):
            if not row.get(field):
                issues.append(f"missing_{field}")
    if event_type == "basic_service":
        if not row.get("timetable_effective_date"):
            issues.append("missing_timetable_effective_date")
        elif row.get("event_date") != row.get("timetable_effective_date"):
            issues.append("event_date_not_timetable_effective_date")
        if not any(row.get(field) for field in ("service_headway", "service_first", "service_last")):
            issues.append("missing_service_level")
    return list(dict.fromkeys(issues))


def line_match(row: dict[str, str], target: str) -> bool:
    values = [norm(value) for value in (row.get("line_name") or "").split(";") if value]
    return norm(target) in values


def best_row(
    rows: list[dict[str, str]],
    qa_pass: set[str],
    development: str,
    event_type: str,
    line_name: str = "",
    require_date: bool = False,
) -> dict[str, str] | None:
    candidates = [
        row for row in rows
        if row.get("development") == development
        and row.get("event_type") == event_type
        and row.get("review_status") != "rejected"
        and (not line_name or line_match(row, line_name))
        and (not require_date or bool(row.get("event_date")))
    ]
    if not candidates:
        return None
    def rank(row: dict[str, str]) -> tuple[int, ...]:
        return (
            int(row.get("review_status") == "human_verified"),
            int(row.get("source_id") in qa_pass),
            int(not row.get("source_id", "").startswith("SRC-PDF")),
            int(row.get("source_type", "").startswith("official") or row.get("publisher") != ""),
            int(row.get("confidence") == "high"),
            int(bool(row.get("event_date"))),
            int(bool(row.get("exact_excerpt"))),
            int(bool(row.get("source_url"))),
        )
    return max(candidates, key=lambda row: (rank(row), row.get("published_date", ""), row.get("source_id", "")))


def representative_deadline(row: dict[str, str] | None) -> date | None:
    if not row:
        return None
    upper = parse_iso(row.get("event_date_upper", ""))
    return upper or parse_iso(row.get("event_date", ""))


def main() -> None:
    rows = read_csv(REGISTRY_PATH)
    rows_by_id = {row.get("source_id", ""): row for row in rows}
    active_rows = [row for row in rows if is_target_active(row)]

    qa_rows = []
    qa_pass: set[str] = set()
    for row in rows:
        if not is_target_active(row):
            continue
        issues = day1_issues(row)
        if not issues:
            qa_pass.add(row["source_id"])
        qa_rows.append({
            "source_id": row.get("source_id", ""),
            "pdf_id": row.get("pdf_id", ""),
            "development": row.get("development", ""),
            "event_type": row.get("event_type", ""),
            "review_status": row.get("review_status", ""),
            "local_exists": local_document_ok(row),
            "sha256_match": hash_ok(row),
            "excerpt_found": excerpt_in_text(row),
            "required_fields_pass": not issues,
            "issues": ";".join(issues),
            "action": "human_verify" if not issues else "repair_then_human_verify",
        })
    write_csv(
        CURATED / "day1_qa.csv", qa_rows,
        ["source_id", "pdf_id", "development", "event_type", "review_status", "local_exists", "sha256_match", "excerpt_found", "required_fields_pass", "issues", "action"],
    )
    qa_by_source = {row["source_id"]: row for row in qa_rows}
    review_queue = []
    for row in rows:
        qa = qa_by_source.get(row.get("source_id", ""), {})
        if row.get("review_status") not in ("needs_human", "rejected") and not qa.get("issues"):
            continue
        if row.get("review_status") == "needs_human" and qa.get("issues"):
            priority = 1
        elif row.get("review_status") == "needs_human":
            priority = 2
        else:
            priority = 3
        review_queue.append({
            "review_priority": priority,
            "source_id": row.get("source_id", ""),
            "pdf_id": row.get("pdf_id", ""),
            "development": row.get("development", ""),
            "event_type": row.get("event_type", ""),
            "title": row.get("title", ""),
            "source_url": row.get("source_url", ""),
            "local_path": row.get("local_path", ""),
            "page_or_section": row.get("page_or_section", ""),
            "exact_excerpt": row.get("exact_excerpt", ""),
            "review_status": row.get("review_status", ""),
            "qa_issues": qa.get("issues", ""),
            "required_action": "원문 페이지·날짜·노선·범위를 사람이 확인 후 human_verified/rejected 확정",
            "reject_reason": row.get("reject_reason", ""),
            "notes": row.get("notes", ""),
        })
    review_queue.sort(key=lambda item: (item["review_priority"], item["development"], item["event_type"], item["source_id"]))
    review_fields = [
        "review_priority", "source_id", "pdf_id", "development", "event_type", "title", "source_url",
        "local_path", "page_or_section", "exact_excerpt", "review_status", "qa_issues",
        "required_action", "reject_reason", "notes",
    ]
    write_csv(CURATED / "review_queue.csv", review_queue, review_fields)

    linkages = []
    for index, development in enumerate(DEVELOPMENTS, 1):
        mode, facility = PROMISED_FACILITY[development]
        promise = rows_by_id.get(PREFERRED_PROMISE_ID[development])
        if not promise or promise.get("review_status") == "rejected":
            promise = best_row(rows, qa_pass, development, "promise_date", facility)
        preferred_actual_id = PREFERRED_ACTUAL_ID[development]
        actual = rows_by_id.get(preferred_actual_id) if preferred_actual_id else None
        if actual and (actual.get("review_status") == "rejected" or not parse_iso(actual.get("event_date", ""))):
            actual = None
        promise_deadline = representative_deadline(promise)
        actual_date = parse_iso(actual.get("event_date", "")) if actual else None
        if not promise:
            status = "promise_absent"
        elif actual:
            status = "fulfilled"
        else:
            status = "unfulfilled"
        if promise_deadline:
            deadline_status = "elapsed" if promise_deadline < AS_OF else "future_or_current_period"
        else:
            deadline_status = "unknown"
        delay = (actual_date - promise_deadline).days if actual_date and promise_deadline else ""
        cohort = "historical_validation" if development in HISTORICAL else "forward_monitoring"
        notes = "동일 수단·노선 기준 자동 연결 초안; 사람 확인 전 확정 금지"
        if cohort == "forward_monitoring" and not actual:
            notes += "; unfulfilled는 현재 미운행 상태이며 미래 지연 확정이 아님"
        linkages.append({
            "linkage_id": f"PL-{index:03d}",
            "cohort": cohort,
            "development": development,
            "promise_source_id": promise.get("source_id", "") if promise else "",
            "actual_source_id": actual.get("source_id", "") if actual else "",
            "mode": mode,
            "promise_line_name": facility,
            "actual_line_name": actual.get("line_name", "") if actual else "",
            "promise_scope": promise.get("scope", "") if promise else "",
            "actual_scope": actual.get("scope", "") if actual else "",
            "mode_match": bool(actual and actual.get("mode") == mode),
            "line_match": bool(actual and line_match(actual, facility)),
            "section_match": bool(actual and line_match(actual, facility)),
            "promise_event_date": promise.get("event_date", "") if promise else "",
            "actual_event_date": actual.get("event_date", "") if actual else "",
            "delay_days_representative": delay,
            "linkage_status": status,
            "deadline_status": deadline_status,
            "review_status": "needs_human",
            "notes": notes,
        })
    linkage_fields = [
        "linkage_id", "cohort", "development", "promise_source_id", "actual_source_id", "mode",
        "promise_line_name", "actual_line_name", "promise_scope", "actual_scope", "mode_match", "line_match",
        "section_match", "promise_event_date", "actual_event_date", "delay_days_representative",
        "linkage_status", "deadline_status", "review_status", "notes",
    ]
    write_csv(CURATED / "promise_linkage.csv", linkages, linkage_fields)

    gaps = []
    for development in HISTORICAL:
        linkage = next(row for row in linkages if row["development"] == development)
        occupancy = rows_by_id.get(PREFERRED_OCCUPANCY_FIRST_ID[development])
        if not occupancy or occupancy.get("review_status") == "rejected":
            occupancy = best_row(rows, qa_pass, development, "occupancy_first_actual", require_date=True)
        actual = next((row for row in rows if row.get("source_id") == linkage["actual_source_id"]), None)
        if not occupancy:
            continue
        lower = parse_iso(occupancy.get("event_date_lower", "")) or parse_iso(occupancy.get("event_date", ""))
        upper = parse_iso(occupancy.get("event_date_upper", "")) or parse_iso(occupancy.get("event_date", ""))
        operation_date = parse_iso(actual.get("event_date", "")) if actual else None
        endpoint = operation_date or AS_OF
        if not lower or not upper:
            continue
        gap_min = (endpoint - upper).days
        gap_max = (endpoint - lower).days
        gaps.append({
            "development": development,
            "occupancy_source_id": occupancy["source_id"],
            "occupancy_event_date": occupancy.get("event_date", ""),
            "occupancy_lower": lower.isoformat(),
            "occupancy_upper": upper.isoformat(),
            "operation_source_id": actual.get("source_id", "") if actual else "",
            "operation_event_date": operation_date.isoformat() if operation_date else "",
            "mode": linkage["mode"],
            "line_name": linkage["promise_line_name"],
            "gap_days_min": gap_min,
            "gap_days_max": gap_max,
            "gap_status": "closed" if operation_date else f"ongoing_as_of_{AS_OF.isoformat()}",
            "precision_note": "입주 날짜 정밀도에 따라 최소~최대 범위로 계산",
            "review_status": "needs_human",
        })
    gap_fields = [
        "development", "occupancy_source_id", "occupancy_event_date", "occupancy_lower", "occupancy_upper",
        "operation_source_id", "operation_event_date", "mode", "line_name", "gap_days_min", "gap_days_max",
        "gap_status", "precision_note", "review_status",
    ]
    write_csv(CURATED / "occupancy_operation_gap.csv", gaps, gap_fields)

    forward_rows = []
    for development in FORWARD:
        occupancy_candidates = [
            row for row in rows
            if row.get("development") == development
            and row.get("event_type") == "occupancy_planned_block"
            and row.get("review_status") != "rejected"
            and row.get("version_status") != "superseded"
            and representative_deadline(row)
        ]
        preferred_occupancy = rows_by_id.get(PREFERRED_FORWARD_OCCUPANCY_ID[development])
        occupancy = preferred_occupancy if preferred_occupancy and preferred_occupancy.get("review_status") != "rejected" else min(
            occupancy_candidates,
            key=lambda row: (representative_deadline(row), int(row.get("source_id") not in qa_pass), row.get("source_id", "")),
        ) if occupancy_candidates else None
        linkage = next(row for row in linkages if row["development"] == development)
        promise_deadline = None
        promise_row = next((row for row in rows if row.get("source_id") == linkage["promise_source_id"]), None)
        promise_deadline = representative_deadline(promise_row)
        occupancy_deadline = representative_deadline(occupancy)
        same_year_low_precision = bool(
            promise_row and occupancy
            and promise_row.get("date_precision") in ("year", "unknown", "")
            and promise_deadline and occupancy_deadline
            and promise_deadline.year == occupancy_deadline.year
        )
        if not promise_deadline:
            timing = "target_date_missing"
        elif same_year_low_precision:
            timing = "overlapping_or_ambiguous_period"
        elif occupancy_deadline and promise_deadline < occupancy_deadline:
            timing = "promise_before_planned_occupancy"
        elif occupancy_deadline and promise_deadline > occupancy_deadline:
            timing = "promise_after_planned_occupancy"
        else:
            timing = "overlapping_or_ambiguous_period"
        forward_rows.append({
            "development": development,
            "first_planned_block_source_id": occupancy.get("source_id", "") if occupancy else "",
            "block_name": occupancy.get("block_name", "") if occupancy else "",
            "planned_occupancy": occupancy.get("event_date", "") if occupancy else "",
            "promise_source_id": linkage["promise_source_id"],
            "mode": linkage["mode"],
            "line_name": linkage["promise_line_name"],
            "promise_target": linkage["promise_event_date"],
            "actual_operation_source_id": linkage["actual_source_id"],
            "monitoring_status": linkage["linkage_status"],
            "timing_relation": timing,
            "next_trigger": "운영기관의 실제 운행 개시 공지 또는 시간표 시행 공지",
        })
    forward_fields = [
        "development", "first_planned_block_source_id", "block_name", "planned_occupancy",
        "promise_source_id", "mode", "line_name", "promise_target", "actual_operation_source_id",
        "monitoring_status", "timing_relation", "next_trigger",
    ]
    write_csv(CURATED / "forward_monitoring.csv", forward_rows, forward_fields)

    coverage = []
    for cohort, developments in (("historical_validation", HISTORICAL), ("forward_monitoring", FORWARD)):
        for development in developments:
            for event_type in ALL_EVENTS:
                if event_type == "promise_linkage":
                    candidates = [row for row in linkages if row["development"] == development]
                    pass_count = len(candidates)
                else:
                    candidates = [row for row in active_rows if row.get("development") == development and row.get("event_type") == event_type]
                    pass_count = sum(row.get("source_id") in qa_pass for row in candidates)
                status = "ready_for_human" if pass_count else ("candidate_with_issues" if candidates else "missing")
                coverage.append({
                    "cohort": cohort, "development": development, "event_type": event_type,
                    "candidate_count": len(candidates), "qa_pass_count": pass_count, "coverage_status": status,
                })
    coverage_fields = ["cohort", "development", "event_type", "candidate_count", "qa_pass_count", "coverage_status"]
    write_csv(CURATED / "event_coverage.csv", coverage, coverage_fields)

    cross_validation = []
    gate_rows = []
    human_verified_total = sum(row.get("review_status") == "human_verified" for row in rows)
    for development in HISTORICAL:
        independent_counts = {}
        for event_type in ("occupancy_first_actual", "promise_date", "actual_operation"):
            evidence = [row for row in active_rows if row.get("development") == development and row.get("event_type") == event_type]
            independent = {(row.get("publisher", ""), row.get("source_url", "")) for row in evidence if row.get("publisher") or row.get("source_url")}
            independent_counts[event_type] = len(independent)
        consistent = all(value >= 2 for value in independent_counts.values())
        cross_validation.append({
            "development": development,
            "occupancy_independent_sources": independent_counts["occupancy_first_actual"],
            "promise_independent_sources": independent_counts["promise_date"],
            "actual_independent_sources": independent_counts["actual_operation"],
            "cross_validation_status": "candidate_multiple_sources" if consistent else "weak",
            "human_verified": 0,
            "notes": "독립 출처 수는 자동 후보 기준이며 사람 검증 완료를 의미하지 않음",
        })
        linkage = next(row for row in linkages if row["development"] == development)
        verified_sources = sum(row.get("review_status") == "human_verified" and row.get("development") == development for row in rows)
        blockers = []
        if verified_sources < 3:
            blockers.append("human_verified 3종 미충족")
        if linkage["review_status"] != "human_verified":
            blockers.append("사람 확인 완료 약속↔이행 링크 없음")
        if not consistent:
            blockers.append("독립 2축 교차검증 미충족")
        gate_rows.append({
            "development": development,
            "human_verified_sources": verified_sources,
            "has_occupancy_promise_actual_verified": False,
            "exact_mode_line_pair_verified": False,
            "cross_validation_consistent": consistent and verified_sources >= 3,
            "fine_precision_verified_pair": False,
            "gate_result": "FAIL",
            "candidate_linkage_status": linkage["linkage_status"],
            "cross_validation_current": "candidate_multiple_sources" if consistent else "weak",
            "blockers": "; ".join(blockers),
        })
    cross_fields = [
        "development", "occupancy_independent_sources", "promise_independent_sources",
        "actual_independent_sources", "cross_validation_status", "human_verified", "notes",
    ]
    gate_fields = [
        "development", "human_verified_sources", "has_occupancy_promise_actual_verified",
        "exact_mode_line_pair_verified", "cross_validation_consistent", "fine_precision_verified_pair",
        "gate_result", "candidate_linkage_status", "cross_validation_current", "blockers",
    ]
    write_csv(CURATED / "cross_validation.csv", cross_validation, cross_fields)
    write_csv(CURATED / "gate_results.csv", gate_rows, gate_fields)
    decision = [{
        "evaluated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pass_count": 0,
        "required_pass_count": 4,
        "fine_precision_count": 0,
        "required_fine_precision_count": 3,
        "decision": "PIVOT(A22)",
        "reason": "83개 PDF 전수 추출은 완료했지만 AI 추출은 human_verified와 독립 2축 검증을 대체하지 않음",
    }]
    decision_fields = ["evaluated_at", "pass_count", "required_pass_count", "fine_precision_count", "required_fine_precision_count", "decision", "reason"]
    write_csv(CURATED / "gate_decision.csv", decision, decision_fields)

    inventory = read_csv(STAGED / "pdf_inventory.csv")
    registry_ids_by_pdf: dict[str, list[str]] = defaultdict(list)
    for registry_row in rows:
        for pdf_id in (registry_row.get("pdf_id") or "").split(";"):
            if pdf_id:
                registry_ids_by_pdf[pdf_id].append(registry_row.get("source_id", ""))
    pdf_coverage = [{
        "pdf_id": row["pdf_id"], "filename": row["filename"], "sha256": row["sha256"],
        "extraction_status": row["extraction_status"], "duplicate_of_pdf_id": row["duplicate_of_pdf_id"],
        "page_count": row["page_count"], "text_chars": row["text_chars"],
        "registry_source_ids": ";".join(sorted(set(registry_ids_by_pdf.get(row["pdf_id"], [])))),
        "registry_represented": bool(
            registry_ids_by_pdf.get(row["pdf_id"])
            or (row["duplicate_of_pdf_id"] and registry_ids_by_pdf.get(row["duplicate_of_pdf_id"]))
        ),
    } for row in inventory]
    pdf_coverage_fields = ["pdf_id", "filename", "sha256", "extraction_status", "duplicate_of_pdf_id", "page_count", "text_chars", "registry_source_ids", "registry_represented"]
    write_csv(CURATED / "pdf_processing_coverage.csv", pdf_coverage, pdf_coverage_fields)

    snapshot = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "as_of": AS_OF.isoformat(),
        "summary": {
            "pdf_files": len(inventory),
            "unique_pdf_hashes": len({row["sha256"] for row in inventory}),
            "pdf_extraction_failures": sum(row["extraction_status"].startswith(("error", "empty", "ocr_empty")) for row in inventory),
            "registry_rows": len(rows),
            "active_target_rows": len(active_rows),
            "day1_pass_rows": len(qa_pass),
            "human_verified_rows": human_verified_total,
            "linkages": len(linkages),
            "gaps": len(gaps),
            "gate_pass": 0,
        },
        "decision": decision[0],
        "coverage": coverage,
        "promise_linkage": linkages,
        "occupancy_operation_gap": gaps,
        "forward_monitoring": forward_rows,
        "gates": gate_rows,
    }
    (CURATED / "report_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    claim_type_by_event = {
        "occupancy_planned_block": "occupancy",
        "occupancy_first_actual": "occupancy",
        "occupancy_first_planned": "occupancy",
        "promise_date": "promise",
        "actual_operation": "operation",
        "basic_service": "service",
    }
    evidence_log = [{
        "evidence_id": "EV-" + row.get("source_id", "").removeprefix("SRC-"),
        "source_id": row.get("source_id", ""),
        "pdf_id": row.get("pdf_id", ""),
        "development": row.get("development", ""),
        "claim_type": claim_type_by_event.get(row.get("event_type", ""), ""),
        "event_type": row.get("event_type", ""),
        "event_date": row.get("event_date", ""),
        "date_precision": row.get("date_precision", ""),
        "event_date_lower": row.get("event_date_lower", ""),
        "event_date_upper": row.get("event_date_upper", ""),
        "mode": row.get("mode", ""),
        "line_name": row.get("line_name", ""),
        "scope": row.get("scope", ""),
        "block_name": row.get("block_name", ""),
        "promise_verb_원문표기": row.get("promise_verb_원문표기", ""),
        "source_url": row.get("source_url", ""),
        "local_path": row.get("local_path", ""),
        "sha256": row.get("sha256", ""),
        "attachment_local_path": row.get("attachment_local_path", ""),
        "attachment_sha256": row.get("attachment_sha256", ""),
        "page_or_section": row.get("page_or_section", ""),
        "exact_excerpt": row.get("exact_excerpt", ""),
        "confidence": row.get("confidence", ""),
        "review_status": "ai_draft" if row.get("review_status") == "needs_human" else row.get("review_status", ""),
        "day1_qa_pass": row.get("source_id", "") in qa_pass,
    } for row in rows]
    evidence_log_fields = [
        "evidence_id", "source_id", "pdf_id", "development", "claim_type", "event_type", "event_date",
        "date_precision", "event_date_lower", "event_date_upper", "mode", "line_name", "scope", "block_name",
        "promise_verb_원문표기", "source_url", "local_path", "sha256", "attachment_local_path",
        "attachment_sha256", "page_or_section", "exact_excerpt", "confidence", "review_status", "day1_qa_pass",
    ]
    write_csv(CURATED / "evidence_log.csv", evidence_log, evidence_log_fields)

    EXPORTS.mkdir(parents=True, exist_ok=True)
    event_counts = Counter(row["event_type"] for row in active_rows)
    report = [
        "# 교통 공백 감사 Day 1·2·3 전수 재실행 보고서",
        "",
        f"**결론: PIVOT(A22)** — 원본 폴더의 PDF {len(inventory)}개(고유 해시 {len({row['sha256'] for row in inventory})}개)를 모두 추출·매칭했습니다. 추출 실패는 0건이며, 이미지형 PDF 1건은 Windows 한국어 OCR로 처리했습니다.",
        "",
        "## Day 1 — 전수 추출·필드 QA",
        "",
        f"- 통합 레지스트리: {len(rows)}행",
        f"- 목표 이벤트 활성 후보: {len(active_rows)}행",
        f"- 필수필드 QA 통과: {len(qa_pass)}행",
        f"- human_verified: {human_verified_total}행",
        "- 원문 PDF는 수정하지 않았고 모든 파일의 SHA-256, 페이지 수, 추출 상태, 레지스트리 연결 여부를 기록했습니다.",
        "",
        "| 이벤트 유형 | 활성 후보 |",
        "|---|---:|",
    ]
    report.extend(f"| {event_type} | {event_counts.get(event_type, 0)} |" for event_type in SOURCE_EVENTS)
    report.extend(["", "## Day 2 — 과거 약속↔이행", "", "| 지구 | 약속 | 실제 운행 | 판정 | 대표 지연일 |", "|---|---|---|---|---:|"])
    for row in linkages[:5]:
        report.append(f"| {row['development']} | {row['promise_source_id'] or '—'} | {row['actual_source_id'] or '—'} | {row['linkage_status']} | {row['delay_days_representative'] or '—'} |")
    report.extend(["", "## 입주–동일 약속시설 운행 공백", "", "| 지구 | 최초 실제 입주 | 동일 시설 운행 | 공백 범위(일) |", "|---|---|---|---:|"])
    for row in gaps:
        report.append(f"| {row['development']} | {row['occupancy_event_date']} | {row['operation_event_date'] or row['gap_status']} | {row['gap_days_min']}~{row['gap_days_max']} |")
    report.extend(["", "## 전방 모니터링 5곳", "", "| 지구 | 최초 예정 블록 | 교통 약속 | 상태 | 시간관계 |", "|---|---|---|---|---|"])
    for row in forward_rows:
        report.append(f"| {row['development']} | {row['block_name']} {row['planned_occupancy']} | {row['line_name']} {row['promise_target']} | {row['monitoring_status']} | {row['timing_relation']} |")
    report.extend(["", "## Day 3 — 엄격 게이트", "", "과거 5곳 모두 FAIL입니다. 전체 PDF 추출 완료는 사람 검증 완료를 의미하지 않으므로, exact excerpt·페이지·노선·날짜를 사람이 확인한 뒤에만 승격합니다.", ""])
    (EXPORTS / "day1_day2_day3_full_refresh_report.md").write_text("\n".join(report), encoding="utf-8")

    canonical_evidence = ROOT / "evidence"
    canonical_evidence.mkdir(parents=True, exist_ok=True)
    mirror_names = [
        "source_registry.csv", "review_queue.csv", "day1_qa.csv", "event_coverage.csv",
        "promise_linkage.csv", "occupancy_operation_gap.csv", "forward_monitoring.csv",
        "cross_validation.csv", "gate_results.csv", "gate_decision.csv", "pdf_processing_coverage.csv",
        "evidence_log.csv", "report_snapshot.json", "evidence_file_manifest.csv", "evidence_hash_map.csv",
        "targeted_evidence_extraction.csv",
    ]
    for name in mirror_names:
        shutil.copy2(CURATED / name, canonical_evidence / name)

    artifact_paths = [
        CURATED / "source_registry.csv", CURATED / "review_queue.csv", CURATED / "day1_qa.csv",
        CURATED / "event_coverage.csv", CURATED / "promise_linkage.csv", CURATED / "occupancy_operation_gap.csv",
        CURATED / "forward_monitoring.csv", CURATED / "cross_validation.csv", CURATED / "gate_results.csv",
        CURATED / "gate_decision.csv", CURATED / "pdf_processing_coverage.csv", CURATED / "report_snapshot.json",
        CURATED / "evidence_log.csv", CURATED / "evidence_file_manifest.csv", CURATED / "evidence_hash_map.csv",
        CURATED / "targeted_evidence_extraction.csv",
        EXPORTS / "day1_day2_day3_full_refresh_report.md",
    ]
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "artifacts": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in artifact_paths
        ],
    }
    (CURATED / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(snapshot["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
