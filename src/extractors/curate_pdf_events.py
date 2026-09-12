"""Curate event candidates and match every unique PDF to the evidence registry.

This stage is deliberately conservative: recruitment notices are not allowed to
create transport-operation events from boilerplate, and future/inspection/trial
operation notices are not treated as actual operation starts.
"""

from __future__ import annotations

import csv
import difflib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pymupdf

from full_pdf_refresh import (
    DEVELOPMENT_PATTERNS,
    LINE_PATTERNS,
    RAW_DIR,
    ROOT,
    STAGED_DIR,
    TEXT_DIR,
    norm,
)


INVENTORY_PATH = STAGED_DIR / "pdf_inventory.csv"
REGISTRY_PATH = RAW_DIR / "source_registry.csv"

RECRUITMENT_TERMS = ("입주자모집", "모집공고", "공공분양", "행복주택", "국민임대", "공공임대")
FUTURE_OPERATION_TERMS = ("앞둔", "예정", "목표", "시범운행", "시험운행", "현장점검", "추진")
DATE_PATTERN = re.compile(
    r"(?<!\d)((?:19|20)\d{2})\s*[.년/-]\s*(0?[1-9]|1[0-2])"
    r"(?:\s*[.월/-]\s*(0?[1-9]|[12]\d|3[01]))?\s*(?:일)?(?!\d)"
)
YEAR_PERIOD_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*년\s*(상반기|하반기|말|초)?")
MONTH_DAY_PATTERN = re.compile(r"(?<!\d)(0?[1-9]|1[0-2])\s*월\s*(0?[1-9]|[12]\d|3[01])\s*일")
SHORT_YEAR_MONTH_PATTERN = re.compile(r"[’'‘]?(\d{2})\s*[.]\s*(0?[1-9]|1[0-2])\s*월")
PRIMARY_BLOCK_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z]{1,2})\s*[- ]?\s*(\d{1,2}[a-z]?)(?:\s*BL|\s*블록)", re.I
)


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


def clean_url(value: str) -> str:
    return (value or "").replace("\x00", "").strip()


def filename_date(filename: str, text: str) -> str:
    stem = Path(filename).stem
    compact = re.search(r"(?<!\d)(\d{2})(0[1-9]|1[0-2])([0-3]\d)(?!\d)", stem)
    if compact:
        year, month, day = compact.groups()
        try:
            return datetime(2000 + int(year), int(month), int(day)).date().isoformat()
        except ValueError:
            pass
    full = DATE_PATTERN.search(f"{stem}\n{text[:2500]}")
    if full:
        year, month, day = full.groups()
        day = day or "01"
        try:
            return datetime(int(year), int(month), int(day)).date().isoformat()
        except ValueError:
            return ""
    return ""


def filename_developments(filename: str) -> list[str]:
    compact = norm(filename)
    found = []
    for development, patterns in DEVELOPMENT_PATTERNS.items():
        if any(norm(pattern) in compact for pattern in patterns):
            found.append(development)
    return found


def filename_lines(filename: str) -> list[str]:
    compact = norm(filename)
    found = []
    for line, patterns in LINE_PATTERNS.items():
        if any(norm(pattern) in compact for pattern in patterns):
            found.append(line)
    return found


def line_developments(lines: list[str]) -> list[str]:
    mapping = {
        "GTX-A 수서~동탄": ["화성 동탄2"],
        "김포도시철도(김포골드라인)": ["김포 한강"],
        "위례선 트램": ["위례"],
        "별내선(8호선 연장)": ["남양주 다산"],
        "하남선(5호선 연장)": ["하남 미사", "하남 교산"],
        "진접선(4호선 연장)": ["남양주 왕숙"],
        "인천도시철도 1호선 검단연장선": ["인천 계양"],
        "고양은평선": ["고양 창릉"],
        "강동하남남양주선": ["남양주 왕숙"],
        "송파하남선": ["하남 교산"],
        "계양~대장 S-BRT": ["인천 계양", "부천 대장"],
        "대곡~소사선": ["고양 창릉"],
    }
    return list(dict.fromkeys(value for line in lines for value in mapping.get(line, [])))


def infer_developments(filename: str, text: str, lines: list[str]) -> list[str]:
    found = filename_developments(filename)
    if found:
        return found
    found = line_developments(lines)
    if found:
        return found
    compact = norm(text[:20000])
    for development, patterns in DEVELOPMENT_PATTERNS.items():
        if any(norm(pattern) in compact for pattern in patterns):
            found.append(development)
    return found


def infer_lines(filename: str, text: str) -> list[str]:
    found = filename_lines(filename)
    compact = norm(text[:50000])
    for line, patterns in LINE_PATTERNS.items():
        if line not in found and any(norm(pattern) in compact for pattern in patterns):
            found.append(line)
    return found


def classify_document(filename: str, text: str) -> tuple[list[str], str]:
    title = filename.lower()
    compact_title = norm(filename)
    if "단지내상가" in title:
        return [], "commercial_notice_out_of_scope"
    if any(term in filename for term in RECRUITMENT_TERMS):
        return ["occupancy_planned_block"], "housing_recruitment_notice"
    if "첫입주" in compact_title or "입주지원특별대책반" in compact_title:
        return ["occupancy_first_actual"], "district_move_in_evidence"
    if "입주예정아파트" in compact_title:
        return ["occupancy_first_actual"], "regional_move_in_schedule"
    if "광역교통" in compact_title or "교통개선대책" in compact_title or "교통대책" in compact_title or filename.lower().startswith("brt"):
        return ["promise_date"], "transport_plan_or_promise"
    if "노면전차사업" in compact_title:
        return ["promise_date", "basic_service"], "transport_project_promise_and_planned_service"
    if "민생토론회" in filename or filename == "bodo_2.pdf":
        return ["promise_date"], "transport_policy_plan"
    if "개통" in filename or "첫 운행" in filename or "운행 시작" in filename or "노선 개통" in filename:
        if any(term in filename for term in FUTURE_OPERATION_TERMS):
            return ["promise_date"], "future_or_trial_operation_notice"
        events = ["actual_operation"]
        if any(term in text for term in ("배차간격", "운행간격", "첫차", "막차", "운행횟수", "운행 횟수")):
            events.append("basic_service")
        return events, "actual_operation_notice"
    if "시내버스" in filename or "노선도" in filename or "8849번" in filename or "땡큐버스" in filename:
        return ["basic_service"], "service_information"
    if "첫공급개시" in compact_title:
        return ["occupancy_planned_block"], "first_supply_with_planned_occupancy"
    if filename == "보도자료 - 김포시뉴스포털.pdf":
        return ["actual_operation", "basic_service"], "actual_operation_notice"
    if "동탄2신도시070601" in compact_title:
        return ["occupancy_first_planned"], "district_master_plan_baseline"
    if "빛나는하남" in compact_title:
        return ["actual_operation", "promise_date"], "municipal_year_end_recap"
    if "동탄신도시김포공항버스" in compact_title:
        return ["actual_operation", "basic_service"], "media_clue_requires_official_source"
    if filename == "인쇄하기 - 하남시청.pdf":
        return ["basic_service"], "municipal_service_context"
    if filename == "정책브리핑 _ 기사인쇄하기.pdf":
        return ["occupancy_first_planned"], "district_planned_move_in_baseline"
    if "회의록" in filename or "정책브리핑" in filename or "기사인쇄" in filename or "의견공감" in filename:
        return [], "context_only_requires_manual_scope_review"
    if "청정하남" in filename:
        return [], "newsletter_context_only"
    if "land_announce" in filename:
        return ["occupancy_first_planned"], "land_plan_notice"
    return [], "no_target_event_detected"


def load_pages(path: Path, sha256: str) -> list[str]:
    ocr_path = TEXT_DIR / f"{sha256}.ocr.txt"
    if ocr_path.exists():
        text = ocr_path.read_text(encoding="utf-8", errors="ignore")
        return re.split(r"(?m)^=== PDF p\.\d+ ===\s*$", text)[1:]
    with pymupdf.open(path) as doc:
        return [page.get_text("text") or "" for page in doc]


def context_candidates(pages: list[str], terms: tuple[str, ...], width: int = 520) -> list[tuple[int, str]]:
    results = []
    for page_number, page in enumerate(pages, 1):
        for term in terms:
            cursor = 0
            while True:
                index = page.find(term, cursor)
                if index < 0:
                    break
                start = max(0, index - width // 3)
                excerpt = re.sub(r"\s+", " ", page[start : start + width]).strip()
                results.append((page_number, excerpt))
                cursor = index + len(term)
                if len(results) >= 20:
                    return results
    return results


def raw_dates(text: str, published_date: str = "") -> list[tuple[str, str, str]]:
    values = []
    for match in DATE_PATTERN.finditer(text):
        year, month, day = match.groups()
        precision = "day" if day else "month"
        normalized = f"{int(year):04d}-{int(month):02d}" + (f"-{int(day):02d}" if day else "")
        values.append((match.group(0).strip(), normalized, precision))
    if published_date:
        year = published_date[:4]
        for match in MONTH_DAY_PATTERN.finditer(text):
            month, day = match.groups()
            normalized = f"{year}-{int(month):02d}-{int(day):02d}"
            values.append((match.group(0).strip(), normalized, "day"))
    for match in SHORT_YEAR_MONTH_PATTERN.finditer(text):
        short_year, month = match.groups()
        normalized = f"20{int(short_year):02d}-{int(month):02d}"
        values.append((match.group(0).strip(), normalized, "month"))
    for match in YEAR_PERIOD_PATTERN.finditer(text):
        year, period = match.groups()
        raw = match.group(0).strip()
        normalized = year + (f"-{period}" if period else "")
        values.append((raw, normalized, "half" if period in ("상반기", "하반기") else "year"))
    return values


def choose_event_evidence(event_type: str, pages: list[str], published_date: str) -> tuple[str, str, str, str]:
    terms = {
        "occupancy_planned_block": ("입주예정 시기는", "입주 예정 시기는", "입주예정시기", "입주 예정시기", "입주예정월", "입주예정일", "입주시기"),
        "occupancy_first_actual": ("첫 입주", "입주를 시작", "입주가 시작", "입주지원"),
        "occupancy_first_planned": ("최초 입주", "입주 예정", "입주시기"),
        "promise_date": ("개통 예정", "준공 예정", "목표", "추진", "계획", "광역교통개선대책"),
        "actual_operation": ("개통", "첫 운행", "운행 개시", "운행을 시작"),
        "basic_service": ("배차간격", "운행간격", "첫차", "막차", "운행 횟수", "운행횟수"),
    }[event_type]
    contexts = context_candidates(pages, terms)
    best = ("", "", "", "")
    for page_number, excerpt in contexts:
        dates = raw_dates(excerpt, published_date)
        if dates:
            published_year = int(published_date[:4]) if published_date else 0
            if event_type in ("occupancy_planned_block", "occupancy_first_planned", "promise_date"):
                future = [value for value in dates if value[1][:4].isdigit() and int(value[1][:4]) >= published_year]
                raw, normalized, precision = (future[-1] if future else dates[-1])
            elif event_type in ("actual_operation", "basic_service"):
                non_publication = [value for value in dates if value[1] != published_date]
                raw, normalized, precision = (non_publication[-1] if non_publication else dates[-1])
            else:
                raw, normalized, precision = dates[-1]
            return normalized, precision, f"PDF p.{page_number}", excerpt
        if not best[3]:
            best = ("", "unknown", f"PDF p.{page_number}", excerpt)
    return best


def clean_title(value: str) -> str:
    value = Path(value).stem
    value = re.sub(r"^[★＇\s()\[\]정정최종0-9._-]+", "", value)
    return norm(value)


def best_registry_match(
    filename: str,
    sha256: str,
    source_url: str,
    developments: list[str],
    event_type: str,
    excerpt: str,
    registry: list[dict[str, str]],
) -> tuple[str, str, float]:
    clean_source_url = clean_url(source_url)
    normalized_excerpt = norm(excerpt)
    file_title = clean_title(filename)
    best = ("", "", 0.0)
    for row in registry:
        source_id = row.get("source_id", "")
        row_hashes = {(row.get("sha256") or "").lower(), (row.get("attachment_sha256") or "").lower()}
        if sha256.lower() in row_hashes:
            return source_id, "sha256", 1.0
        row_urls = {clean_url(row.get("source_url", "")), clean_url(row.get("attachment_source_url", ""))}
        if clean_source_url and clean_source_url in row_urls:
            return source_id, "source_url", 0.99
        row_excerpt = norm(row.get("exact_excerpt", ""))
        if len(row_excerpt) >= 35 and row_excerpt in normalized_excerpt:
            return source_id, "exact_excerpt", 0.98
        if event_type and row.get("event_type") and event_type != row.get("event_type"):
            continue
        if developments and row.get("development") not in developments:
            continue
        title_score = difflib.SequenceMatcher(None, file_title, clean_title(row.get("title", ""))).ratio()
        if title_score > best[2]:
            best = (source_id, "title_development_event", round(title_score, 3))
    return best if best[2] >= 0.58 else ("", "", 0.0)


def mode_for(lines: list[str], event_type: str) -> str:
    if "위례선 트램" in lines:
        return "tram"
    if "계양~대장 S-BRT" in lines:
        return "sbrt"
    if lines and event_type in ("promise_date", "actual_operation", "basic_service"):
        return "rail"
    return ""


def primary_blocks(filename: str, text: str) -> list[str]:
    matches = PRIMARY_BLOCK_PATTERN.findall(filename)
    if not matches:
        matches = PRIMARY_BLOCK_PATTERN.findall(text[:2200])
    values = []
    for prefix, number in matches:
        value = f"{prefix.upper()}-{number}"
        if value not in values:
            values.append(value)
    return values[:4]


def main() -> None:
    inventory = read_csv(INVENTORY_PATH)
    registry = read_csv(REGISTRY_PATH)
    dispositions: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    match_audit: list[dict[str, object]] = []

    for row in inventory:
        if row.get("duplicate_of_pdf_id"):
            dispositions.append({
                "pdf_id": row["pdf_id"], "filename": row["filename"], "sha256": row["sha256"],
                "disposition": "duplicate", "reason": f"same_sha256_as:{row['duplicate_of_pdf_id']}",
                "event_types": "", "developments": "", "registry_match": "",
            })
            continue
        path = Path(row["raw_path"])
        text_path = Path(row["text_path"])
        text = text_path.read_text(encoding="utf-8", errors="ignore")
        pages = load_pages(path, row["sha256"])
        lines = infer_lines(row["filename"], text)
        developments = infer_developments(row["filename"], text, lines)
        blocks = primary_blocks(row["filename"], text)
        event_types, reason = classify_document(row["filename"], text)
        published_date = filename_date(row["filename"], text)
        source_url = clean_url(row.get("source_url", ""))
        registry_matches = []
        for event_type in event_types:
            event_date, precision, page_or_section, excerpt = choose_event_evidence(event_type, pages, published_date)
            source_id, method, score = best_registry_match(
                row["filename"], row["sha256"], source_url, developments, event_type, excerpt, registry
            )
            if source_id:
                registry_matches.append(source_id)
            event_id = f"{row['pdf_id']}-{event_type}"
            events.append({
                "pdf_event_id": event_id,
                "pdf_id": row["pdf_id"],
                "filename": row["filename"],
                "raw_path": row["raw_path"],
                "sha256": row["sha256"],
                "development": ";".join(developments),
                "event_type": event_type,
                "published_date": published_date,
                "event_date": event_date,
                "date_precision": precision,
                "mode": mode_for(lines, event_type),
                "line_name": ";".join(lines),
                "scope": "block" if event_type == "occupancy_planned_block" else "district",
                "block_name": ";".join(blocks),
                "promise_verb_원문표기": ";".join(verb for verb in ("예정", "목표", "추진", "확정", "계획") if verb in excerpt),
                "page_or_section": page_or_section,
                "exact_excerpt": excerpt,
                "source_url": source_url,
                "publisher": row.get("publisher_guess", ""),
                "registry_source_id": source_id,
                "match_method": method,
                "match_score": score,
                "review_status": "needs_human",
                "review_issue": "" if event_date and excerpt else "missing_event_date_or_excerpt",
            })
            match_audit.append({
                "pdf_id": row["pdf_id"], "pdf_event_id": event_id, "filename": row["filename"],
                "event_type": event_type, "registry_source_id": source_id, "match_method": method,
                "match_score": score, "requires_new_registry_row": "N" if source_id and score >= 0.9 else "Y",
            })
        disposition = "target_event" if event_types else "context_or_out_of_scope"
        dispositions.append({
            "pdf_id": row["pdf_id"], "filename": row["filename"], "sha256": row["sha256"],
            "disposition": disposition, "reason": reason, "event_types": ";".join(event_types),
            "developments": ";".join(developments), "registry_match": ";".join(sorted(set(registry_matches))),
        })

    write_csv(
        STAGED_DIR / "pdf_document_disposition.csv", dispositions,
        ["pdf_id", "filename", "sha256", "disposition", "reason", "event_types", "developments", "registry_match"],
    )
    write_csv(
        STAGED_DIR / "pdf_curated_events.csv", events,
        [
            "pdf_event_id", "pdf_id", "filename", "raw_path", "sha256", "development", "event_type",
            "published_date", "event_date", "date_precision", "mode", "line_name", "scope", "block_name",
            "promise_verb_원문표기", "page_or_section", "exact_excerpt", "source_url", "publisher",
            "registry_source_id", "match_method", "match_score", "review_status", "review_issue",
        ],
    )
    write_csv(
        STAGED_DIR / "pdf_match_audit.csv", match_audit,
        [
            "pdf_id", "pdf_event_id", "filename", "event_type", "registry_source_id", "match_method",
            "match_score", "requires_new_registry_row",
        ],
    )
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "inventory_files": len(inventory),
        "unique_documents": len(dispositions) - sum(row["disposition"] == "duplicate" for row in dispositions),
        "duplicate_files": sum(row["disposition"] == "duplicate" for row in dispositions),
        "target_documents": sum(row["disposition"] == "target_event" for row in dispositions),
        "context_or_out_of_scope_documents": sum(row["disposition"] == "context_or_out_of_scope" for row in dispositions),
        "curated_event_rows": len(events),
        "strong_registry_matches": sum(float(row["match_score"]) >= 0.9 for row in match_audit),
        "new_or_weak_match_rows": sum(row["requires_new_registry_row"] == "Y" for row in match_audit),
        "event_rows_with_date_and_excerpt": sum(bool(row["event_date"] and row["exact_excerpt"]) for row in events),
    }
    (STAGED_DIR / "pdf_curation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
