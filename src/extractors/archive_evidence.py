"""Centralize source evidence and build reproducible filename/SHA-256 maps."""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "evidence"
CURATED = ROOT / "data" / "curated"
STAGED = ROOT / "data" / "staged"
REGISTRY_PATH = CURATED / "source_registry.csv"
LEGACY_DOCS = ROOT / "evidence" / "documents"
RETRIEVED_DATE = "2026-09-02"

TARGET_URLS = {
    "SRC-E1-A04": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=0000061160&ccrCnntSysDsCd=02&uppAisTpCd=06&aisTpCd=08&mi=1026",
    "SRC-E1-A08": "https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId=6410",
    "SRC-E1-A10": "https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId=920",
    "SRC-E1-B02": "https://www.molit.go.kr/USR/NEWS/m_71/dtl.jsp?id=95086846",
    "SRC-E1-B05": "https://www.molit.go.kr/mta/USR/N0201/m_36770/dtl.jsp?lcmspage=1&id=95087500",
    "SRC-E1-B08": "https://www.korea.kr/news/policyNewsView.do?newsId=148931611",
    "SRC-E1-B10": "https://www.korea.kr/briefing/policyBriefingView.do?newsId=148775695",
    "SRC-E1-C08": "https://www.nyj.go.kr/www/selectBbsNttView.do?key=2498&bbsNo=68&pageIndex=405&pageUnit=8&searchCnd=all&nttNo=432164",
    "SRC-E2-C08": "https://www.myhome.go.kr/hws/portal/bbs/selectBoardHappyNewsDetailView.do?nttId=797",
    "SRC-E2-C09": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=0000061134&ccrCnntSysDsCd=02&uppAisTpCd=05&aisTpCd=05&mi=1027",
    "SRC-E2-C10": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=0000060706&ccrCnntSysDsCd=02&uppAisTpCd=05&aisTpCd=05&mi=1027",
}

EVIDENCE_EXTENSIONS = {".pdf", ".html", ".htm", ".hwp", ".hwpx"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value).strip("._")


def download_targets() -> dict[str, Path]:
    dest = RAW / "documents" / f"target_refresh_{RETRIEVED_DATE.replace('-', '')}"
    dest.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 evidence-archive/1.0"})
    for source_id, url in TARGET_URLS.items():
        path = dest / f"{source_id}_{RETRIEVED_DATE}.html"
        response = session.get(url, timeout=60)
        response.raise_for_status()
        body = response.content
        if len(body) < 200 or b"<html" not in body[:5000].lower():
            raise RuntimeError(f"invalid HTML response for {source_id}: {len(body)} bytes")
        path.write_bytes(body)
        saved[source_id] = path
    return saved


def centralize_legacy_documents() -> None:
    if not LEGACY_DOCS.exists():
        return
    destination = RAW / "documents"
    for source in LEGACY_DOCS.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(LEGACY_DOCS)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256(target) != sha256(source):
                raise RuntimeError(f"archive collision: {target}")
            continue
        shutil.copy2(source, target)


def centralize_registry_references(rows: list[dict[str, str]]) -> None:
    raw_resolved = RAW.resolve()
    for row in rows:
        source_id = row.get("source_id", "UNASSIGNED")
        for column in ("local_path", "attachment_local_path", "raw_pdf_path"):
            for value in (row.get(column) or "").split(";"):
                value = value.strip()
                if not value:
                    continue
                source = Path(value)
                if not source.exists() or not source.is_file():
                    continue
                try:
                    source.resolve().relative_to(raw_resolved)
                    continue
                except ValueError:
                    pass
                if LEGACY_DOCS in source.parents:
                    relative = source.relative_to(LEGACY_DOCS)
                    target = RAW / "documents" / relative
                else:
                    target = RAW / "imported" / safe_name(source_id) / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if sha256(target) != sha256(source):
                        target = target.with_name(f"{target.stem}_{sha256(source)[:12]}{target.suffix}")
                if not target.exists():
                    shutil.copy2(source, target)


def write_rows(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def normalize_registry_paths(
    registry_rows: list[dict[str, str]], canonical_by_hash: dict[str, Path]
) -> int:
    changed = 0
    bindings = (
        ("sha256", "local_path"),
        ("attachment_sha256", "attachment_local_path"),
        ("pdf_sha256", "raw_pdf_path"),
    )
    for row in registry_rows:
        for hash_column, path_column in bindings:
            hashes = [value.strip().lower() for value in (row.get(hash_column) or "").split(";") if value.strip()]
            paths = [canonical_by_hash[value] for value in hashes if value in canonical_by_hash]
            if not paths:
                continue
            replacement = ";".join(str(path) for path in paths)
            if row.get(path_column, "") != replacement:
                row[path_column] = replacement
                changed += 1
    if registry_rows:
        fields = list(registry_rows[0])
        temp = REGISTRY_PATH.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(registry_rows)
        temp.replace(REGISTRY_PATH)
    return changed


def main() -> None:
    registry_rows = read_csv(CURATED / "source_registry.csv") or read_csv(RAW / "source_registry.csv")
    centralize_legacy_documents()
    centralize_registry_references(registry_rows)
    downloaded = download_targets()

    source_by_hash: dict[str, set[str]] = defaultdict(set)
    urls_by_hash: dict[str, set[str]] = defaultdict(set)
    retrieved_by_hash: dict[str, set[str]] = defaultdict(set)
    for row in registry_rows:
        source_id = row.get("source_id", "")
        for hash_column in ("sha256", "attachment_sha256", "pdf_sha256"):
            value = (row.get(hash_column) or "").lower().strip()
            if re.fullmatch(r"[0-9a-f]{64}", value):
                source_by_hash[value].add(source_id)
                for url_column in ("source_url", "attachment_source_url"):
                    url = (row.get(url_column) or "").strip()
                    if url.startswith(("http://", "https://")):
                        urls_by_hash[value].add(url)
                if row.get("retrieved_at"):
                    retrieved_by_hash[value].add(row["retrieved_at"])
    for source_id, path in downloaded.items():
        digest = sha256(path)
        source_by_hash[digest].add(source_id)
        urls_by_hash[digest].add(TARGET_URLS[source_id])
        retrieved_by_hash[digest].add(f"{RETRIEVED_DATE}T00:00:00+09:00")

    files = sorted(
        (p for p in RAW.rglob("*") if p.is_file() and p.suffix.lower() in EVIDENCE_EXTENSIONS),
        key=lambda p: str(p.relative_to(RAW)).casefold(),
    )
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        by_hash[sha256(path)].append(path)

    manifest_rows: list[dict[str, object]] = []
    hash_rows: list[dict[str, object]] = []
    canonical_by_hash: dict[str, Path] = {}
    for digest, paths in sorted(by_hash.items()):
        canonical = min(paths, key=lambda p: (len(p.relative_to(RAW).parts), len(str(p)), str(p).casefold()))
        canonical_by_hash[digest] = canonical
        hash_rows.append({
            "sha256": digest,
            "canonical_relative_path": str(canonical.relative_to(RAW)),
            "file_count": len(paths),
            "filenames": ";".join(sorted({p.name for p in paths})),
            "all_relative_paths": ";".join(str(p.relative_to(RAW)) for p in paths),
            "source_ids": ";".join(sorted(source_by_hash[digest])),
            "source_urls": ";".join(sorted(urls_by_hash[digest])),
            "retrieved_at": ";".join(sorted(retrieved_by_hash[digest])),
        })
        for path in paths:
            relative = path.relative_to(RAW)
            manifest_rows.append({
                "archive_relative_path": str(relative),
                "filename": path.name,
                "extension": path.suffix.lower(),
                "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "bytes": path.stat().st_size,
                "sha256": digest,
                "is_canonical_copy": str(path == canonical).lower(),
                "duplicate_of_relative_path": "" if path == canonical else str(canonical.relative_to(RAW)),
                "source_ids": ";".join(sorted(source_by_hash[digest])),
                "source_urls": ";".join(sorted(urls_by_hash[digest])),
                "retrieved_at": ";".join(sorted(retrieved_by_hash[digest])),
            })

    write_rows(
        STAGED / "evidence_file_manifest.csv",
        manifest_rows,
        ["archive_relative_path", "filename", "extension", "mime_type", "bytes", "sha256", "is_canonical_copy", "duplicate_of_relative_path", "source_ids", "source_urls", "retrieved_at"],
    )
    write_rows(
        STAGED / "evidence_hash_map.csv",
        hash_rows,
        ["sha256", "canonical_relative_path", "file_count", "filenames", "all_relative_paths", "source_ids", "source_urls", "retrieved_at"],
    )
    write_rows(
        CURATED / "evidence_file_manifest.csv",
        manifest_rows,
        ["archive_relative_path", "filename", "extension", "mime_type", "bytes", "sha256", "is_canonical_copy", "duplicate_of_relative_path", "source_ids", "source_urls", "retrieved_at"],
    )
    write_rows(
        CURATED / "evidence_hash_map.csv",
        hash_rows,
        ["sha256", "canonical_relative_path", "file_count", "filenames", "all_relative_paths", "source_ids", "source_urls", "retrieved_at"],
    )
    normalized_paths = normalize_registry_paths(registry_rows, canonical_by_hash)
    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "archive_root": str(RAW),
        "physical_files": len(files),
        "unique_hashes": len(by_hash),
        "duplicate_copies": len(files) - len(by_hash),
        "downloaded_html": len(downloaded),
        "mapped_source_ids": len({sid for values in source_by_hash.values() for sid in values if sid}),
        "normalized_registry_paths": normalized_paths,
    }
    (STAGED / "evidence_archive_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
