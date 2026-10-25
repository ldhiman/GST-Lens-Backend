import re
from fastapi import FastAPI, UploadFile, File, HTTPException
from app.image_process import extract_invoice_data
from app.gst_info import get_gst_info, state_code_map
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


MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


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

        # 3️⃣ Return validated invoice data
        return {
            "status": "success",
            "data": validated_data,
        }

    except HTTPException:
        profile.refund_credit(user["uid"])
        raise
    except Exception as e:
        print("ERROR:", e)
        profile.refund_credit(user["uid"])
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


MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def normalize_invoice_date(raw: str | None) -> str | None:
    """Strictly normalizes any real-world invoice date into Indian statutory DD-MM-YYYY format."""
    if not raw or not isinstance(raw, str):
        return None
    cleaned = re.sub(r"[./\s]+", "-", raw.strip())
    parts = [p for p in cleaned.split("-") if p]
    if len(parts) != 3:
        return None

    day, month, year = None, None, None
    # YYYY-MM-DD (ISO standard)
    if len(parts[0]) == 4 and parts[0].isdigit():
        year = int(parts[0])
        month_part = parts[1]
        day_part = parts[2]
    # DD-MM-YYYY or DD-MMM-YY
    elif (len(parts[2]) == 4 or len(parts[2]) == 2) and parts[2].isdigit():
        day_part = parts[0]
        month_part = parts[1]
        year = int(parts[2])
        if len(parts[2]) == 2:
            year += 2000 if year < 70 else 1900
    else:
        return None

    m_str = month_part.lower()[:3]
    if m_str in MONTH_MAP:
        month = MONTH_MAP[m_str]
    elif month_part.isdigit():
        month = int(month_part)
    else:
        return None

    if day_part.isdigit():
        day = int(day_part)
    else:
        return None

    if not (1 <= month <= 12 and 1 <= day <= 31 and 1990 <= year <= 2099):
        return None

    return f"{day:02d}-{month:02d}-{year:04d}"


def post_validate(data: dict) -> dict:
    # 1. Strict Date Normalization (DD-MM-YYYY)
    data["invoice_date"] = normalize_invoice_date(data.get("invoice_date"))

    # Normalize empty strings & strip whitespace
    for key in ["seller_gstin", "buyer_gstin"]:
        val = data.get(key)
        if isinstance(val, str):
            cleaned = val.strip().upper()
            data[key] = cleaned if cleaned not in ("", "NULL", "NONE") else None
        else:
            data[key] = None

    # GSTIN length check (15 characters)
    for key in ["seller_gstin", "buyer_gstin"]:
        val = data.get(key)
        if val and len(val) != 15:
            data[key] = None

    # POS resolution (Statutory GST Rules under Sec 10 IGST Act):
    # 1. Retain extracted POS if valid 2-digit code
    # 2. For B2B, default to buyer state (destination)
    # 3. For B2C, default to seller state
    extracted_pos = str(data.get("pos") or "").strip()
    seller_gst = data.get("seller_gstin")
    buyer_gst = data.get("buyer_gstin")
    seller_state = seller_gst[:2] if (isinstance(seller_gst, str) and len(seller_gst) >= 2) else None
    buyer_state = buyer_gst[:2] if (isinstance(buyer_gst, str) and len(buyer_gst) >= 2) else None

    if len(extracted_pos) >= 2 and extracted_pos[:2].isdigit():
        data["pos"] = extracted_pos[:2]
    elif buyer_state:
        data["pos"] = buyer_state
    elif seller_state:
        data["pos"] = seller_state
    else:
        data["pos"] = None

    # Tax sanity check
    cgst = float(data.get("cgst") or 0.0)
    sgst = float(data.get("sgst") or 0.0)
    igst = float(data.get("igst") or 0.0)
    taxable = float(data.get("taxable_value") or 0.0)
    total = data.get("invoice_total")

    if total is not None:
        try:
            total_num = float(total)
            if abs((taxable + cgst + sgst + igst) - total_num) > 2.0:
                data["warning"] = "Tax mismatch"
        except (ValueError, TypeError):
            pass

    # Invoice type consistency
    data["invoice_type"] = "B2B" if data.get("buyer_gstin") else "B2C"

    return data
