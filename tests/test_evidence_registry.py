import pytest
import pandas as pd
from pathlib import Path
from src.evidence_registry import validate_registry, generate_gate_report

@pytest.fixture
def synthetic_registry():
    """
    Creates a synthetic evidence registry for testing the gate logic.
    Provides 4 passed pilots and 1 failed pilot.
    """
    data = []
    pilots = ["Dongtan2", "Gimpo Hangang", "Wirye", "Namyangju Dasan", "Hanam Misa"]
    events = ["occupancy_start", "promise_date", "actual_operation"]
    
    # Pilots 0 to 3 have all events and human_verified
    for i in range(4):
        for ev in events:
            data.append({
                "candidate_id": f"CAND_{i}_{ev}",
                "development": pilots[i],
                "event_type": ev,
                "event_date": "2020-01-01",
                "date_precision": "day",
                "date_lower_bound": "2020-01-01",
                "date_upper_bound": "2020-01-01",
                "source_url": "http://example.com",
                "local_path": "fake/path.pdf",
                "sha256": "fakehash123",
                "review_status": "human_verified"
            })
            
    # Pilot 4 is missing actual_operation
    for ev in ["occupancy_start", "promise_date"]:
        data.append({
            "candidate_id": f"CAND_4_{ev}",
            "development": pilots[4],
            "event_type": ev,
            "event_date": "2020-01-01",
            "date_precision": "day",
            "date_lower_bound": "2020-01-01",
            "date_upper_bound": "2020-01-01",
            "source_url": "http://example.com",
            "local_path": "fake/path.pdf",
            "sha256": "fakehash123",
            "review_status": "human_verified"
        })
        
    return pd.DataFrame(data)

def test_validate_registry(synthetic_registry):
    df = validate_registry(synthetic_registry)
    assert "metric_eligible" in df.columns
    assert df["metric_eligible"].all() # All synthetic are human_verified
    
def test_gate_report_pass(synthetic_registry, tmp_path):
    # Should pass because 4 out of 5 have all 3 events
    df = validate_registry(synthetic_registry)
    report_file = tmp_path / "data_gate_status.md"
    generate_gate_report(df, str(report_file))
    
    content = report_file.read_text(encoding="utf-8")
    assert "**Gate Decision:** PASS" in content
    assert "- Pilots with all 3 events: 4 / 5" in content
    assert "**actual_operation**: MISSING EVIDENCE" in content

def test_gate_report_fail(synthetic_registry, tmp_path):
    # Make pilot 0 missing actual_operation -> now only 3 have all 3 events
    df = synthetic_registry
    df = df[df["candidate_id"] != "CAND_0_actual_operation"]
    
    df = validate_registry(df)
    report_file = tmp_path / "data_gate_status.md"
    generate_gate_report(df, str(report_file))
    
    content = report_file.read_text(encoding="utf-8")
    assert "**Gate Decision:** FAIL" in content
    assert "- Pilots with all 3 events: 3 / 5" in content
    
def test_gate_report_fail_precision(synthetic_registry, tmp_path):
    # Downgrade precision to "year" for all events
    df = synthetic_registry.copy()
    df["date_precision"] = "year"
    
    df = validate_registry(df)
    report_file = tmp_path / "data_gate_status.md"
    generate_gate_report(df, str(report_file))
    
    content = report_file.read_text(encoding="utf-8")
    assert "**Gate Decision:** FAIL" in content
    assert "- Pilots with high precision (day/month): 0 / 5" in content

