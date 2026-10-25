import pytest
from app.routes.payments import get_event_key, CREDIT_PACKS


def test_credit_packs_pricing():
    assert CREDIT_PACKS[50] == 100
    assert CREDIT_PACKS[150] == 250
    assert CREDIT_PACKS[350] == 500


def test_get_event_key_payment_captured():
    event = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_ABC123"
                }
            }
        }
    }
    assert get_event_key(event) == "pay_ABC123"


def test_get_event_key_subscription_activated():
    event = {
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_XYZ789"
                }
            }
        }
    }
    assert get_event_key(event) == "sub_XYZ789"


def test_get_event_key_unknown_or_malformed():
    assert get_event_key({"event": "unknown.event"}) is None
    assert get_event_key({}) is None
    assert get_event_key({"event": "payment.captured", "payload": {}}) is None
