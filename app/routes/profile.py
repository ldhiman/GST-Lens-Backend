from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import verify_firebase_token, subscription_required
from app.gst_info import get_gst_info
from google.cloud import firestore
from app.firebase import db

router = APIRouter()


@router.post("/profile/gstin")
async def save_gstin(payload: dict, user=Depends(verify_firebase_token)):
    gstin = payload.get("gstin")
    if not gstin:
        raise HTTPException(status_code=400, detail="GSTIN required")

    gstin = gstin.strip().upper()

    # 🔒 Fetch GST info from backend (trusted)
    gst_info = get_gst_info(gstin)
    if not gst_info:
        raise HTTPException(status_code=404, detail="GSTIN not found")

    if gst_info.get("trade_name") is None or gst_info.get("trade_name") == "N/A":
        raise HTTPException(status_code=422, detail="GSTIN not valid")

    uid = user["uid"]
    user_ref = db.collection("users").document(uid)

    user_ref.update({
        "primary_gstin": gstin,
        "gst_verified": True,
        "gst_info": gst_info,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })

    return {
        "status": "success",
        "gst_info": gst_info
    }


@router.post("/profile/settings")
async def update_settings(payload: dict, user=Depends(verify_firebase_token)):
    uid = user["uid"]
    allowed_keys = {"autoSave", "notificationsEnabled"}

    settings = {
        f"settings.{k}": v
        for k, v in payload.items()
        if k in allowed_keys
    }

    if not settings:
        raise HTTPException(status_code=400, detail="No valid settings")

    db.collection("users").document(uid).update({
        **settings,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })

    return {"status": "success"}


@router.post("/profile/settings/paid")
async def update_paid_settings(payload: dict, user=Depends(subscription_required())):
    uid = user["uid"]
    allowed_keys = {"cloud_sync_enabled"}
    updates = {
        f"settings.{k}": v
        for k, v in payload.items()
        if k in allowed_keys
    }

    if not updates:
        raise HTTPException(status_code=400, detail="No valid settings")

    db.collection("users").document(uid).update(updates)

    return {"status": "success"}


async def ensure_user_exists(user):
    user_ref = db.collection("users").document(user["uid"])
    snap = user_ref.get()

    if snap.exists:
        print("User already exists")
        return

    print("Creating new user")

    email = user.get("email") or ""
    display_name = user.get("name") or (email.split("@")[0] if email else "User")
    picture = user.get("picture")

    # 👇 First-time user
    user_ref.set({
        "email": email,
        "name": display_name,
        "uid": user["uid"],
        "photoURL": picture,
        "credits": 10,              # 🎁 Free credits
        "gst_verified": False,
        "primary_gstin": None,
        "settings": {
            "autoSave": False,
            "notificationsEnabled": True,
        },
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })


def refund_credit(uid: str, amount: int = 1):
    try:
        ref = db.collection("users").document(uid)
        ref.update({
            "credits": firestore.Increment(amount)
        })
    except Exception as e:
        print(f"Error refunding credit for user {uid}: {e}")
