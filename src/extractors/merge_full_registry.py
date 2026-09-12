"""Merge curated PDF evidence into canonical staged/curated registries.

Raw evidence files remain unchanged. Strong matches enrich existing records;
weak or new evidence becomes a separate needs_human row. Every unique PDF is
represented, including context/out-of-scope documents with an explicit reason.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW_EVIDENCE = ROOT / "data" / "raw" / "evidence"
STAGED = ROOT / "data" / "staged"
CURATED = ROOT / "data" / "curated"
CANONICAL_EVIDENCE = ROOT / "evidence"
BASE_REGISTRY = RAW_EVIDENCE / "source_registry.csv"
EVENTS_PATH = STAGED / "pdf_curated_events.csv"
DISPOSITION_PATH = STAGED / "pdf_document_disposition.csv"
INVENTORY_PATH = STAGED / "pdf_inventory.csv"


EVENT_ROLE = {
    "occupancy_planned_block": "planned_block",
    "occupancy_first_actual": "gap_start",
    "occupancy_first_planned": "delay_baseline",
    "promise_date": "promise",
    "actual_operation": "gap_end",
    "basic_service": "service_level",
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


def append_unique(row: dict[str, str], field: str, value: str) -> None:
    value = (value or "").strip()
    if not value:
        return
    current = [item for item in (row.get(field) or "").split(";") if item]
    if value not in current:
        current.append(value)
    row[field] = ";".join(current)


def clean_url(value: str) -> str:
    value = (value or "").replace("\x00", "").strip()
    return value if value.startswith(("http://", "https://")) else ""


def date_bounds(value: str, precision: str) -> tuple[str, str, str]:
    if not value:
        return "", "", ""
    if precision == "day" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value, value, value
    if precision == "month" and re.fullmatch(r"\d{4}-\d{2}", value):
        year, month = map(int, value.split("-"))
        next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        upper = date.fromordinal(next_month.toordinal() - 1)
        return upper.isoformat(), f"{year:04d}-{month:02d}-01", upper.isoformat()
    year_match = re.match(r"^(\d{4})", value)
    if year_match:
        year = int(year_match.group(1))
        if "상반기" in value:
            return f"{year}-06-30", f"{year}-01-01", f"{year}-06-30"
        if "하반기" in value:
            return f"{year}-12-31", f"{year}-07-01", f"{year}-12-31"
        return f"{year}-12-31", f"{year}-01-01", f"{year}-12-31"
    return "", "", ""


def publisher_type(publisher: str, source_url: str) -> str:
    if publisher == "연합뉴스" or "yna.co.kr" in source_url:
        return "media_clue"
    if publisher:
        return "official_pdf"
    return "local_pdf_unknown_publisher"


def row_issue(row: dict[str, str]) -> str:
    issues = []
    if row.get("review_status") == "rejected":
        return row.get("reject_reason", "rejected")
    if not row.get("source_url"):
        issues.append("missing_direct_source_url")
    if not row.get("development"):
        issues.append("missing_development")
    if not row.get("event_type"):
        issues.append("missing_event_type")
    if row.get("event_type") in EVENT_ROLE and not row.get("event_date"):
        issues.append("missing_event_date")
    if row.get("event_type") in EVENT_ROLE and not row.get("exact_excerpt"):
        issues.append("missing_exact_excerpt")
    if row.get("event_type") == "promise_date":
        for field in ("mode", "line_name", "scope", "promise_verb_원문표기"):
            if not row.get(field):
                issues.append(f"missing_{field}")
    if row.get("event_type") == "basic_service" and not any(
        row.get(field) for field in ("service_headway", "service_first", "service_last")
    ):
        issues.append("missing_service_level")
    return ";".join(issues)


def version_rank(title: str) -> int:
    if "정정" in title:
        return 2
    if "최종" in title:
        return 1
    return 0


def assign_versions(rows: list[dict[str, str]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("event_type") != "occupancy_planned_block":
            continue
        development = row.get("development", "")
        blocks = [block for block in (row.get("block_name") or "").split(";") if block]
        if not development or not blocks:
            continue
        for block in blocks:
            normalized_block = re.sub(r"[^A-Z0-9]", "", block.upper())
            groups[(development, normalized_block)].append(row)
    for group in groups.values():
        unique_rows = list({row["source_id"]: row for row in group}.values())
        unique_rows.sort(key=lambda row: (
            (row.get("published_date", "") or "")[:7],
            version_rank(row.get("title", "")),
            row.get("published_date", ""),
            row["source_id"],
        ))
        if len(unique_rows) < 2:
            continue
        previous = ""
        for index, row in enumerate(unique_rows, 1):
            row["document_version"] = f"v{index}"
            row["version_status"] = "latest" if index == len(unique_rows) else "superseded"
            row["supersedes_source_id"] = previous
            previous = row["source_id"]


def main() -> None:
    base_rows = read_csv(BASE_REGISTRY)
    events = read_csv(EVENTS_PATH)
    dispositions = read_csv(DISPOSITION_PATH)
    inventory = read_csv(INVENTORY_PATH)
    inventory_by_id = {row["pdf_id"]: row for row in inventory}
    base_by_id = {row["source_id"]: row for row in base_rows}
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    extra_fields = [
        "pdf_id", "raw_pdf_path", "pdf_sha256", "pdf_match_method", "pdf_match_confidence",
        "pdf_disposition", "pdf_extraction_status", "pdf_page_count", "pdf_text_chars",
    ]
    fields = list(base_rows[0].keys())
    for field in extra_fields:
        if field not in fields:
            fields.append(field)
    rows = [{field: row.get(field, "") for field in fields} for row in base_rows]
    by_id = {row["source_id"]: row for row in rows}

    created_ids: list[str] = []
    represented_pdf_ids: set[str] = set()
    for event in events:
        inventory_row = inventory_by_id[event["pdf_id"]]
        score = float(event.get("match_score") or 0)
        # Only byte identity or the same direct file URL can enrich an existing
        # record. Shared excerpts occur across original/correction versions and
        # must remain separate versioned records.
        strong_methods = {"sha256", "source_url"}
        strong_match = event.get("registry_source_id", "") if score >= 0.9 and event.get("match_method") in strong_methods else ""
        if strong_match and strong_match in by_id:
            target = by_id[strong_match]
            append_unique(target, "pdf_id", event["pdf_id"])
            append_unique(target, "raw_pdf_path", event["raw_path"])
            append_unique(target, "pdf_sha256", event["sha256"])
            append_unique(target, "pdf_match_method", event.get("match_method", ""))
            append_unique(target, "pdf_match_confidence", event.get("match_score", ""))
            append_unique(target, "attachment_local_path", event["raw_path"])
            append_unique(target, "attachment_sha256", event["sha256"])
            append_unique(target, "attachment_source_url", clean_url(event.get("source_url", "")))
            target["pdf_disposition"] = "matched_existing"
            target["pdf_extraction_status"] = inventory_row.get("extraction_status", "")
            target["pdf_page_count"] = inventory_row.get("page_count", "")
            target["pdf_text_chars"] = inventory_row.get("text_chars", "")
            represented_pdf_ids.add(event["pdf_id"])
            continue

        developments = [value for value in event.get("development", "").split(";") if value] or [""]
        for development_index, development in enumerate(developments, 1):
            suffix = re.sub(r"[^A-Z0-9]", "", event["event_type"].upper())[:4]
            source_id = f"SRC-{event['pdf_id']}-{suffix}-{development_index}"
            counter = 1
            original_id = source_id
            while source_id in by_id:
                counter += 1
                source_id = f"{original_id}-{counter}"
            normalized, lower, upper = date_bounds(event.get("event_date", ""), event.get("date_precision", ""))
            source_url = clean_url(event.get("source_url", ""))
            source_type = publisher_type(event.get("publisher", ""), source_url)
            review_status = "rejected" if source_type == "media_clue" else "needs_human"
            reject_reason = "media_clue_not_primary_source" if source_type == "media_clue" else ""
            new_row = {field: "" for field in fields}
            new_row.update({
                "source_id": source_id,
                "development": development,
                "source_type": source_type,
                "title": Path(event["filename"]).stem,
                "publisher": event.get("publisher", ""),
                "published_date": event.get("published_date", ""),
                "retrieved_at": now,
                "source_url": source_url,
                "local_path": event["raw_path"],
                "sha256": event["sha256"],
                "page_or_section": event.get("page_or_section", ""),
                "exact_excerpt": event.get("exact_excerpt", ""),
                "event_type": event["event_type"],
                "event_date": event.get("event_date", ""),
                "date_precision": event.get("date_precision", ""),
                "mode": event.get("mode", ""),
                "scope": event.get("scope", ""),
                "confidence": "medium" if event.get("event_date") and event.get("exact_excerpt") else "low",
                "review_status": review_status,
                "notes": "83개 PDF 전수 추출에서 생성된 AI 초안; 사람 확인 전 지표 확정 금지",
                "cand_id": event["pdf_event_id"],
                "cand_id_namespaced": event["pdf_event_id"],
                "cohort_type": "2G_historical" if development in ("화성 동탄2", "김포 한강", "위례", "남양주 다산", "하남 미사") else ("3G_forward" if development else "other"),
                "file_kind": "pdf",
                "event_date_normalized": normalized,
                "event_date_lower": lower,
                "event_date_upper": upper,
                "line_name": event.get("line_name", ""),
                "promise_verb_원문표기": event.get("promise_verb_원문표기", ""),
                "http_status": "LOCAL_FILE",
                "bytes": inventory_row.get("bytes", ""),
                "local_text_path": inventory_row.get("text_path", ""),
                "excerpt_found": "Y" if event.get("exact_excerpt") else "N",
                "excerpt_sim": "1.000" if event.get("exact_excerpt") else "",
                "review_issue": event.get("review_issue", ""),
                "reject_reason": reject_reason,
                "pairable": "True" if event.get("event_date") and event.get("line_name") and ";" not in event.get("line_name", "") else "False",
                "commitment_version": "1",
                "block_name": event.get("block_name", ""),
                "event_date_basis": event.get("page_or_section", ""),
                "evidence_role": EVENT_ROLE[event["event_type"]],
                "document_verified": "agent_extracted",
                "verification_method": "local_pdf_sha256_text_extract" if inventory_row.get("extraction_status") != "ocr_success" else "local_pdf_sha256_windows_ocr",
                "verified_at": now,
                "pdf_id": event["pdf_id"],
                "raw_pdf_path": event["raw_path"],
                "pdf_sha256": event["sha256"],
                "pdf_match_method": event.get("match_method", "new_pdf_event"),
                "pdf_match_confidence": event.get("match_score", ""),
                "pdf_disposition": "new_or_weak_match",
                "pdf_extraction_status": inventory_row.get("extraction_status", ""),
                "pdf_page_count": inventory_row.get("page_count", ""),
                "pdf_text_chars": inventory_row.get("text_chars", ""),
            })
            new_row["review_issue"] = ";".join(filter(None, [new_row.get("review_issue", ""), row_issue(new_row)]))
            rows.append(new_row)
            by_id[source_id] = new_row
            created_ids.append(source_id)
            represented_pdf_ids.add(event["pdf_id"])

    # Add explicit context/out-of-scope records so every unique document is accounted for.
    for disposition in dispositions:
        pdf_id = disposition["pdf_id"]
        if disposition["disposition"] == "duplicate" or pdf_id in represented_pdf_ids:
            continue
        inventory_row = inventory_by_id[pdf_id]
        source_id = f"SRC-{pdf_id}-DOC"
        new_row = {field: "" for field in fields}
        new_row.update({
            "source_id": source_id,
            "development": disposition.get("developments", ""),
            "source_type": "context_pdf",
            "title": Path(disposition["filename"]).stem,
            "publisher": inventory_row.get("publisher_guess", ""),
            "published_date": inventory_row.get("published_date_guess", ""),
            "retrieved_at": now,
            "source_url": clean_url(inventory_row.get("source_url", "")),
            "local_path": inventory_row["raw_path"],
            "sha256": inventory_row["sha256"],
            "file_kind": "pdf",
            "review_status": "rejected",
            "reject_reason": disposition["reason"],
            "notes": "83개 PDF 전수 인벤토리에는 포함하되 7개 목표 이벤트 직접 증거에서는 제외",
            "evidence_role": "context_only",
            "document_verified": "agent_extracted",
            "verification_method": "local_pdf_sha256_text_extract",
            "verified_at": now,
            "pdf_id": pdf_id,
            "raw_pdf_path": inventory_row["raw_path"],
            "pdf_sha256": inventory_row["sha256"],
            "pdf_disposition": disposition["disposition"],
            "pdf_extraction_status": inventory_row.get("extraction_status", ""),
            "pdf_page_count": inventory_row.get("page_count", ""),
            "pdf_text_chars": inventory_row.get("text_chars", ""),
        })
        rows.append(new_row)
        by_id[source_id] = new_row
        created_ids.append(source_id)
        represented_pdf_ids.add(pdf_id)

    assign_versions(rows)
    for row in rows:
        if row.get("review_status") == "needs_human":
            computed = row_issue(row)
            if computed:
                row["review_issue"] = ";".join(dict.fromkeys(filter(None, (row.get("review_issue", "") + ";" + computed).split(";"))))

    registry_out = CURATED / "source_registry.csv"
    write_csv(registry_out, rows, fields)
    CANONICAL_EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(registry_out, CANONICAL_EVIDENCE / "source_registry.csv")

    queue_rows = []
    for row in rows:
        issue = row_issue(row) or row.get("review_issue", "")
        if row.get("review_status") not in ("needs_human", "rejected") and not issue:
            continue
        priority = 1 if row.get("review_status") == "needs_human" and issue else (2 if row.get("review_status") == "needs_human" else 3)
        queue_rows.append({
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
            "review_issue": issue or row.get("reject_reason", ""),
            "required_action": "원문 페이지·날짜·노선·범위를 사람이 확인 후 human_verified/rejected 확정",
            "reject_reason": row.get("reject_reason", ""),
            "notes": row.get("notes", ""),
        })
    queue_rows.sort(key=lambda row: (row["review_priority"], row["development"], row["event_type"], row["source_id"]))
    queue_fields = [
        "review_priority", "source_id", "pdf_id", "development", "event_type", "title", "source_url",
        "local_path", "page_or_section", "exact_excerpt", "review_status", "review_issue",
        "required_action", "reject_reason", "notes",
    ]
    queue_out = CURATED / "review_queue.csv"
    write_csv(queue_out, queue_rows, queue_fields)
    shutil.copy2(queue_out, CANONICAL_EVIDENCE / "review_queue.csv")

    summary = {
        "generated_at": now,
        "base_registry_rows": len(base_rows),
        "curated_registry_rows": len(rows),
        "new_rows": len(created_ids),
        "review_queue_rows": len(queue_rows),
        "unique_pdf_ids_represented": len(represented_pdf_ids),
        "unique_pdf_ids_expected": sum(row["disposition"] != "duplicate" for row in dispositions),
        "duplicate_pdf_files": sum(row["disposition"] == "duplicate" for row in dispositions),
        "registry_sha256": hashlib.sha256(registry_out.read_bytes()).hexdigest(),
        "queue_sha256": hashlib.sha256(queue_out.read_bytes()).hexdigest(),
    }
    (CURATED / "registry_merge_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
