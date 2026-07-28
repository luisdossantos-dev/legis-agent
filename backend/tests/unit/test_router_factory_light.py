"""Lightweight tests for router_factory profile resolution — pure function."""

from app.core.router_factory import _resolve_profile_model


class TestResolveProfileModel:
    def test_openai_current_reasoning(self):
        assert _resolve_profile_model("openai/gpt-5.6-sol", "reasoning") == "openai/gpt-5.6-sol"

    def test_openai_current_fast(self):
        assert _resolve_profile_model("openai/gpt-5.6-sol", "fast") == "openai/gpt-5.6-luna"

    def test_openai_legacy_gpt4o_still_works(self):
        assert _resolve_profile_model("openai/gpt-4o", "fast") == "openai/gpt-4o-mini"

    def test_anthropic_fable_fast(self):
        assert _resolve_profile_model("anthropic/claude-fable-5", "fast") == "anthropic/claude-sonnet-5"

    def test_anthropic_sonnet_5_reasoning(self):
        assert _resolve_profile_model("anthropic/claude-sonnet-5", "reasoning") == "anthropic/claude-sonnet-5"

    def test_google_cheap(self):
        assert _resolve_profile_model("google/gemini-3.6-flash", "cheap") == "google/gemini-3.5-flash-lite"

    def test_unknown_model_fallback(self):
        assert _resolve_profile_model("ollama/llama3", "fast") == "ollama/llama3"
        assert _resolve_profile_model("ollama/llama3", "reasoning") == "ollama/llama3"

    def test_deepseek_v4_pro_fast(self):
        assert _resolve_profile_model("deepseek/deepseek-v4-pro", "fast") == "deepseek/deepseek-v4-flash"

    def test_deepseek_v4_flash_fast(self):
        assert _resolve_profile_model("deepseek/deepseek-v4-flash", "fast") == "deepseek/deepseek-v4-flash"

    def test_groq_llama33_fast_now_maps(self):
        assert _resolve_profile_model("groq/llama-3.3-70b", "fast") == "groq/llama-3.1-8b"

    def test_custom_endpoint_uses_base_model(self):
        assert _resolve_profile_model("openai/deepseek-v4-flash", "fast", provider_id="opencode-go") == "openai/deepseek-v4-flash"

    def test_unknown_profile_returns_base(self):
        assert _resolve_profile_model("openai/gpt-5.6-sol", "nonexistent_profile") == "openai/gpt-5.6-sol"
