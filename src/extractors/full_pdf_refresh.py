"""Build a complete, auditable inventory for every PDF in data/raw/evidence.

Raw PDFs are never modified. Each file is hashed and extracted one at a time.
Outputs are written under data/staged so every source, duplicate, match, and
candidate event remains inspectable before it is promoted to curated evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pymupdf


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "evidence"
STAGED_DIR = ROOT / "data" / "staged"
TEXT_DIR = STAGED_DIR / "pdf_text"
REGISTRY_PATH = RAW_DIR / "source_registry.csv"


DEVELOPMENT_PATTERNS = {
    "화성 동탄2": ("동탄2", "동탄(2)", "동탄신도시", "동탄 2"),
    "김포 한강": ("김포한강", "김포 한강", "김포도시철도", "김포골드라인"),
    "위례": ("위례",),
    "남양주 다산": ("다산신도시", "다산지금", "다산역", "남양주 다산"),
    "하남 미사": ("미사강변", "하남미사", "하남 미사", "미사지구"),
    "인천 계양": ("인천계양", "인천 계양", "계양~대장", "계양-대장"),
    "남양주 왕숙": ("남양주왕숙", "남양주 왕숙", "왕숙"),
    "하남 교산": ("하남교산", "하남 교산", "교산"),
    "고양 창릉": ("고양창릉", "고양 창릉", "창릉"),
    "부천 대장": ("부천대장", "부천 대장", "계양~대장", "계양-대장"),
}

LINE_PATTERNS = {
    "GTX-A 수서~동탄": ("GTX-A", "수서~동탄", "수서-동탄"),
    "김포도시철도(김포골드라인)": ("김포도시철도", "김포골드라인", "골드라인"),
    "위례선 트램": ("위례선 트램", "위례선", "노면전차"),
    "별내선(8호선 연장)": ("별내선", "8호선 연장"),
    "하남선(5호선 연장)": ("하남선", "5호선 연장"),
    "진접선(4호선 연장)": ("진접선", "4호선 연장"),
    "인천도시철도 1호선 검단연장선": ("검단연장선", "검단 연장선"),
    "고양은평선": ("고양은평선", "고양-은평선", "고양 은평선"),
    "강동하남남양주선": ("강동하남남양주선", "강동-하남-남양주선"),
    "송파하남선": ("송파하남선", "송파-하남선"),
    "계양~대장 S-BRT": ("S-BRT", "계양~대장", "계양-대장"),
    "대곡~소사선": ("대곡-소사", "대곡~소사", "대곡소사"),
}

EVENT_KEYWORDS = {
    "occupancy_planned_block": (
        "입주예정", "입주 예정", "입주예정월", "입주자모집공고", "공공분양", "예비입주자",
    ),
    "occupancy_first_actual": (
        "첫 입주 시작", "첫 입주를 시작", "첫 입주", "최초 입주", "입주가 시작",
    ),
    "occupancy_first_planned": (
        "최초 입주 예정", "첫 입주 예정", "입주를 시작할 계획", "입주가 이루어지도록 할 계획",
    ),
    "promise_date": (
        "광역교통개선대책", "광역교통 개선대책", "교통대책", "준공 목표", "개통 목표", "개통 예정",
        "완공 예정", "추진할 계획", "확충 추진", "사업 완료",
    ),
    "actual_operation": (
        "개통", "첫 운행", "운행 개시", "운행을 시작", "노선 신설", "노선 개통",
    ),
    "basic_service": (
        "배차간격", "운행간격", "첫차", "막차", "시간표", "운행 횟수", "운행횟수",
    ),
}

PROMISE_VERBS = ("예정", "목표", "추진", "확정", "계획", "완료", "준공", "개통")
DATE_RE = re.compile(
    r"(?:20\d{2}|19\d{2})\s*[.년/-]\s*(?:0?[1-9]|1[0-2])(?:\s*[.월/-]\s*(?:0?[1-9]|[12]\d|3[01]))?\s*(?:일)?"
    r"|(?:20\d{2}|19\d{2})\s*년(?:\s*(?:상반기|하반기|말|초))?"
    r"|(?:20\d{2}|19\d{2})\s*[-/]\s*(?:0?[1-9]|1[0-2])"
)
BLOCK_RE = re.compile(r"(?<![가-힣A-Z0-9])([A-Z]{1,2})\s*[- ]?\s*(\d{1,2}[a-z]?)(?:\s*BL|\s*블록)?", re.I)


def norm(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
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


def zone_urls(path: Path) -> tuple[str, str]:
    try:
        zone = Path(f"{path}:Zone.Identifier").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "", ""
    host = re.search(r"^HostUrl=(.+)$", zone, flags=re.M)
    referrer = re.search(r"^ReferrerUrl=(.+)$", zone, flags=re.M)
    return (host.group(1).strip() if host else "", referrer.group(1).strip() if referrer else "")


def extract_pdf(path: Path, text_path: Path) -> tuple[str, list[str], int, str]:
    try:
        with pymupdf.open(path) as doc:
            pages = [page.get_text("text") or "" for page in doc]
            page_count = len(doc)
        text = "\n\n".join(pages)
        text_path.write_text(text, encoding="utf-8", errors="ignore")
        status = "success" if norm(text) else "empty_text"
        return text, pages, page_count, status
    except Exception as exc:  # retain the failure in the inventory
        return "", [], 0, f"error:{exc.__class__.__name__}"


def find_developments(text: str) -> list[str]:
    compact = norm(text)
    found = []
    for development, patterns in DEVELOPMENT_PATTERNS.items():
        if any(norm(pattern) in compact for pattern in patterns):
            found.append(development)
    return found


def find_lines(text: str) -> list[str]:
    compact = norm(text)
    found = []
    for line, patterns in LINE_PATTERNS.items():
        if any(norm(pattern) in compact for pattern in patterns):
            found.append(line)
    return found


def page_excerpt(pages: list[str], keywords: Iterable[str], width: int = 360) -> tuple[str, str]:
    for page_number, page in enumerate(pages, 1):
        compact = norm(page)
        for keyword in keywords:
            key = norm(keyword)
            if key and key in compact:
                raw_index = page.find(keyword)
                if raw_index < 0:
                    # Find a nearby Korean token when spacing differs.
                    token = re.sub(r"\s+", "", keyword)[:4]
                    raw_index = page.find(token)
                raw_index = max(0, raw_index)
                start = max(0, raw_index - width // 3)
                excerpt = re.sub(r"\s+", " ", page[start : start + width]).strip()
                return f"PDF p.{page_number}", excerpt
    return "", ""


def event_types_for(filename: str, text: str) -> list[str]:
    haystack = f"{filename}\n{text}"
    events = []
    for event_type, keywords in EVENT_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            events.append(event_type)
    # 모집공고의 일반적인 '입주' 문구가 district first actual로 오분류되지 않도록 제한한다.
    if "입주자모집" in haystack and "occupancy_first_actual" in events:
        first_terms = ("첫 입주 시작", "첫 입주를 시작", "최초 입주")
        if not any(term in haystack for term in first_terms):
            events.remove("occupancy_first_actual")
    return events


def date_candidates(text: str, limit: int = 12) -> list[str]:
    values = []
    for match in DATE_RE.finditer(text):
        value = re.sub(r"\s+", " ", match.group(0)).strip(" .")
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return values


def block_names(filename: str, text: str) -> list[str]:
    source = f"{filename}\n{text[:6000]}"
    values = []
    for prefix, number in BLOCK_RE.findall(source):
        value = f"{prefix.upper()}-{number}"
        if value not in values:
            values.append(value)
    return values[:8]


def publisher_guess(filename: str, text: str, url: str) -> str:
    haystack = f"{filename} {text[:5000]} {url}"
    candidates = (
        ("국토교통부", ("국토교통부", "molit.go.kr")),
        ("한국토지주택공사", ("한국토지주택공사", "LH 청약", "apply.lh.or.kr")),
        ("경기주택도시공사", ("경기주택도시공사", "gh.or.kr")),
        ("서울특별시", ("서울특별시", "seoul.go.kr")),
        ("하남시", ("하남시청", "hanam.go.kr")),
        ("남양주시", ("남양주시", "nyj.go.kr")),
        ("인천광역시", ("인천광역시", "incheon.go.kr")),
        ("경기도", ("경기도", "gg.go.kr")),
        ("김포시", ("김포시", "gimpo.go.kr")),
        ("연합뉴스", ("연합뉴스", "yna.co.kr")),
    )
    for publisher, patterns in candidates:
        if any(pattern in haystack for pattern in patterns):
            return publisher
    return ""


def published_date_guess(filename: str, text: str) -> str:
    for pattern in (
        re.compile(r"(?<!\d)(20\d{2})[.\-/년]\s*(0?[1-9]|1[0-2])[.\-/월]\s*(0?[1-9]|[12]\d|3[01])"),
        re.compile(r"(?<!\d)(\d{2})(0[1-9]|1[0-2])([0-3]\d)(?!\d)"),
    ):
        match = pattern.search(f"{filename}\n{text[:3000]}")
        if not match:
            continue
        year, month, day = match.groups()
        if len(year) == 2:
            year = f"20{year}"
        try:
            return datetime(int(year), int(month), int(day)).date().isoformat()
        except ValueError:
            continue
    return ""


def main() -> None:
    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    registry = read_csv(REGISTRY_PATH)
    registry_hashes: dict[str, list[str]] = defaultdict(list)
    registry_names: dict[str, list[str]] = defaultdict(list)
    registry_excerpts: list[tuple[str, str]] = []
    for row in registry:
        source_id = row.get("source_id", "")
        for field in ("sha256", "attachment_sha256"):
            value = (row.get(field) or "").lower()
            if value:
                registry_hashes[value].append(source_id)
        for field in ("local_path", "attachment_local_path"):
            value = row.get(field) or ""
            if value:
                registry_names[Path(value).name].append(source_id)
        excerpt = norm(row.get("exact_excerpt", ""))
        if len(excerpt) >= 35:
            registry_excerpts.append((source_id, excerpt))

    inventory: list[dict[str, object]] = []
    matches: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    first_by_hash: dict[str, str] = {}
    pdfs = sorted(
        RAW_DIR.rglob("*.pdf"),
        key=lambda value: str(value.relative_to(RAW_DIR)).casefold(),
    )

    for index, path in enumerate(pdfs, 1):
        raw = path.read_bytes()
        sha256 = hashlib.sha256(raw).hexdigest()
        pdf_id = f"PDF-{index:03d}"
        duplicate_of = first_by_hash.get(sha256, "")
        first_by_hash.setdefault(sha256, pdf_id)
        text_path = TEXT_DIR / f"{sha256}.txt"
        if duplicate_of and text_path.exists():
            text = text_path.read_text(encoding="utf-8", errors="ignore")
            try:
                with pymupdf.open(path) as doc:
                    pages = [page.get_text("text") or "" for page in doc]
                    page_count = len(doc)
                extraction_status = "duplicate_reused"
            except Exception as exc:
                pages, page_count = [], 0
                extraction_status = f"error:{exc.__class__.__name__}"
        else:
            text, pages, page_count, extraction_status = extract_pdf(path, text_path)
            ocr_path = TEXT_DIR / f"{sha256}.ocr.txt"
            if extraction_status == "empty_text" and ocr_path.exists():
                text = ocr_path.read_text(encoding="utf-8", errors="ignore")
                pages = re.split(r"(?m)^=== PDF p\.\d+ ===\s*$", text)[1:]
                extraction_status = "ocr_success" if norm(text) else "ocr_empty"
                text_path = ocr_path

        host_url, referrer_url = zone_urls(path)
        hash_matches = sorted(set(registry_hashes.get(sha256, [])))
        name_matches = sorted(set(registry_names.get(path.name, [])))
        excerpt_matches = []
        compact_text = norm(text)
        if compact_text:
            for source_id, excerpt in registry_excerpts:
                if excerpt in compact_text:
                    excerpt_matches.append(source_id)
        all_matches = sorted(set(hash_matches + name_matches + excerpt_matches))
        developments = find_developments(f"{path.name}\n{text}")
        lines = find_lines(f"{path.name}\n{text}")
        events = event_types_for(path.name, text)
        dates = date_candidates(text)
        blocks = block_names(path.name, text)
        source_url = host_url
        if not source_url and all_matches:
            matched_rows = [row for row in registry if row.get("source_id") in all_matches]
            source_url = next((row.get("attachment_source_url") for row in matched_rows if row.get("attachment_source_url")), "")
            source_url = source_url or next((row.get("source_url") for row in matched_rows if row.get("source_url")), "")

        inventory.append({
            "pdf_id": pdf_id,
            "filename": path.name,
            "raw_path": str(path),
            "sha256": sha256,
            "bytes": len(raw),
            "page_count": page_count,
            "text_chars": len(text),
            "extraction_status": extraction_status,
            "text_path": str(text_path),
            "duplicate_of_pdf_id": duplicate_of,
            "source_url": source_url,
            "referrer_url": referrer_url,
            "publisher_guess": publisher_guess(path.name, text, source_url),
            "published_date_guess": published_date_guess(path.name, text),
            "developments": ";".join(developments),
            "candidate_event_types": ";".join(events),
            "line_names": ";".join(lines),
            "block_names": ";".join(blocks),
            "date_candidates": ";".join(dates),
            "registry_source_ids": ";".join(all_matches),
            "coverage_status": "duplicate" if duplicate_of else ("matched" if all_matches else "unmatched"),
            "scope_status": "relevant_candidate" if developments and events else "out_of_scope_candidate",
        })

        match_types = {
            "hash": hash_matches,
            "filename": name_matches,
            "exact_excerpt": sorted(set(excerpt_matches)),
        }
        for match_type, source_ids in match_types.items():
            for source_id in source_ids:
                matches.append({
                    "pdf_id": pdf_id,
                    "filename": path.name,
                    "sha256": sha256,
                    "match_type": match_type,
                    "source_id": source_id,
                })

        for event_type in events:
            page_or_section, excerpt = page_excerpt(pages, EVENT_KEYWORDS[event_type])
            promise_verbs = [verb for verb in PROMISE_VERBS if verb in excerpt]
            candidates.append({
                "candidate_id": f"{pdf_id}-{event_type}",
                "pdf_id": pdf_id,
                "filename": path.name,
                "sha256": sha256,
                "duplicate_of_pdf_id": duplicate_of,
                "development_candidates": ";".join(developments),
                "event_type": event_type,
                "published_date_guess": published_date_guess(path.name, text),
                "event_date_candidates": ";".join(dates),
                "mode": "rail" if any("선" in line or "GTX" in line for line in lines) else ("tram" if "위례선 트램" in lines else ("sbrt" if "계양~대장 S-BRT" in lines else "")),
                "line_names": ";".join(lines),
                "scope": "block" if blocks and event_type == "occupancy_planned_block" else ("district" if developments else ""),
                "block_names": ";".join(blocks),
                "promise_verb_원문표기": ";".join(promise_verbs),
                "page_or_section": page_or_section,
                "exact_excerpt": excerpt,
                "source_url": source_url,
                "publisher_guess": publisher_guess(path.name, text, source_url),
                "registry_source_ids": ";".join(all_matches),
                "review_status": "duplicate" if duplicate_of else "needs_human",
            })

    write_csv(
        STAGED_DIR / "pdf_inventory.csv",
        inventory,
        [
            "pdf_id", "filename", "raw_path", "sha256", "bytes", "page_count", "text_chars",
            "extraction_status", "text_path", "duplicate_of_pdf_id", "source_url", "referrer_url",
            "publisher_guess", "published_date_guess", "developments", "candidate_event_types",
            "line_names", "block_names", "date_candidates", "registry_source_ids", "coverage_status", "scope_status",
        ],
    )
    write_csv(
        STAGED_DIR / "pdf_registry_matches.csv",
        matches,
        ["pdf_id", "filename", "sha256", "match_type", "source_id"],
    )
    write_csv(
        STAGED_DIR / "pdf_event_candidates.csv",
        candidates,
        [
            "candidate_id", "pdf_id", "filename", "sha256", "duplicate_of_pdf_id",
            "development_candidates", "event_type", "published_date_guess", "event_date_candidates",
            "mode", "line_names", "scope", "block_names", "promise_verb_원문표기", "page_or_section",
            "exact_excerpt", "source_url", "publisher_guess", "registry_source_ids", "review_status",
        ],
    )

    extraction_counts = Counter(row["extraction_status"] for row in inventory)
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "raw_directory": str(RAW_DIR),
        "pdf_files": len(inventory),
        "unique_pdf_hashes": len({row["sha256"] for row in inventory}),
        "duplicate_file_copies": sum(bool(row["duplicate_of_pdf_id"]) for row in inventory),
        "text_extraction": dict(sorted(extraction_counts.items())),
        "empty_or_error": sum(row["extraction_status"] == "empty_text" or str(row["extraction_status"]).startswith("error:") for row in inventory),
        "matched_files": sum(row["coverage_status"] == "matched" for row in inventory),
        "unmatched_unique_files": sum(row["coverage_status"] == "unmatched" for row in inventory),
        "relevant_unique_files": sum(not row["duplicate_of_pdf_id"] and row["scope_status"] == "relevant_candidate" for row in inventory),
        "out_of_scope_unique_files": sum(not row["duplicate_of_pdf_id"] and row["scope_status"] == "out_of_scope_candidate" for row in inventory),
        "event_candidate_rows": len(candidates),
        "inventory_csv": str(STAGED_DIR / "pdf_inventory.csv"),
        "matches_csv": str(STAGED_DIR / "pdf_registry_matches.csv"),
        "event_candidates_csv": str(STAGED_DIR / "pdf_event_candidates.csv"),
    }
    (STAGED_DIR / "pdf_extraction_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
