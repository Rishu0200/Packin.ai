"""
PO extraction agent — reads a scanned handwritten PO slip and proposes box
sizes + quantities, with the same Claude -> Gemini -> Groq -> Hugging Face
fallback chain as invoice extraction.

Handwriting is the hardest input this system sees, so having several
providers to fall back through matters more here than anywhere else —
a single provider's OCR having a bad day on messy handwriting shouldn't
block a PO from being processed.
"""
import json
import re
from app.config import EXTRACTION_PROVIDER_ORDER
from app.agents.providers import call_with_fallback

SYSTEM_PROMPT_TEMPLATE = """You are reading a handwritten purchase order \
slip for corrugated boxes. Valid box dimensions are ONLY these combinations:
dim1 must be one of: {dim1_values}
dim2 must be one of: {dim2_values}
dim3 must be one of: {dim3_values}
Valid brands are ONLY: {brand_names}

Output ONLY a JSON object, no prose, no markdown fences:
{{
  "items": [
    {{"dim1": int, "dim2": int, "dim3": int, "brand": "...", "qty": int,
      "confidence": "high"|"low"}}
  ]
}}

If handwriting is unclear or a number doesn't cleanly match the valid set, \
still give your best guess but set confidence to "low"."""


def extract_po_slip(image_bytes: bytes, media_type: str,
                     dim1_values: list[int], dim2_values: list[int],
                     dim3_values: list[int], brand_names: list[str]) -> dict:
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        dim1_values=dim1_values, dim2_values=dim2_values,
        dim3_values=dim3_values, brand_names=brand_names,
    )

    result = call_with_fallback(
        system_prompt=system_prompt,
        user_text="Extract all box orders from this PO slip.",
        file_bytes=image_bytes,
        media_type=media_type,
        provider_order=EXTRACTION_PROVIDER_ORDER,
    )

    if result["status"] == "all_providers_failed":
        return {"error": "all_providers_failed", "details": result["failed_providers"]}

    cleaned = re.sub(r"^```(json)?|```$", "", result["text"].strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "failed_to_parse_model_output", "raw": result["text"]}

    parsed["_extraction_provider"] = result["provider"]
    if result["failed_providers"]:
        parsed["_fallback_from"] = [f["provider"] for f in result["failed_providers"]]
    return parsed


def validate_po_item(item: dict, dim1_values: list[int], dim2_values: list[int],
                      dim3_values: list[int]) -> dict:
    """Hard validation against the real catalog — never trust the model's
    output blindly, even when it claims high confidence, and regardless of
    which provider produced it."""
    if item.get("dim1") not in dim1_values or item.get("dim2") not in dim2_values \
            or item.get("dim3") not in dim3_values:
        return {"status": "invalid", "reason": "Not a real catalog box size — likely misread"}
    if item.get("confidence") == "low":
        return {"status": "needs_review", "reason": "Low OCR confidence on handwriting"}
    return {"status": "valid"}
