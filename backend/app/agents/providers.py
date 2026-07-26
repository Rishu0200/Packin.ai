"""
Wraps each backup LLM provider behind the same simple interface:
    call(system_prompt, user_text, file_bytes, media_type) -> raw text output

Used by extraction_agent.py and po_extraction_agent.py to build a fallback
chain: Claude (primary) -> Gemini -> Groq -> Hugging Face. Every provider
here ONLY returns text; none of them touch the database. Parsing/validation
stays centralized in the calling agent so the fallback is transparent to
the rest of the pipeline.
"""
import base64
from app.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    GEMINI_API_KEY, GEMINI_MODEL,
    GROQ_API_KEY, GROQ_VISION_MODEL,
    HF_API_TOKEN, HF_VISION_MODEL,
)


class ProviderError(Exception):
    """Raised when a provider fails so the fallback chain can move on."""
    def __init__(self, provider: str, original: Exception):
        self.provider = provider
        self.original = original
        super().__init__(f"{provider} failed: {original}")


def call_claude(system_prompt: str, user_text: str, file_bytes: bytes, media_type: str) -> str:
    from anthropic import Anthropic
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        encoded = base64.standard_b64encode(file_bytes).decode("utf-8")
        block_type = "document" if media_type == "application/pdf" else "image"
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {"type": block_type, "source": {"type": "base64", "media_type": media_type,
                                                      "data": encoded}},
                    {"type": "text", "text": user_text},
                ],
            }],
        )
        return "".join(b.text for b in response.content if b.type == "text")
    except Exception as e:
        raise ProviderError("anthropic", e)


def call_gemini(system_prompt: str, user_text: str, file_bytes: bytes, media_type: str) -> str:
    """Gemini 3.6 Flash — chosen for its high throughput on document/data
    extraction workloads at a lower cost than the previous Flash tier."""
    from google import genai
    from google.genai import types
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=media_type),
                f"{system_prompt}\n\n{user_text}",
            ],
        )
        return response.text
    except Exception as e:
        raise ProviderError("gemini", e)


def call_groq(system_prompt: str, user_text: str, file_bytes: bytes, media_type: str) -> str:
    """Groq's qwen/qwen3.6-27b — a 27B multimodal model with JSON mode,
    served on Groq's LPU hardware for very fast turnaround."""
    from groq import Groq
    try:
        client = Groq(api_key=GROQ_API_KEY)
        encoded = base64.standard_b64encode(file_bytes).decode("utf-8")
        data_uri = f"data:{media_type};base64,{encoded}"
        response = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ]},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        raise ProviderError("groq", e)


def call_huggingface(system_prompt: str, user_text: str, file_bytes: bytes, media_type: str) -> str:
    """Qwen2.5-VL-7B-Instruct via HF Inference Providers — tuned for
    documents, layouts, and structured output; the strongest general-purpose
    open-weight choice for invoice/PO OCR."""
    from huggingface_hub import InferenceClient
    try:
        client = InferenceClient(token=HF_API_TOKEN)
        encoded = base64.standard_b64encode(file_bytes).decode("utf-8")
        data_uri = f"data:{media_type};base64,{encoded}"
        response = client.chat.completions.create(
            model=HF_VISION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ]},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        raise ProviderError("huggingface", e)


PROVIDER_FUNCTIONS = {
    "anthropic": call_claude,
    "gemini": call_gemini,
    "groq": call_groq,
    "huggingface": call_huggingface,
}


def call_with_fallback(system_prompt: str, user_text: str, file_bytes: bytes,
                        media_type: str, provider_order: list[str]) -> dict:
    """Tries each provider in order. Returns the first success, along with
    which providers failed along the way — useful both for debugging and
    for the activity/monitoring feed (see app/routers/activity.py)."""
    attempts = []
    for provider_name in provider_order:
        fn = PROVIDER_FUNCTIONS.get(provider_name.strip())
        if not fn:
            continue
        try:
            text = fn(system_prompt, user_text, file_bytes, media_type)
            return {"status": "success", "provider": provider_name, "text": text,
                    "failed_providers": attempts}
        except ProviderError as e:
            attempts.append({"provider": provider_name, "error": str(e.original)})
            continue

    return {"status": "all_providers_failed", "failed_providers": attempts}
