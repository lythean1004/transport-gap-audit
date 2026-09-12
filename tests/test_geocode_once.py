import pytest
import sys
from unittest.mock import patch, Mock
import io
from src.tools.geocode_once import geocode_address

def test_geocode_ok(capsys):
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "response": {
            "status": "OK",
            "result": {
                "point": {
                    "x": "127.1054", # Longitude
                    "y": "37.4020"   # Latitude
                },
                "items": [{"text": "경기도 성남시 분당구 판교로 242 (도로명정제)"}]
            }
        }
    }
    
    with patch('requests.get', return_value=mock_resp):
        with pytest.raises(SystemExit) as exc_info:
            geocode_address("판교로 242", "ROAD")
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr().out
        
        # Assert x is emitted as lon and y as lat
        assert "X (경도/Longitude): 127.1054" in captured
        assert "Y (위도/Latitude) : 37.4020" in captured
        assert "lat: 37.4020" in captured
        assert "lon: 127.1054" in captured
        assert "경기도 성남시 분당구 판교로 242 (도로명정제)" in captured

def test_geocode_not_found(capsys):
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "response": {
            "status": "NOT_FOUND"
        }
    }
    
    with patch('requests.get', return_value=mock_resp):
        with pytest.raises(SystemExit) as exc_info:
            geocode_address("없는주소", "ROAD")
            
        assert exc_info.value.code != 0
        captured = capsys.readouterr().out
        assert "NOT FOUND" in captured

def test_geocode_incorrect_key(capsys):
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "response": {
            "status": "ERROR",
            "error": {
                "text": "INCORRECT_KEY"
            }
        }
    }
    
    with patch('requests.get', return_value=mock_resp):
        with pytest.raises(SystemExit) as exc_info:
            geocode_address("주소", "ROAD")
            
        assert exc_info.value.code != 0
        captured = capsys.readouterr().out
        assert "발급 시 입력한 도메인과 로컬/요청 환경이 다를 수 있습니다" in captured

