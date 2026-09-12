"""Unit tests for evidence verifier logic."""

import pytest
pytest.importorskip("html2text")

import pathlib
from src.collectors.evidence_verifier import (
    norm,
    extract_text_from_html,
    resolve_candidate_file,
    read_candidate_rows,
)


def test_norm():
    # Test whitespace and smart quote normalization
    text1 = '“동탄(2)지구,  첫 입주 시작”'
    text2 = '"동탄(2)지구,첫입주시작"'
    assert norm(text1) == norm(text2)
    assert norm(None) == ""
    assert norm("   앞뒤 공백   ") == "앞뒤공백"


def test_extract_text_from_html(tmp_path: pathlib.Path):
    html_content = "<html><body><h1>공약 발표</h1><p>2026년 하반기 개통 목표</p></body></html>"
    html_file = tmp_path / "test.html"
    txt_file = tmp_path / "test.txt"
    html_file.write_text(html_content, encoding="utf-8")

    text = extract_text_from_html(html_file, txt_file)
    assert "2026년 하반기 개통 목표" in text
    assert txt_file.exists()


def test_resolve_candidate_file_psv_to_csv_fallback(tmp_path: pathlib.Path):
    # Create sample.csv only (no .psv)
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("cand_id,development,title\nC01,동탄,제목", encoding="utf-8")

    # Requesting sample.psv should automatically resolve to sample.csv
    resolved = resolve_candidate_file(tmp_path / "sample.psv", base_dir=tmp_path)
    assert resolved == csv_file
    assert resolved.exists()


def test_read_candidate_rows(tmp_path: pathlib.Path):
    # CSV file
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text("cand_id,development,title\nC01,위례,위례선 개통", encoding="utf-8-sig")
    rows_csv = read_candidate_rows(csv_file)
    assert len(rows_csv) == 1
    assert rows_csv[0]["cand_id"] == "C01"
    assert rows_csv[0]["development"] == "위례"

    # PSV file
    psv_file = tmp_path / "test_data.psv"
    psv_file.write_text("cand_id|development|title\nP01|동탄|GTX-A 개통", encoding="utf-8")
    rows_psv = read_candidate_rows(psv_file)
    assert len(rows_psv) == 1
    assert rows_psv[0]["cand_id"] == "P01"
    assert rows_psv[0]["development"] == "동탄"
