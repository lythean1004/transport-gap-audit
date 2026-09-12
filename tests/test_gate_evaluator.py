"""Tests for registry staging and gate evaluation."""

import pytest
import pathlib
import pandas as pd
from src.extractors.append_registry import classify_occupancy_event, build_staged_registry
from src.metrics.gate_evaluator import evaluate_gate


def test_classify_occupancy_event():
    # District first actual
    assert classify_occupancy_event("H001", "동탄(2)지구, 첫 입주 시작", "첫 입주", "", "district") == "occupancy_first_actual"
    
    # Block planned
    assert classify_occupancy_event("A01", "동탄2 C-27블록 공공분양", "입주예정일", "", "block") == "occupancy_planned_block"
    
    # First planned
    assert classify_occupancy_event("H002", "동탄 개발계획 확정", "이루어지도록 할 계획", "초기 계획", "district") == "occupancy_first_planned"


def test_gate_evaluator_runs():
    # Build staged registry first
    df = build_staged_registry()
    assert not df.empty
    
    # Evaluate gate
    report = evaluate_gate()
    assert "gate_decision" in report
    assert "districts_detail" in report
