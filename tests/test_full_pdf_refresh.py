import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "evidence"
STAGED = ROOT / "data" / "staged"
CURATED = ROOT / "data" / "curated"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_all_raw_pdfs_are_in_inventory_and_hashes_still_match():
    inventory = read_csv(STAGED / "pdf_inventory.csv")
    raw_pdfs = sorted(RAW.rglob("*.pdf"))
    assert raw_pdfs
    assert len(inventory) == len(raw_pdfs)
    by_path = {(ROOT / row["raw_path"]).resolve(): row for row in inventory}
    for path in raw_pdfs:
        assert path in by_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == by_path[path]["sha256"]


def test_every_pdf_extracted_or_duplicate_reused():
    inventory = read_csv(STAGED / "pdf_inventory.csv")
    allowed = {"success", "ocr_success", "duplicate_reused"}
    assert {row["extraction_status"] for row in inventory} <= allowed
    assert sum(row["extraction_status"] == "ocr_success" for row in inventory) == 1
    assert sum(bool(row["duplicate_of_pdf_id"]) for row in inventory) == len(inventory) - len({row["sha256"] for row in inventory})


def test_every_unique_pdf_is_represented_in_registry():
    inventory = read_csv(STAGED / "pdf_inventory.csv")
    registry = read_csv(CURATED / "source_registry.csv")
    represented = {
        pdf_id
        for row in registry
        for pdf_id in (row.get("pdf_id") or "").split(";")
        if pdf_id
    }
    unique_pdf_ids = {row["pdf_id"] for row in inventory if not row["duplicate_of_pdf_id"]}
    assert unique_pdf_ids == represented


def test_registry_keys_and_allowed_linkage_statuses():
    registry = read_csv(CURATED / "source_registry.csv")
    source_ids = [row["source_id"] for row in registry]
    assert len(source_ids) == len(set(source_ids))
    linkages = read_csv(CURATED / "promise_linkage.csv")
    allowed = {"fulfilled", "partial", "substituted", "unfulfilled", "promise_absent"}
    assert len(linkages) == 10
    assert {row["linkage_status"] for row in linkages} <= allowed


def test_wirye_is_not_closed_by_a_different_rail_station():
    linkage = next(row for row in read_csv(CURATED / "promise_linkage.csv") if row["development"] == "위례")
    assert linkage["promise_line_name"] == "위례선 트램"
    assert linkage["actual_source_id"] == ""
    assert linkage["linkage_status"] == "unfulfilled"
    gap = next(row for row in read_csv(CURATED / "occupancy_operation_gap.csv") if row["development"] == "위례")
    assert gap["operation_source_id"] == ""
    assert gap["gap_status"] == "ongoing_as_of_2026-09-02"


def test_gap_ranges_are_nonnegative_and_misa_uses_first_hanam_line_stage():
    gaps = read_csv(CURATED / "occupancy_operation_gap.csv")
    assert len(gaps) == 5
    assert all(int(row["gap_days_min"]) >= 0 and int(row["gap_days_max"]) >= int(row["gap_days_min"]) for row in gaps)
    misa = next(row for row in gaps if row["development"] == "하남 미사")
    assert misa["operation_source_id"] == "SRC-H029"
    assert misa["operation_event_date"] == "2020-08-08"


def test_basic_service_uses_timetable_effective_date_when_qa_passes():
    registry = {row["source_id"]: row for row in read_csv(CURATED / "source_registry.csv")}
    qa_pass_ids = {
        row["source_id"]
        for row in read_csv(CURATED / "day1_qa.csv")
        if row["required_fields_pass"].lower() == "true"
    }
    passed_service = [row for source_id, row in registry.items() if source_id in qa_pass_ids and row["event_type"] == "basic_service"]
    assert passed_service
    for row in passed_service:
        assert row["event_date"] == row["timetable_effective_date"]
        assert row["service_headway"] or row["service_first"] or row["service_last"]


def test_strict_gate_does_not_promote_ai_extraction():
    gates = read_csv(CURATED / "gate_results.csv")
    assert len(gates) == 5
    assert all(row["gate_result"] == "FAIL" for row in gates)
    assert all(int(row["human_verified_sources"]) == 0 for row in gates)


def test_key_correction_chains_have_one_latest_version():
    registry = read_csv(CURATED / "source_registry.csv")
    checks = [("인천 계양", "A2", "SRC-E2-A06"), ("하남 교산", "A2", "SRC-U002")]
    for development, block, expected_latest in checks:
        normalized = block.replace("-", "").upper()
        versions = [
            row for row in registry
            if row["development"] == development
            and row["event_type"] == "occupancy_planned_block"
            and any(value.replace("-", "").upper() == normalized for value in row["block_name"].split(";") if value)
        ]
        latest = [row for row in versions if row["version_status"] == "latest"]
        assert len(latest) == 1
        assert latest[0]["source_id"] == expected_latest


def test_targeted_refresh_has_all_requested_and_split_block_rows():
    rows = read_csv(CURATED / "targeted_evidence_extraction.csv")
    requested = {
        "SRC-E1-A04", "SRC-E1-A08", "SRC-E1-A10", "SRC-E1-B02", "SRC-E1-B05",
        "SRC-E1-B08", "SRC-E1-B10", "SRC-E1-C01", "SRC-E1-C02", "SRC-E1-C04",
        "SRC-E1-C08", "SRC-E2-C07", "SRC-E2-C08", "SRC-E2-C09", "SRC-E2-C10",
    }
    assert requested <= {row["source_id"] for row in rows}
    assert {"SRC-E1-A10-A25", "SRC-E2-C09-S3"} <= {row["source_id"] for row in rows}
    assert len(rows) == 17


def test_targeted_refresh_preserves_precision_and_rejects_mismatches():
    rows = {row["source_id"]: row for row in read_csv(CURATED / "targeted_evidence_extraction.csv")}
    assert rows["SRC-E1-A10"]["event_date"] == "2018-11"
    assert rows["SRC-E1-A10-A25"]["event_date"] == "2018-10"
    assert rows["SRC-E2-C09"]["event_date"] == "2030-03"
    assert rows["SRC-E2-C09-S3"]["event_date"] == "2030-02"
    assert rows["SRC-E1-A08"]["date_precision"] == "unknown"
    assert rows["SRC-E1-A08"]["event_date"] == ""
    for source_id in ("SRC-E1-B05", "SRC-E1-B10", "SRC-E1-C01", "SRC-E1-C02", "SRC-E1-C04", "SRC-E2-C10"):
        assert rows[source_id]["review_status"] == "rejected"


def test_evidence_log_has_required_reproducibility_columns_and_stable_ids():
    rows = read_csv(CURATED / "evidence_log.csv")
    required = {
        "evidence_id", "claim_type", "exact_excerpt", "page_or_section", "date_precision",
        "event_date_lower", "event_date_upper", "confidence", "review_status", "sha256",
    }
    assert required <= set(rows[0])
    assert len({row["evidence_id"] for row in rows}) == len(rows)
    assert all(row["evidence_id"] == "EV-" + row["source_id"].removeprefix("SRC-") for row in rows)


def test_central_evidence_manifest_covers_every_source_file_and_hashes_match():
    manifest = read_csv(CURATED / "evidence_file_manifest.csv")
    extensions = {".pdf", ".html", ".htm", ".hwp", ".hwpx"}
    raw_files = sorted(path for path in RAW.rglob("*") if path.is_file() and path.suffix.lower() in extensions)
    assert len(manifest) == len(raw_files)
    by_path = {row["archive_relative_path"]: row for row in manifest}
    for path in raw_files:
        relative = str(path.relative_to(RAW))
        assert relative in by_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == by_path[relative]["sha256"]


def test_registry_local_evidence_paths_are_centralized():
    raw_resolved = RAW.resolve()
    for row in read_csv(CURATED / "source_registry.csv"):
        for column in ("local_path", "attachment_local_path", "raw_pdf_path"):
            for value in (row.get(column) or "").split(";"):
                if not value:
                    continue
                path = Path(value).resolve()
                assert path.exists()
                assert path.is_relative_to(raw_resolved)
