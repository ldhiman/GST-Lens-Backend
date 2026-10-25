import pytest
from unittest.mock import patch
from app.gst_info import get_state_name, get_gst_info


def test_get_state_name_valid_codes():
    assert get_state_name("07") == "Delhi"
    assert get_state_name(7) == "Delhi"
    assert get_state_name("29") == "Karnataka"
    assert get_state_name("27") == "Maharashtra"
    assert get_state_name("99") == "Centre Jurisdiction"


def test_get_state_name_invalid_code():
    assert get_state_name("999") == "Invalid Code"
    assert get_state_name("-1") == "Invalid Code"


@patch("app.gst_info.get_gst_info_1")
@patch("app.gst_info.get_gst_info_2")
def test_get_gst_info_field_mapping(mock_source_2, mock_source_1):
    # Mock source 1 (MastersIndia)
    mock_source_1.return_value = {
        "success": True,
        "data": {
            "lgnm": "ROSMERTA SAFETY SYSTEMS LIMITED",
            "tradeNam": "ROSMERTA SAFETY",
            "sts": "Active",
            "ctb": "Public Limited Company",
        }
    }
    # Mock source 2 (Cashfree)
    mock_source_2.return_value = {
        "legal_business_name": "ROSMERTA SAFETY SYSTEMS LIMITED",
        "trade_name": "ROSMERTA SAFETY",
        "gstin_uin_status": "Active",
        "constitution_of_business": "Public Limited Company",
    }

    info = get_gst_info("07AAACU4747P1ZR")

    assert info["gstin"] == "07AAACU4747P1ZR"
    assert info["legal_name"] == "ROSMERTA SAFETY SYSTEMS LIMITED"
    assert info["trade_name"] == "ROSMERTA SAFETY"
    assert info["status"] == "Active"
    assert info["state_code"] == "07"
    assert info["state"] == "Delhi"
    assert info["pan_number"] == "AAACU4747P"


@patch("app.gst_info.get_gst_info_1")
@patch("app.gst_info.get_gst_info_2")
def test_get_gst_info_graceful_on_source_failures(mock_source_2, mock_source_1):
    mock_source_1.return_value = {}
    mock_source_2.return_value = {}

    info = get_gst_info("29ABCDE1234F1Z5")

    assert info["gstin"] == "29ABCDE1234F1Z5"
    assert info["legal_name"] == "N/A"
    assert info["trade_name"] == "N/A"
    assert info["status"] == "Inactive / Not Found"
    assert info["state_code"] == "29"
    assert info["state"] == "Karnataka"
    assert info["pan_number"] == "ABCDE1234F"
