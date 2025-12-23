
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from typing import Optional, Literal
from app.core.config import settings

import json

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Define the JSON structure for the AI
from pydantic import BaseModel
from typing import Optional, Literal

class InvoiceData(BaseModel):
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    seller_gstin: Optional[str]
    buyer_gstin: Optional[str]
    invoice_type: Literal["B2B", "B2C"]
    pos: Optional[str]
    taxable_value_before_discount: Optional[float]
    taxable_value: Optional[float]
    cgst: Optional[float]
    sgst: Optional[float]
    igst: Optional[float]
    invoice_total: Optional[float]


SYSTEM_PROMPT = """
You are a GST invoice extraction system.

Rules:
- Extract ONLY the fields defined in the schema
- If a field is missing, return null (JSON null)
- Do NOT guess values
- Do NOT calculate anything
- Dates must be in DD.MM.YYYY format
- invoice_type:
    - B2B if buyer_gstin exists
    - B2C otherwise
- Output ONLY valid JSON
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
