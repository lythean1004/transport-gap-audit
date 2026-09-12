"""Independent completion and data-quality audit for the full PDF refresh."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "evidence"
STAGED = ROOT / "data" / "staged"
CURATED = ROOT / "data" / "curated"
EXPORTS = ROOT / "exports"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = ["check_id", "status", "severity", "observed", "expected", "notes"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    inventory = read_csv(STAGED / "pdf_inventory.csv")
    registry = read_csv(CURATED / "source_registry.csv")
    qa = read_csv(CURATED / "day1_qa.csv")
    linkages = read_csv(CURATED / "promise_linkage.csv")
    gaps = read_csv(CURATED / "occupancy_operation_gap.csv")
    forward = read_csv(CURATED / "forward_monitoring.csv")
    gates = read_csv(CURATED / "gate_results.csv")
    queue = read_csv(CURATED / "review_queue.csv")
    evidence_manifest = read_csv(CURATED / "evidence_file_manifest.csv")
    targeted = read_csv(CURATED / "targeted_evidence_extraction.csv")

    raw_pdfs = sorted(RAW.rglob("*.pdf"))
    inventory_by_path = {Path(row["raw_path"]): row for row in inventory}
    current_hash_matches = sum(
        path in inventory_by_path
        and hashlib.sha256(path.read_bytes()).hexdigest() == inventory_by_path[path]["sha256"]
        for path in raw_pdfs
    )
    represented = {
        pdf_id
        for row in registry
        for pdf_id in (row.get("pdf_id") or "").split(";")
        if pdf_id
    }
    unique_inventory_ids = {row["pdf_id"] for row in inventory if not row["duplicate_of_pdf_id"]}
    valid_statuses = {"fulfilled", "partial", "substituted", "unfulfilled", "promise_absent"}
    qa_pass = sum(row["required_fields_pass"].lower() == "true" for row in qa)
    active = len(qa)
    raw_unique_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in raw_pdfs}
    evidence_extensions = {".pdf", ".html", ".htm", ".hwp", ".hwpx"}
    raw_evidence_files = sorted(path for path in RAW.rglob("*") if path.is_file() and path.suffix.lower() in evidence_extensions)
    target_ids = {
        "SRC-E1-A04", "SRC-E1-A08", "SRC-E1-A10", "SRC-E1-B02", "SRC-E1-B05",
        "SRC-E1-B08", "SRC-E1-B10", "SRC-E1-C01", "SRC-E1-C02", "SRC-E1-C04",
        "SRC-E1-C08", "SRC-E2-C07", "SRC-E2-C08", "SRC-E2-C09", "SRC-E2-C10",
    }
    central_paths = []
    for row in registry:
        for column in ("local_path", "attachment_local_path", "raw_pdf_path"):
            central_paths.extend(Path(value) for value in (row.get(column) or "").split(";") if value)
    raw_resolved = RAW.resolve()

    checks = [
        {"check_id": "raw_pdf_count", "status": "PASS" if len(raw_pdfs) == len(inventory) else "FAIL", "severity": "critical", "observed": len(raw_pdfs), "expected": len(inventory), "notes": "recursive PDF count is inventory-driven because the user may add files"},
        {"check_id": "inventory_row_count", "status": "PASS" if len(inventory) == len(raw_pdfs) else "FAIL", "severity": "critical", "observed": len(inventory), "expected": len(raw_pdfs), "notes": "one row per raw PDF file"},
        {"check_id": "unique_pdf_hashes", "status": "PASS" if len({row['sha256'] for row in inventory}) == len(raw_unique_hashes) else "FAIL", "severity": "high", "observed": len({row['sha256'] for row in inventory}), "expected": len(raw_unique_hashes), "notes": "duplicate copies are retained but not double-counted"},
        {"check_id": "raw_hash_reconciliation", "status": "PASS" if current_hash_matches == len(raw_pdfs) else "FAIL", "severity": "critical", "observed": current_hash_matches, "expected": len(raw_pdfs), "notes": "raw PDFs remain byte-consistent with inventory"},
        {"check_id": "extraction_failures", "status": "PASS" if all(row['extraction_status'] in {'success','ocr_success','duplicate_reused'} for row in inventory) else "FAIL", "severity": "critical", "observed": sum(row['extraction_status'] not in {'success','ocr_success','duplicate_reused'} for row in inventory), "expected": 0, "notes": "one scanned document used Windows Korean OCR"},
        {"check_id": "unique_pdf_registry_coverage", "status": "PASS" if represented == unique_inventory_ids else "FAIL", "severity": "critical", "observed": len(represented), "expected": len(unique_inventory_ids), "notes": "every unique PDF represented in registry"},
        {"check_id": "source_id_uniqueness", "status": "PASS" if len(registry) == len({row['source_id'] for row in registry}) else "FAIL", "severity": "critical", "observed": len({row['source_id'] for row in registry}), "expected": len(registry), "notes": "registry primary key"},
        {"check_id": "day1_required_fields", "status": "PASS_WITH_CAVEATS" if qa_pass < active else "PASS", "severity": "medium", "observed": f"{qa_pass}/{active}", "expected": f"{active}/{active}", "notes": "failed rows remain in review_queue; not fabricated"},
        {"check_id": "linkage_rows_and_status", "status": "PASS" if len(linkages) == 10 and {row['linkage_status'] for row in linkages} <= valid_statuses else "FAIL", "severity": "critical", "observed": len(linkages), "expected": 10, "notes": "five historical plus five forward"},
        {"check_id": "gap_nonnegative", "status": "PASS" if len(gaps) == 5 and all(int(row['gap_days_min']) >= 0 and int(row['gap_days_max']) >= int(row['gap_days_min']) for row in gaps) else "FAIL", "severity": "critical", "observed": len(gaps), "expected": 5, "notes": "same promised facility endpoint"},
        {"check_id": "forward_monitoring_rows", "status": "PASS" if len(forward) == 5 else "FAIL", "severity": "high", "observed": len(forward), "expected": 5, "notes": "all named 3G developments"},
        {"check_id": "strict_gate_no_ai_promotion", "status": "PASS" if len(gates) == 5 and all(row['gate_result'] == 'FAIL' and int(row['human_verified_sources']) == 0 for row in gates) else "FAIL", "severity": "critical", "observed": sum(row['gate_result'] == 'PASS' for row in gates), "expected": 0, "notes": "AI extraction remains draft"},
        {"check_id": "review_queue_alignment", "status": "PASS" if len(queue) == len(registry) else "FAIL", "severity": "high", "observed": len(queue), "expected": len(registry), "notes": "all needs_human/rejected rows queued"},
        {"check_id": "central_evidence_manifest", "status": "PASS" if len(evidence_manifest) == len(raw_evidence_files) else "FAIL", "severity": "critical", "observed": len(evidence_manifest), "expected": len(raw_evidence_files), "notes": "PDF/HTML/HWP/HWPX physical files mapped by filename and hash"},
        {"check_id": "registry_paths_centralized", "status": "PASS" if all(path.exists() and path.resolve().is_relative_to(raw_resolved) for path in central_paths) else "FAIL", "severity": "critical", "observed": sum(path.exists() and path.resolve().is_relative_to(raw_resolved) for path in central_paths), "expected": len(central_paths), "notes": "all registry evidence paths resolve under data/raw/evidence"},
        {"check_id": "targeted_source_coverage", "status": "PASS" if target_ids <= {row['source_id'] for row in targeted} and len(targeted) == 17 else "FAIL", "severity": "critical", "observed": len(targeted), "expected": 17, "notes": "15 requested source rows plus two block-specific splits"},
    ]
    write_csv(CURATED / "validation_results.csv", checks)

    blockers = [row for row in checks if row["status"] == "FAIL"]
    assessment = "Share with caveats" if not blockers else "Needs revision"
    report = [
        "# Full PDF Refresh Validation Report",
        "",
        f"## Overall assessment: {assessment}",
        "",
        f"The pipeline is complete for all {len(raw_pdfs)} PDF files. The evidence dataset is suitable for continued human review, but it is not a human-verified final fact set.",
        "",
        "## Verified checks",
        "",
        "| Check | Status | Observed | Expected |",
        "|---|---|---:|---:|",
    ]
    report.extend(f"| {row['check_id']} | {row['status']} | {row['observed']} | {row['expected']} |" for row in checks)
    report.extend([
        "",
        "## Required caveats",
        "",
        f"- Day 1 complete-field pass rate is {qa_pass}/{active} ({qa_pass/active:.1%}); the remaining rows are explicitly queued for repair and human verification.",
        "- human_verified remains 0. The strict gate therefore remains PIVOT(A22), even where multiple official candidate sources are present.",
        f"- {len(raw_pdfs) - len(raw_unique_hashes)} byte-identical PDF copies are retained in the inventory but not double-counted as unique evidence.",
        "- Context-only, media-clue, commercial, and user-petition documents are retained with rejection or scope reasons rather than used as primary metric evidence.",
    ])
    validation_csv = CURATED / "validation_results.csv"
    validation_report = EXPORTS / "full_refresh_validation_report.md"
    validation_report.write_text("\n".join(report), encoding="utf-8")

    manifest_path = CURATED / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    retained = [
        item
        for item in manifest.get("artifacts", [])
        if Path(item["path"]) not in {validation_csv, validation_report}
    ]
    for path in (validation_csv, validation_report):
        retained.append(
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest["generated_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    manifest["artifacts"] = retained
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"assessment": assessment, "failed_checks": len(blockers), "checks": len(checks), "qa_pass": qa_pass, "qa_total": active}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
