import os
import csv
from pathlib import Path

def test_smoke_arrival_script_exists():
    assert Path("scripts/smoke_arrival.py").exists()

def test_smoke_raw_json_file_created():
    smoke_dir = Path("evidence/smoke")
    assert smoke_dir.exists()
    json_files = list(smoke_dir.glob("*.json"))
    assert len(json_files) >= 1, "evidence/smoke 에 최소 1개 이상의 raw json 파일이 있어야 합니다."

def test_smoke_log_csv_format():
    log_file = Path("evidence/smoke_log.csv")
    assert log_file.exists(), "evidence/smoke_log.csv 가 존재해야 합니다."
    
    with open(log_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    assert len(rows) >= 1, "smoke_log.csv 에 최소 1개 행이 기록되어야 합니다."
    
    required_cols = [
        "citycode", "nodeid", "smoke_test_at_kst", "smoke_test_at_utc",
        "http_status", "resultCode", "resultMsg", "item_count",
        "outcome", "raw_path", "key_form_used"
    ]
    for col in required_cols:
        assert col in rows[0], f"smoke_log.csv 에 {col} 컬럼이 존재해야 합니다."
        
    assert rows[0]["outcome"] in ["ok_with_items", "ok_empty", "api_error"]
    assert rows[0]["key_form_used"] != ""
