import os
import hashlib
import time
import csv
from pathlib import Path
from datetime import datetime
import openpyxl
import polars as pl
import yaml
import logging

from src.logging_utils import setup_logger

logger = setup_logger("kapt_normalizer")

def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def find_newest_kapt_file(raw_dir: Path) -> Path:
    excel_files = list(raw_dir.glob("*.xls*"))
    if not excel_files:
        raise FileNotFoundError(f"No Excel files found in {raw_dir}")
    excel_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return excel_files[0]

def parse_date(raw_val) -> str:
    """Returns YYYY-MM-DD or raises ValueError"""
    if raw_val is None:
        raise ValueError("Null value")
    
    if hasattr(raw_val, "strftime"):
        return raw_val.strftime("%Y-%m-%d")
        
    val_str = str(raw_val).strip()
    if not val_str or val_str in ["-", "null", "NULL"]:
        raise ValueError("Empty or dash")
        
    if len(val_str) == 8 and val_str.isdigit():
        return f"{val_str[:4]}-{val_str[4:6]}-{val_str[6:]}"
        
    if "-" in val_str and len(val_str) == 10:
        # basic check for YYYY-MM-DD
        parts = val_str.split("-")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return val_str
            
    raise ValueError(f"Unparsable date format: {val_str}")

def parse_int(raw_val) -> int:
    """Returns int or raises ValueError"""
    if raw_val is None:
        raise ValueError("Null value")
    val_str = str(raw_val).strip()
    if not val_str or val_str.lower() in ["-", "null", ""]:
        raise ValueError("Empty or dash")
    try:
        return int(float(val_str))
    except (ValueError, TypeError):
        raise ValueError(f"Non-numeric: {val_str}")

def process_kapt(input_path: Path = None, config_path: Path = None, out_dir: Path = None, qa_dir: Path = None):
    start_time = time.time()
    
    if config_path is None:
        config_path = Path("config/kapt_columns.yaml")
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    if input_path is None:
        input_path = find_newest_kapt_file(Path("data/raw/kapt"))
        
    if out_dir is None:
        out_dir = Path("data/staged")
    if qa_dir is None:
        qa_dir = Path("exports")
        
    out_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)
    
    file_sha256 = compute_sha256(input_path)
    
    header_row_idx = config["meta"]["header_row"] - 1
    data_start_row_idx = config["meta"]["data_start_row"] - 1
    mapping = config["mapping"]
    
    # Check if read_only=True works for this file
    # Some K-apt files have broken XML dimensions that cause read_only to yield only 1 row.
    wb_test = openpyxl.load_workbook(input_path, read_only=True, data_only=True)
    ws_test = wb_test.active
    test_count = 0
    for _ in ws_test.iter_rows(values_only=True):
        test_count += 1
        if test_count > 10:
            break
    wb_test.close()
    
    use_read_only = (test_count > 10)
    if not use_read_only:
        logger.warning("read_only=True yielded too few rows (broken XML dimension). Falling back to data_only=True.")
        
    wb = openpyxl.load_workbook(input_path, read_only=use_read_only, data_only=True)
    ws = wb.active
    
    row_iter = ws.iter_rows(values_only=True)
    
    # Skip to header
    all_headers = []
    for i, row in enumerate(row_iter):
        if i == header_row_idx:
            all_headers = [str(c).strip().replace('\n', ' ') if c else None for c in row]
            break
            
    col_idx_map = {}
    for int_name, ext_name in mapping.items():
        for i, h in enumerate(all_headers):
            if h == ext_name:
                col_idx_map[int_name] = i
                break
                
    # Skip to data start
    # We already consumed up to header_row_idx.
    to_skip = data_start_row_idx - header_row_idx - 1
    for _ in range(to_skip):
        next(row_iter, None)
        
    records = []
    qa_records = []
    
    ingested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_caveat = "K-apt 주간 엑셀. 참고자료. 값이 사후 수정될 수 있음."
    kapt_extracted_at = config["meta"].get("kapt_extracted_at", "UNKNOWN")
    
    rows_in = 0
    
    for row in row_iter:
        if not row or not any(row): continue
        rows_in += 1
        
        rec = {}
        qa_reasons = []
        
        # Extract mapped cols
        for int_name, ext_name in mapping.items():
            idx = col_idx_map.get(int_name)
            raw_val = row[idx] if idx is not None and idx < len(row) else None
            
            if int_name == "kapt_code":
                rec["kapt_code"] = str(raw_val).strip() if raw_val is not None else None
            elif int_name == "approval_date":
                rec["approval_date_raw"] = str(raw_val).strip() if raw_val is not None else None
                try:
                    rec["approval_date"] = parse_date(raw_val)
                except ValueError as e:
                    rec["approval_date"] = None
                    if raw_val is not None and str(raw_val).strip() not in ["", "-", "null", "NULL"]:
                        qa_reasons.append(f"unparsable_date: {e}")
            elif int_name in ["household_count", "bldg_count"]:
                try:
                    rec[int_name] = parse_int(raw_val)
                except ValueError as e:
                    rec[int_name] = None
                    if raw_val is not None and str(raw_val).strip() not in ["", "-", "null", "NULL"]:
                        qa_reasons.append(f"non_numeric_{int_name}: {e}")
            else:
                rec[int_name] = str(raw_val).strip() if raw_val is not None else None
                
        # Metadata
        rec["source_file"] = input_path.name
        rec["source_sha256"] = file_sha256
        rec["kapt_extracted_at"] = kapt_extracted_at
        rec["ingested_at"] = ingested_at
        rec["data_caveat"] = data_caveat
        
        records.append(rec)
        
        if qa_reasons:
            qa_rec = {
                "kapt_code": rec.get("kapt_code"),
                "reasons": " | ".join(qa_reasons),
                "approval_date_raw": rec.get("approval_date_raw"),
                "household_count_raw": row[col_idx_map.get("household_count")] if col_idx_map.get("household_count") is not None and col_idx_map.get("household_count") < len(row) else None,
                "bldg_count_raw": row[col_idx_map.get("bldg_count")] if col_idx_map.get("bldg_count") is not None and col_idx_map.get("bldg_count") < len(row) else None
            }
            qa_records.append(qa_rec)
            
    wb.close()
    
    # Save to parquet using Polars
    df = pl.DataFrame(records)
    # Ensure kapt_code is string
    if "kapt_code" in df.columns:
        df = df.with_columns(pl.col("kapt_code").cast(pl.Utf8))
        
    out_parquet = out_dir / "kapt_basic.parquet"
    df.write_parquet(out_parquet)
    
    # Save QA
    qa_csv = qa_dir / "kapt_qa.csv"
    if qa_records:
        with open(qa_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["kapt_code", "reasons", "approval_date_raw", "household_count_raw", "bldg_count_raw"])
            writer.writeheader()
            writer.writerows(qa_records)
    else:
        # Create empty with headers
        with open(qa_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["kapt_code", "reasons", "approval_date_raw", "household_count_raw", "bldg_count_raw"])
            writer.writeheader()
            
    rows_out = len(records)
    
    elapsed = time.time() - start_time
    logger.info(f"K-apt Normalized. File: {input_path.name}")
    logger.info(f"Rows In: {rows_in}, Rows Out: {rows_out}")
    logger.info(f"QA Drops/Issues: {len(qa_records)}")
    logger.info(f"Extraction time: {elapsed:.2f}s")
    
    print(f"Extraction Complete. Rows In: {rows_in}, Rows Out: {rows_out}, QA Issues: {len(qa_records)}")

if __name__ == "__main__":
    process_kapt()
