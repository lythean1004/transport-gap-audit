import pytest
import openpyxl
from pathlib import Path
import datetime
import polars as pl
import yaml
import csv

from src.extractors.kapt_normalizer import process_kapt

@pytest.fixture
def temp_kapt_env(tmp_path):
    # Create fake raw dir
    raw_dir = tmp_path / "data" / "raw" / "kapt"
    raw_dir.mkdir(parents=True)
    
    # Create fake output dirs
    out_dir = tmp_path / "data" / "staged"
    qa_dir = tmp_path / "exports"
    
    # Generate tiny workbook
    excel_path = raw_dir / "test_kapt.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # R1: Notice (merged conceptually, just put in A1)
    ws.append(["This is a warning notice"])
    
    # R2: Headers
    ws.append(["단지코드", "단지명", "법정동주소", "도로명주소", "사용승인일", "동수", "세대수"])
    
    # R3-R7: Data
    # 1. datetime cell, leading zero code
    ws.append(["01007001", "Apt 1", "Addr 1", "Road 1", datetime.datetime(2015, 1, 31), 5, 100])
    
    # 2. "20150131" string
    ws.append(["A1007002", "Apt 2", "Addr 2", "Road 2", "20150131", "3", "200.0"])
    
    # 3. "2015-01-31" string
    ws.append(["B1007003", "Apt 3", "Addr 3", "Road 3", "2015-01-31", 1, 300])
    
    # 4. unparsable date (QA drop/null), non-numeric household
    ws.append(["C1007004", "Apt 4", "Addr 4", "Road 4", "UnknownDate", "NotInt", "Many"])
    
    wb.save(excel_path)
    
    # Create fake config
    config_path = tmp_path / "config" / "kapt_columns.yaml"
    config_path.parent.mkdir(parents=True)
    
    config_data = {
        "meta": {
            "header_row": 2,
            "data_start_row": 3,
            "kapt_extracted_at": "2026-08-21"
        },
        "mapping": {
            "kapt_code": "단지코드",
            "kapt_name": "단지명",
            "addr_legal": "법정동주소",
            "addr_road": "도로명주소",
            "approval_date": "사용승인일",
            "bldg_count": "동수",
            "household_count": "세대수"
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True)
        
    return excel_path, config_path, out_dir, qa_dir

def test_kapt_normalizer(temp_kapt_env):
    excel_path, config_path, out_dir, qa_dir = temp_kapt_env
    
    # Run process
    process_kapt(input_path=excel_path, config_path=config_path, out_dir=out_dir, qa_dir=qa_dir)
    
    out_parquet = out_dir / "kapt_basic.parquet"
    assert out_parquet.exists()
    
    df = pl.read_parquet(out_parquet)
    assert len(df) == 4 # 4 data rows in input, all 4 are outputted (unparsable just become NULL)
    
    # Check leading zero preservation
    codes = df["kapt_code"].to_list()
    assert "01007001" in codes
    
    # Check date parsing
    dates = df["approval_date"].to_list()
    assert dates[0] == "2015-01-31" # datetime
    assert dates[1] == "2015-01-31" # YYYYMMDD
    assert dates[2] == "2015-01-31" # YYYY-MM-DD
    assert dates[3] is None         # unparsable
    
    # Check raw date preservation
    raw_dates = df["approval_date_raw"].to_list()
    assert "UnknownDate" in raw_dates
    
    # Check non-numeric parsing
    bldg = df["bldg_count"].to_list()
    assert bldg[3] is None # "NotInt"
    hcount = df["household_count"].to_list()
    assert hcount[1] == 200 # parsed from 200.0
    assert hcount[3] is None # "Many"
    
    # Check added columns
    cols = df.columns
    assert "source_file" in cols
    assert "kapt_extracted_at" in cols
    assert "data_caveat" in cols
    
    # Ensure no occupancy columns
    forbidden = ["occupancy_start", "first_occupancy", "move_in_date"]
    for f in forbidden:
        assert f not in cols
        
    # Check QA
    qa_csv = qa_dir / "kapt_qa.csv"
    assert qa_csv.exists()
    
    with open(qa_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        qa_rows = list(reader)
        
    assert len(qa_rows) == 1
    assert qa_rows[0]["kapt_code"] == "C1007004"
    assert "unparsable_date" in qa_rows[0]["reasons"]
    assert "non_numeric_household_count" in qa_rows[0]["reasons"]
    assert qa_rows[0]["approval_date_raw"] == "UnknownDate"
