import pytest
from app.image_process import InvoiceData


def test_invoice_data_defaults():
    inv = InvoiceData()
    assert inv.invoice_type == "B2C"
    assert inv.invoice_number is None
    assert inv.seller_gstin is None
    assert inv.buyer_gstin is None
    assert inv.taxable_value is None


def test_invoice_data_model_validate():
    payload = {
        "invoice_number": "INV/2026/001",
        "invoice_date": "24-10-2026",
        "seller_gstin": "07AAAAA0000A1Z5",
        "buyer_gstin": "29BBBBB1111B2Z6",
        "invoice_type": "B2B",
        "pos": "07",
        "taxable_value": 1500.50,
        "cgst": 135.0,
        "sgst": 135.0,
        "igst": 0.0,
        "invoice_total": 1770.50,
    }
    inv = InvoiceData.model_validate(payload)
    dumped = inv.model_dump()

    assert dumped["invoice_number"] == "INV/2026/001"
    assert dumped["invoice_type"] == "B2B"
    assert dumped["taxable_value"] == 1500.50
    assert dumped["seller_gstin"] == "07AAAAA0000A1Z5"
