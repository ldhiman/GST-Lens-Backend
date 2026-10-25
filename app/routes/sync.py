# routes/sync.py
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import verify_firebase_token, subscription_required
from app.firebase import db
from firebase_admin import firestore
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/sync")


@router.get("/invoices")
async def get_new_invoices(
    last_sync_time: int = 0,
    user = Depends(subscription_required())
):
    uid = user["uid"]

    invoices_ref = db.collection("users").document(uid).collection("invoices")

    if last_sync_time == 0:
        # First sync on new device → get ALL invoices
        docs = invoices_ref.stream()
    else:
        # Incremental sync → only newer than last_sync_time
        sync_datetime = datetime.fromtimestamp(
            last_sync_time / 1000,
            tz=timezone.utc
        )
        docs = invoices_ref.where("updated_at", ">", sync_datetime).stream()

    invoices = []
    for doc in docs:
        data = doc.to_dict()
        data["cloud_id"] = doc.id

        # Convert timestamps to milliseconds for frontend
        for field in ["created_at", "updated_at"]:
            if field in data and hasattr(data[field], "timestamp"):
                data[field] = int(data[field].timestamp() * 1000)

        invoices.append(data)

    return {"invoices": invoices}


@router.post("/invoices")
async def upload_invoices(invoices: list[dict], user=Depends(subscription_required())):
    uid = user["uid"]

    # Firestore batch limit is 500 operations. Chunk into 400.
    CHUNK_SIZE = 400
    cloud_ids = []

    for i in range(0, len(invoices), CHUNK_SIZE):
        chunk = invoices[i:i + CHUNK_SIZE]
        batch = db.batch()

        for inv in chunk:
            local_id = (
                inv.get("local_id")
                or inv.get("data", {}).get("_local_id")
                or inv.get("id")
                or str(uuid.uuid4())
            )
            ref = db.collection("users").document(uid).collection("invoices").document(local_id)
            batch.set(ref, {
                **inv,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            cloud_ids.append(ref.id)

        batch.commit()

    return {"cloud_ids": cloud_ids}
