import os
import pytest
from pathlib import Path

def test_tago_route_findings_doc_exists():
    doc_path = Path("docs/tago_route_api_findings.md")
    assert doc_path.exists(), "docs/tago_route_api_findings.md 파일이 존재해야 합니다."

def test_tago_route_findings_contains_required_operations():
    doc_path = Path("docs/tago_route_api_findings.md")
    content = doc_path.read_text(encoding="utf-8")
    
    # 4개 오퍼레이션 명시 여부
    assert "getCtyCodeList" in content, "getCtyCodeList 오퍼레이션이 문서에 포함되어야 합니다."
    assert "getRouteNoList" in content, "getRouteNoList 오퍼레이션이 문서에 포함되어야 합니다."
    assert "getRouteAcctoThrghSttnList" in content, "getRouteAcctoThrghSttnList 오퍼레이션이 문서에 포함되어야 합니다."
    assert "getRouteInfoIem" in content, "getRouteInfoIem 오퍼레이션이 문서에 포함되어야 합니다."

def test_tago_route_findings_contains_first_last_bus_fields():
    doc_path = Path("docs/tago_route_api_findings.md")
    content = doc_path.read_text(encoding="utf-8")
    
    # 첫차, 막차 정확한 필드명 확인 (AGENTS.md 기준)
    assert "startvehicletime" in content, "첫차 필드 startvehicletime이 명시되어야 합니다."
    assert "endvehicletime" in content, "막차 필드 endvehicletime이 명시되어야 합니다."

def test_tago_route_findings_contains_headway_fields():
    doc_path = Path("docs/tago_route_api_findings.md")
    content = doc_path.read_text(encoding="utf-8")
    
    # 배차간격 정확한 필드명 확인 (AGENTS.md 기준)
    assert "intervaltime" in content, "평일 배차간격 필드 intervaltime이 명시되어야 합니다."
    assert "intervalsattime" in content, "토요일 배차간격 필드 intervalsattime이 명시되어야 합니다."
    assert "intervalsuntime" in content, "일요일 배차간격 필드 intervalsuntime이 명시되어야 합니다."

def test_smoke_raw_files_exist():
    smoke_dir = Path("data/raw/tago_route_smoke")
    assert smoke_dir.exists(), "data/raw/tago_route_smoke 디렉토리가 존재해야 합니다."
    raw_files = list(smoke_dir.glob("*.json"))
    assert len(raw_files) >= 4, "4개 오퍼레이션의 raw 스냅샷 파일이 저장되어야 합니다."
