import pytest
from unittest.mock import patch
from src.collectors.building_title import get_building_title

@pytest.fixture
def mock_api_common():
    with patch('src.collectors.building_title.fetch_public_api') as mock_fetch:
        yield mock_fetch

def test_dry_run(mock_api_common, caplog):
    # Call with dry_run
    res = get_building_title("41590", "12345", "0", "0001", "0002", dry_run=True)
    assert res == []
    
    # fetch_public_api should have been called with dry_run=True
    mock_api_common.assert_called_once()
    kwargs = mock_api_common.call_args[1]
    assert kwargs.get("dry_run") is True
    
def test_items_item_variations(mock_api_common):
    # 1. Test dict (single item)
    mock_api_common.return_value = {
        "data": {
            "response": {
                "body": {
                    "totalCount": 1,
                    "items": {
                        "item": {"mgmBldrgstPk": "PK1", "useAprDay": "20200101"}
                    }
                }
            }
        }
    }
    res = get_building_title("1", "2", "3", "4", "5")
    assert len(res) == 1
    assert res[0]["mgmBldrgstPk"] == "PK1"
    assert "useAprDay" in res[0]
    assert "occupancy_start" not in res[0]
    
    # 2. Test list (multiple items)
    mock_api_common.return_value = {
        "data": {
            "response": {
                "body": {
                    "totalCount": 2,
                    "items": {
                        "item": [
                            {"mgmBldrgstPk": "PK1"},
                            {"mgmBldrgstPk": "PK2"}
                        ]
                    }
                }
            }
        }
    }
    res = get_building_title("1", "2", "3", "4", "5")
    assert len(res) == 2
    assert res[1]["mgmBldrgstPk"] == "PK2"

    # 3. Test missing items/empty
    mock_api_common.return_value = {
        "data": {
            "response": {
                "body": {
                    "totalCount": 0,
                    "items": ""
                }
            }
        }
    }
    res = get_building_title("1", "2", "3", "4", "5")
    assert len(res) == 0
