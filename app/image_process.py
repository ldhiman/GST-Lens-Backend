from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError, Field, field_validator
from typing import Optional, Literal
from app.core.config import settings
import json

client = genai.Client(api_key=settings.GEMINI_API_KEY)


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    seller_gstin: Optional[str] = None
    buyer_gstin: Optional[str] = None
    invoice_type: Optional[Literal["B2B", "B2C"]] = Field(default_factory=lambda: "B2C")
    pos: Optional[str] = None
    taxable_value: Optional[float] = None
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None
    invoice_total: Optional[float] = None

    @field_validator("invoice_type", mode="before")
    @classmethod
    def set_invoice_type_default(cls, v):
        return v if v in ("B2B", "B2C") else "B2C"


SYSTEM_PROMPT = """
You are a highly accurate GST invoice extraction system.

STRICT RULES:
- Extract ONLY visible data from the document
- DO NOT infer or calculate values
- If unsure, return null
- GSTIN must be exactly 15 characters
- All monetary values must be numbers (no symbols)
- Dates must be DD-MM-YYYY format
- If multiple invoices exist, return an array

LOGIC:
- invoice_type = "B2B" if buyer_gstin exists, else "B2C"

OUTPUT:
- Return ONLY valid JSON matching schema
- No explanation, no extra text
"""


def extract_invoice_data(file_bytes: bytes, mime_type: str):
    """Sends bytes directly to Gemini without saving to disk."""
    image_part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type,
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            SYSTEM_PROMPT,
            image_part,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InvoiceData,
        ),
    )

    print(response.text)

    try:
        parsed = json.loads(response.text)
        validated = InvoiceData.model_validate(parsed)
        return {
            "status": "success",
            "data": validated.model_dump()
        }

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON returned by model"
        }

    except ValidationError as e:
        return {
            "status": "error",
            "message": "Schema validation failed",
            "details": e.errors()
        }
