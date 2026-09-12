import pytest
import os
import requests
from unittest.mock import patch, Mock
import polars as pl
from pathlib import Path
from src.collectors.building_hub import (
    fetch_page, BuildingHubAuthError, BuildingHubAPIError,
    extract_items, collect_bldg_title, save_to_parquet, parse_useAprDay
)

def test_extract_items():
    # Missing item
    assert extract_items({}) == []
    assert extract_items({'response': {'body': {}}}) == []
    
    # Single dict
    data_dict = {'response': {'body': {'items': {'item': {'mgmBldrgstPk': '1'}}}}}
    assert extract_items(data_dict) == [{'mgmBldrgstPk': '1'}]
    
    # List
    data_list = {'response': {'body': {'items': {'item': [{'mgmBldrgstPk': '1'}, {'mgmBldrgstPk': '2'}]}}}}
    assert extract_items(data_list) == [{'mgmBldrgstPk': '1'}, {'mgmBldrgstPk': '2'}]

def test_fetch_page_auth_error():
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': {'header': {'resultCode': '30', 'resultMsg': 'ERR'}}}
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        with pytest.raises(BuildingHubAuthError) as e:
            fetch_page("http://dummy", {})
        assert "TAGO_SERVICE_KEY" in str(e.value)
        assert mock_get.call_count == 1  # Fail fast, no retries

def test_fetch_page_api_error():
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': {'header': {'resultCode': '22', 'resultMsg': 'ERR'}}}
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        with patch('time.sleep') as mock_sleep:
            with pytest.raises(BuildingHubAPIError) as e:
                fetch_page("http://dummy", {})
            assert "API Error 22" in str(e.value)
            assert mock_get.call_count == 3  # Retry logic applies
            assert mock_sleep.call_count == 2

def test_fetch_page_http_error():
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 502
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
        mock_get.return_value = mock_resp
        
        with patch('time.sleep') as mock_sleep:
            with pytest.raises(BuildingHubAPIError) as e:
                fetch_page("http://dummy", {})
            assert "HTTP Error 502" in str(e.value)
            assert mock_get.call_count == 3
            assert mock_sleep.call_count == 2

def test_parse_useAprDay():
    assert parse_useAprDay(None) is None
    assert parse_useAprDay("") is None
    assert parse_useAprDay("19911120") == "1991-11-20"
    assert parse_useAprDay("invalid") is None

def test_save_to_parquet(tmp_path):
    items = [{
        "mgmBldrgstPk": "PK1",
        "useAprDay": "19911120",
        "hhldCnt": "100"
    }]
    out_path = tmp_path / "test.parquet"
    save_to_parquet(items, str(out_path))
    
    df = pl.read_parquet(out_path)
    assert len(df) == 1
    assert df["mgmBldrgstPk"][0] == "PK1"
    assert df["useAprDay_raw"][0] == "19911120"
    assert df["useAprDay"][0] == "1991-11-20"
    assert df["hhldCnt"][0] == 100
