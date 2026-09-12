import pytest
import pandas as pd
from pathlib import Path

def test_parquet_file_exists():
    p = Path("data/staged/route_service_hours.parquet")
    assert p.exists(), "data/staged/route_service_hours.parquet 파일이 존재해야 합니다."

def test_parquet_schema_and_columns():
    p = Path("data/staged/route_service_hours.parquet")
    df = pd.read_parquet(p)
    
    expected_cols = [
        "citycode", "routeid", "routeno", "routetp", "startnodenm", "endnodenm",
        "startvehicletime", "endvehicletime", "intervaltime", "intervalsattime",
        "intervalsuntime", "fetched_at_kst", "fetched_at_utc", "raw_path",
        "first_bus_ok", "last_bus_ok"
    ]
    for col in expected_cols:
        assert col in df.columns, f"{col} 컬럼이 데이터셋에 존재해야 합니다."
        
    assert len(df) >= 1, "최소 1개 이상의 노선 데이터가 있어야 합니다."

def test_time_columns_are_string_zero_padded():
    p = Path("data/staged/route_service_hours.parquet")
    df = pd.read_parquet(p)
    
    for col in ["startvehicletime", "endvehicletime"]:
        non_nulls = df[col].dropna()
        for val in non_nulls:
            assert isinstance(val, str), f"{col}의 값 {val}은 str이어야 합니다 (int 캐스팅 금지)."
            assert len(val) == 4, f"{col}의 값 {val}은 4자리 HHMM 형태여야 합니다 (예: 0600)."

def test_boolean_derivation_null_preservation():
    p = Path("data/staged/route_service_hours.parquet")
    df = pd.read_parquet(p)
    
    for _, row in df.iterrows():
        # startvehicletime이 없으면 first_bus_ok는 반드시 NA
        if pd.isna(row["startvehicletime"]):
            assert pd.isna(row["first_bus_ok"]), "startvehicletime이 결측이면 first_bus_ok는 False가 아닌 NA여야 합니다."
        else:
            expected = (row["startvehicletime"] <= "0630")
            assert row["first_bus_ok"] == expected
            
        # endvehicletime이 없으면 last_bus_ok는 반드시 NA
        if pd.isna(row["endvehicletime"]):
            assert pd.isna(row["last_bus_ok"]), "endvehicletime이 결측이면 last_bus_ok는 False가 아닌 NA여야 합니다."
        else:
            expected = (row["endvehicletime"] >= "2200")
            assert row["last_bus_ok"] == expected
