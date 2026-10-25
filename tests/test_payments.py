import pytest
from app.routes.payments import get_event_key, CREDIT_PACKS


def test_credit_packs_pricing():
    assert CREDIT_PACKS[50] == 100
    assert CREDIT_PACKS[150] == 250
    assert CREDIT_PACKS[350] == 500


def test_get_event_key_with_razorpay_event_id():
    event = {
        "id": "evt_test123456",
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_XYZ789"
                }
            }
        }
    }
    assert get_event_key(event) == "evt_test123456"


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


def test_get_event_key_subscription_activated_and_cancelled_never_collide():
    activated_event = {
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_XYZ789"
                }
            }
        }
    }
    cancelled_event = {
        "event": "subscription.cancelled",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_XYZ789"
                }
            }
        }
    }
    key_act = get_event_key(activated_event)
    key_can = get_event_key(cancelled_event)

    assert key_act == "subscription.activated_sub_XYZ789"
    assert key_can == "subscription.cancelled_sub_XYZ789"
    # Essential assertion: Keys must not collide, otherwise cancellation is swallowed as duplicate!
    assert key_act != key_can


def test_get_event_key_unknown_or_malformed():
    assert get_event_key({"event": "unknown.event"}) is None
    assert get_event_key({}) is None
    assert get_event_key({"event": "payment.captured", "payload": {}}) is None
