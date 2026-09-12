# Full PDF Refresh Validation Report

## Overall assessment: Share with caveats

The pipeline is complete for all 112 PDF files. The evidence dataset is suitable for continued human review, but it is not a human-verified final fact set.

## Verified checks

| Check | Status | Observed | Expected |
|---|---|---:|---:|
| raw_pdf_count | PASS | 112 | 112 |
| inventory_row_count | PASS | 112 | 112 |
| unique_pdf_hashes | PASS | 92 | 92 |
| raw_hash_reconciliation | PASS | 112 | 112 |
| extraction_failures | PASS | 0 | 0 |
| unique_pdf_registry_coverage | PASS | 92 | 92 |
| source_id_uniqueness | PASS | 197 | 197 |
| day1_required_fields | PASS_WITH_CAVEATS | 117/180 | 180/180 |
| linkage_rows_and_status | PASS | 10 | 10 |
| gap_nonnegative | PASS | 5 | 5 |
| forward_monitoring_rows | PASS | 5 | 5 |
| strict_gate_no_ai_promotion | PASS | 0 | 0 |
| review_queue_alignment | PASS | 197 | 197 |
| central_evidence_manifest | PASS | 237 | 237 |
| registry_paths_centralized | PASS | 366 | 366 |
| targeted_source_coverage | PASS | 17 | 17 |

## Required caveats

- Day 1 complete-field pass rate is 117/180 (65.0%); the remaining rows are explicitly queued for repair and human verification.
- human_verified remains 0. The strict gate therefore remains PIVOT(A22), even where multiple official candidate sources are present.
- 20 byte-identical PDF copies are retained in the inventory but not double-counted as unique evidence.
- Context-only, media-clue, commercial, and user-petition documents are retained with rejection or scope reasons rather than used as primary metric evidence.