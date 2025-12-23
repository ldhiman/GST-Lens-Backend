from fastapi import FastAPI, UploadFile, File, HTTPException
from app.image_process import extract_invoice_data
from app.gst_info import get_gst_info
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends
import app.firebase
from app.dependencies import verify_firebase_token, credit_required
from app.routes import profile
from app.routes import sync
from app.routes import payments


app = FastAPI()

# ✅ CORS CONFIG
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gstlens-frontend.vercel.app", "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(sync.router)
app.include_router(payments.router)


MAX_FILE_SIZE = 1 * 1024 * 1024  # 4MB (Vercel limit is ~4.5MB)


@app.get("/")
async def root():
    return {"message": "GST Invoice Processor Running"}


@app.post("/login")
async def login(user=Depends(verify_firebase_token)):
    await profile.ensure_user_exists(user)
    return {"message": "Logged in"}


@app.post("/upload")
async def process_invoice(file: UploadFile = File(...), user = Depends(credit_required(1))):
    allowed_types = {
        "application/pdf",
        "image/jpeg",
        "image/png"
    }

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    try:
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")

        # 1️⃣ Extract
        extraction_response = extract_invoice_data(content, file.content_type)

        if extraction_response.get("status") != "success":
            raise HTTPException(status_code=422, detail="Extraction failed")

        raw_data = extraction_response["data"]

        # 2️⃣ Post-validate (copy-safe)
        validated_data = post_validate(raw_data.copy())

        # 3️⃣ GST info lookup (only if GSTIN exists)
        return {
            "status": "success",
            "data": validated_data,
        }

    except HTTPException:
        profile.refund_credit(user["uid"])
        raise
    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail="Internal processing error")
    finally:
        await file.close()

@app.get("/gstinfo/{gstin}")
async def gst_info(gstin: str):
    try:
        info = get_gst_info(gstin)
        if not info:
            raise HTTPException(status_code=404, detail="GSTIN not found")

        return {
            "status": "success",
            "data": info
        }

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail="Internal server error")


def post_validate(data: dict) -> dict:
    # Normalize empty strings
    for key in ["seller_gstin", "buyer_gstin"]:
        if data.get(key) in ("", "null"):
            data[key] = None

    # GSTIN length check (basic)
    if data.get("seller_gstin") and len(data["seller_gstin"]) != 15:
        data["seller_gstin"] = None

    if data.get("buyer_gstin") and len(data["buyer_gstin"]) != 15:
        data["buyer_gstin"] = None

    # POS logic
    if data.get("seller_gstin"):
        data["pos"] = data["seller_gstin"][:2]

    # Tax sanity check
    cgst = data.get("cgst") or 0
    sgst = data.get("sgst") or 0
    igst = data.get("igst") or 0
    taxable = data.get("taxable_value") or 0
    total = data.get("invoice_total")

    if total and abs((taxable + cgst + sgst + igst) - total) > 2:
        data["warning"] = "Tax mismatch"

    # Invoice type consistency
    data["invoice_type"] = "B2B" if data.get("buyer_gstin") else "B2C"

    return data
