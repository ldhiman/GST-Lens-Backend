# app/routes/payments.py
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.core.razorpay_client import razorpay_client
from app.core.config import settings
from app.dependencies import verify_firebase_token
from app.firebase import db
from firebase_admin import firestore
import uuid
from datetime import datetime
from dateutil.relativedelta import relativedelta

router = APIRouter(prefix="/payments", tags=["payments"])

# Credit pack pricing (credits → price in rupees)
CREDIT_PACKS = {
    50: 100,    # 50 credits = ₹100
    150: 250,   # 150 credits = ₹250
    350: 500,   # 350 credits = ₹500
}

MONTHLY_PLAN_ID = settings.RAZORPAY_MONTHLY_PLAN_ID


class CreateOrderRequest(BaseModel):
    credits: int  # must be 50, 150, or 350


class CreateSubscriptionRequest(BaseModel):
    plan: str = "monthly"


# Transactional credit addition
def add_credits(uid: str, amount: int):
    user_ref = db.collection("users").document(uid)

    @firestore.transactional
    def update_credits(transaction):
        snap = user_ref.get(transaction=transaction)
        if not snap.exists:
            raise ValueError("User not found")
        current = snap.to_dict().get("credits", 0)
        transaction.update(user_ref, {
            "credits": current + amount,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })

    transaction = db.transaction()
    update_credits(transaction)


# 1. Create one-time order for credit packs
@router.post("/create-order")
async def create_order(
    req: CreateOrderRequest,
    user = Depends(verify_firebase_token)
):
    uid = user["uid"]

    if req.credits not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail="Invalid credit amount")

    price_rupees = CREDIT_PACKS[req.credits]
    amount_paise = price_rupees * 100
    short_uid = uid[-8:]  # last 8 chars of UID
    short_uuid = uuid.uuid4().hex[:6]

    receipt = f"cr_{short_uid}_{short_uuid}"
    order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": {
            "uid": uid,
            "credits": req.credits,
            "type": "credit_pack"
        }
    })

    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
        "receipt": receipt
    }


# 2. Create subscription for cloud sync + monthly credits
@router.post("/create-subscription")
async def create_subscription(
    req: CreateSubscriptionRequest,
    user = Depends(verify_firebase_token)
):
    uid = user["uid"]

    if req.plan != "monthly":
        raise HTTPException(status_code=400, detail="Invalid plan")

    subscription = razorpay_client.subscription.create({
        "plan_id": MONTHLY_PLAN_ID,
        "total_count": 12,  # Optional: auto-cancel after 12 months
        "quantity": 1,
        "customer_notify": 1,
        "notes": {"uid": uid},
        "notify_info": {
            "notify_email": user.get("email")
        }
    })

    return {
        "subscription_id": subscription["id"],
        "short_url": subscription["short_url"]
    }


def is_event_processed(event_id: str | None) -> bool:
    if not event_id:
        return False
    ref = db.collection("payment_events").document(event_id)
    if ref.get().exists:
        return True
    ref.set({
        "processedAt": firestore.SERVER_TIMESTAMP
    })
    return False


# 3. Webhook handler
@router.post("/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    try:
        razorpay_client.utility.verify_webhook_signature(
            body.decode(),
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = await request.json()
    print(event)

    event_id = get_event_key(event)
    event_type = event.get("event")
    payload = event.get("payload", {})

    # 🔐 Idempotency
    if event_id and is_event_processed(event_id):
        return {"status": "duplicate_ignored"}

    # ✅ CREDIT PURCHASE (one-time)
    if event_type == "payment.captured":
        payment = payload.get("payment", {}).get("entity", {})
        notes = payment.get("notes", {})
        uid = notes.get("uid")
        credits = int(notes.get("credits", 0))

        if uid and credits > 0:
            add_credits(uid, credits)

    # ✅ SUBSCRIPTION ACTIVATED
    elif event_type == "subscription.activated":
        sub = payload.get("subscription", {}).get("entity", {})
        uid = sub.get("notes", {}).get("uid")

        if uid:
            db.collection("users").document(uid).update({
                "subscription": {
                    "active": True,
                    "razorpay_subscription_id": sub.get("id"),
                    "plan": "monthly",
                    "current_period_end": sub.get("current_end"),
                },
                "settings.cloud_sync_enabled": True,
                "updatedAt": firestore.SERVER_TIMESTAMP
            })

    # ✅ MONTHLY CREDIT GRANT
    elif event_type == "subscription.charged":
        sub = payload.get("subscription", {}).get("entity", {})
        uid = sub.get("notes", {}).get("uid")

        if uid:
            add_credits(uid, 100)

    # ❌ SUBSCRIPTION STOPPED
    elif event_type in ["subscription.cancelled", "subscription.halted", "subscription.paused"]:
        sub_entity = payload.get("subscription", {}).get("entity", {})
        razorpay_sub_id = sub_entity.get("id")
        notes = sub_entity.get("notes", {})
        uid = notes.get("uid")

        if not uid or not razorpay_sub_id:
            print("Webhook missing uid or subscription ID - ignoring")
            return {"status": "ignored"}

        # Fetch current user data
        user_ref = db.collection("users").document(uid)
        user_snap = user_ref.get()

        if not user_snap.exists:
            print(f"User {uid} not found for subscription cancel")
            return {"status": "user_not_found"}

        user_data = user_snap.to_dict()
        stored_sub_id = user_data.get("subscription", {}).get("razorpay_subscription_id")

        # Only disable if this is the SAME subscription
        if stored_sub_id == razorpay_sub_id:
            user_ref.update({
                "subscription.active": False,
                "settings.cloud_sync_enabled": False,
                "updatedAt": firestore.SERVER_TIMESTAMP
            })
            print(f"Disabled cloud sync for user {uid} - subscription {razorpay_sub_id} cancelled")
        else:
            print(f"Ignored cancel event for old subscription {razorpay_sub_id} (current: {stored_sub_id})")

        return {"status": "processed"}


def get_event_key(event: dict) -> str | None:
    etype = event.get("event")
    payload = event.get("payload", {})

    try:
        if etype == "payment.captured":
            return payload["payment"]["entity"]["id"]

        if etype in {
            "subscription.activated",
            "subscription.cancelled",
            "subscription.halted",
        }:
            return payload["subscription"]["entity"]["id"]

        if etype == "subscription.charged":
            # Razorpay sends invoice entity here
            return payload["invoice"]["entity"]["id"]

    except KeyError:
        return None

    return None


@router.post("/cancel-subscription")
async def cancel_subscription(user = Depends(verify_firebase_token)):
    uid = user["uid"]

    user_ref = db.collection("users").document(uid)
    user_snap = user_ref.get()

    if not user_snap.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_snap.to_dict()
    sub = user_data.get("subscription", {})

    if not sub.get("active", False):
        raise HTTPException(status_code=400, detail="No active subscription to cancel")

    if sub.get("cancel_requested", False):
        raise HTTPException(status_code=400, detail="Subscription cancellation already requested")

    razorpay_sub_id = sub.get("razorpay_subscription_id")
    if not razorpay_sub_id:
        raise HTTPException(status_code=500, detail="Subscription ID missing")

    try:
        # Call Razorpay API to cancel
        razorpay_client.subscription.cancel(
            razorpay_sub_id, {
                "cancel_at_cycle_end": True  # Keep access until end of current period
            }
        )

        # Update user document
        user_ref.update({
            "subscription.cancel_requested": True,
            "subscription.cancel_at_period_end": True,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })

        return {
            "status": "success",
            "message": "Subscription will be cancelled at the end of current billing period."
        }
    except Exception as e:
        print(f"Razorpay cancel error: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")
