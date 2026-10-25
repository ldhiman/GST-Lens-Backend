import pytest
from app.main import post_validate


def test_post_validate_valid_b2b():
    data = {
        "seller_gstin": "07AAAAA0000A1Z5",
        "buyer_gstin": "29BBBBB1111B2Z6",
        "taxable_value": 1000.0,
        "cgst": 90.0,
        "sgst": 90.0,
        "igst": 0.0,
        "invoice_total": 1180.0,
    }
    validated = post_validate(data)

    assert validated["seller_gstin"] == "07AAAAA0000A1Z5"
    assert validated["buyer_gstin"] == "29BBBBB1111B2Z6"
    assert validated["pos"] == "29"  # Section 10 IGST Act: B2B default is buyer destination state
    assert validated["invoice_type"] == "B2B"
    assert "warning" not in validated


def test_post_validate_strict_date_normalization():
    # ISO date -> DD-MM-YYYY
    assert post_validate({"invoice_date": "2026-10-25"})["invoice_date"] == "25-10-2026"

    # Slash date -> DD-MM-YYYY
    assert post_validate({"invoice_date": "5/4/2026"})["invoice_date"] == "05-04-2026"

    # Dot date -> DD-MM-YYYY
    assert post_validate({"invoice_date": "15.08.2025"})["invoice_date"] == "15-08-2025"

    # Alphanumeric month -> DD-MM-YYYY
    assert post_validate({"invoice_date": "24-Oct-2026"})["invoice_date"] == "24-10-2026"

    # Invalid date -> None
    assert post_validate({"invoice_date": "invalid-date"})["invoice_date"] is None


def test_post_validate_b2c_when_no_buyer_gstin():
    data = {
        "seller_gstin": "07AAAAA0000A1Z5",
        "buyer_gstin": None,
        "taxable_value": 500.0,
        "cgst": 45.0,
        "sgst": 45.0,
        "igst": 0.0,
        "invoice_total": 590.0,
    }
    validated = post_validate(data)

    assert validated["invoice_type"] == "B2C"
    assert validated["buyer_gstin"] is None


def test_post_validate_invalid_gstin_length_is_stripped():
    data = {
        "seller_gstin": "INVALID_TOO_SHORT",
        "buyer_gstin": "29BBBBB1111B2Z6_TOO_LONG",
    }
    validated = post_validate(data)

    assert validated["seller_gstin"] is None
    assert validated["buyer_gstin"] is None
    assert validated["pos"] is None
    assert validated["invoice_type"] == "B2C"


def test_post_validate_normalizes_empty_and_null_strings():
    data = {
        "seller_gstin": " null ",
        "buyer_gstin": "NONE",
    }
    validated = post_validate(data)

    assert validated["seller_gstin"] is None
    assert validated["buyer_gstin"] is None


def test_post_validate_tax_mismatch_warning():
    data = {
        "seller_gstin": "07AAAAA0000A1Z5",
        "taxable_value": 1000.0,
        "cgst": 90.0,
        "sgst": 90.0,
        "igst": 0.0,
        # Expected total is 1180, but total is 1500 (mismatch > 2.0)
        "invoice_total": 1500.0,
    }
    validated = post_validate(data)

    assert validated["warning"] == "Tax mismatch"


def test_post_validate_tax_within_tolerance_no_warning():
    data = {
        "seller_gstin": "07AAAAA0000A1Z5",
        "taxable_value": 1000.0,
        "cgst": 90.0,
        "sgst": 90.0,
        "igst": 0.0,
        # 1 rupee difference due to rounding
        "invoice_total": 1181.0,
    }
    validated = post_validate(data)

    assert "warning" not in validated


def test_post_validate_strict_date_normalization():
    # ISO date -> DD-MM-YYYY
    assert post_validate({"invoice_date": "2026-10-25"})["invoice_date"] == "25-10-2026"

    # Slash date -> DD-MM-YYYY
    assert post_validate({"invoice_date": "5/4/2026"})["invoice_date"] == "05-04-2026"

    # Dot date -> DD-MM-YYYY
    assert post_validate({"invoice_date": "15.08.2025"})["invoice_date"] == "15-08-2025"

    # Alphanumeric month -> DD-MM-YYYY
    assert post_validate({"invoice_date": "24-Oct-2026"})["invoice_date"] == "24-10-2026"

    # Invalid date -> None
    assert post_validate({"invoice_date": "invalid-date"})["invoice_date"] is None
