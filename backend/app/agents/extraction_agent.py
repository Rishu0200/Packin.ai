"""
Extraction agent: turns an invoice (PDF or photo) into structured JSON.

Design principle unchanged: this agent ONLY extracts. It never computes
box sizes, resolves brands, or writes to the database. The only change
from the single-provider version is resilience — if Claude is down/rate
limited, it falls back through Gemini -> Groq -> Hugging Face before
giving up, so a provider outage doesn't stop invoice processing.
"""
import json
import re
from app.config import EXTRACTION_PROVIDER_ORDER
from app.agents.providers import call_with_fallback

SYSTEM_PROMPT = """You are an invoice line-item extractor for a packaging \
company. Invoices list items like "17X18X8 THALI PC" where the numbers are \
box-relevant dimensions (dim1 x dim2 x dim3, always in that fixed order) \
and the trailing text names the product type (THALI, PLATE, MP, BPO, S/C, \
C/S, or similar).

Output ONLY a JSON object, no prose, no markdown fences:
{
  "invoice_no": "...",
  "date": "...",
  "party": "...",
  "line_items": [
    {"raw_description": "...", "dim1": int, "dim2": int, "dim3": int,
     "product_type": "...", "qty": number}
  ]
}

If a line's dimensions can't be confidently parsed, still include it with
"dim1": null, "dim2": null, "dim3": null and "unparsed": true — never \
invent numbers you're not confident about."""


def extract_invoice(file_bytes: bytes, media_type: str = "application/pdf") -> dict:
    result = call_with_fallback(
        system_prompt=SYSTEM_PROMPT,
        user_text="Extract all line items from this invoice.",
        file_bytes=file_bytes,
        media_type=media_type,
        provider_order=EXTRACTION_PROVIDER_ORDER,
    )

    if result["status"] == "all_providers_failed":
        return {"error": "all_providers_failed", "details": result["failed_providers"]}

    parsed = _parse_json_response(result["text"])
    parsed["_extraction_provider"] = result["provider"]  # for the activity/monitoring feed
    if result["failed_providers"]:
        parsed["_fallback_from"] = [f["provider"] for f in result["failed_providers"]]
    return parsed


def _parse_json_response(text: str) -> dict:
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "failed_to_parse_model_output", "raw": text}
