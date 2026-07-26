import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch
from app.agents.providers import call_with_fallback, ProviderError


def test_falls_back_to_second_provider_when_first_fails():
    def failing_claude(*args, **kwargs):
        raise ProviderError("anthropic", Exception("rate limited"))

    def working_gemini(*args, **kwargs):
        return '{"line_items": []}'

    with patch.dict("app.agents.providers.PROVIDER_FUNCTIONS", {
        "anthropic": failing_claude,
        "gemini": working_gemini,
    }):
        result = call_with_fallback("sys", "user", b"fakebytes", "image/jpeg",
                                     provider_order=["anthropic", "gemini"])

    assert result["status"] == "success"
    assert result["provider"] == "gemini"
    assert len(result["failed_providers"]) == 1
    assert result["failed_providers"][0]["provider"] == "anthropic"


def test_all_providers_failing_is_reported_clearly():
    def failing(*args, **kwargs):
        raise ProviderError("groq", Exception("timeout"))

    with patch.dict("app.agents.providers.PROVIDER_FUNCTIONS", {"groq": failing}):
        result = call_with_fallback("sys", "user", b"fakebytes", "image/jpeg",
                                     provider_order=["groq"])

    assert result["status"] == "all_providers_failed"
    assert result["failed_providers"][0]["provider"] == "groq"


def test_first_provider_success_skips_remaining():
    calls = []

    def working_claude(*args, **kwargs):
        calls.append("anthropic")
        return '{"line_items": []}'

    def should_not_be_called(*args, **kwargs):
        calls.append("gemini")
        return '{"line_items": []}'

    with patch.dict("app.agents.providers.PROVIDER_FUNCTIONS", {
        "anthropic": working_claude,
        "gemini": should_not_be_called,
    }):
        call_with_fallback("sys", "user", b"fakebytes", "image/jpeg",
                            provider_order=["anthropic", "gemini"])

    assert calls == ["anthropic"]
