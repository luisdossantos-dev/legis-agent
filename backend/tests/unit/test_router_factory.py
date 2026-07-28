"""Unit tests for router_factory.py — profile-aware model resolution."""

import pytest


class TestResolveProfileModel:
    """Tests for _resolve_profile_model(base_model, profile, provider_id)."""

    # ── Current gen models (2026) ────────────────────────────────

    def test_openai_sol_reasoning(self):
        """OpenAI gpt-5.6-sol with reasoning → gpt-5.6-sol."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("openai/gpt-5.6-sol", "reasoning") == "openai/gpt-5.6-sol"

    def test_openai_sol_fast(self):
        """OpenAI gpt-5.6-sol with fast → gpt-5.6-luna."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("openai/gpt-5.6-sol", "fast") == "openai/gpt-5.6-luna"

    def test_openai_unknown_model_fast(self):
        """OpenAI unknown model → falls back to provider default (luna)."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("openai/gpt-5.7-alpha", "fast") == "openai/gpt-5.6-luna"

    # ── Anthropic (2026) ─────────────────────────────────────────

    def test_anthropic_fable_fast(self):
        """Anthropic claude-fable-5 with fast → claude-sonnet-5."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("anthropic/claude-fable-5", "fast") == "anthropic/claude-sonnet-5"

    def test_anthropic_fable_reasoning(self):
        """Anthropic claude-fable-5 with reasoning → claude-fable-5."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("anthropic/claude-fable-5", "reasoning") == "anthropic/claude-fable-5"

    def test_anthropic_unknown_fast(self):
        """Anthropic unknown model → falls back to provider default."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("anthropic/claude-mythos-5", "fast") == "anthropic/claude-3.5-haiku"

    # ── Google (2026) ────────────────────────────────────────────

    def test_google_cheap(self):
        """Google gemini-3.6-flash with cheap → flash-lite."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("google/gemini-3.6-flash", "cheap") == "google/gemini-3.5-flash-lite"

    # ── DeepSeek (2026) ──────────────────────────────────────────

    def test_deepseek_v4_flash_reasoning(self):
        """DeepSeek v4-flash uses same model for all profiles."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("deepseek/deepseek-v4-flash", "reasoning") == "deepseek/deepseek-v4-flash"
        assert _resolve_profile_model("deepseek/deepseek-v4-flash", "fast") == "deepseek/deepseek-v4-flash"

    def test_deepseek_v4_pro_fast(self):
        """DeepSeek v4-pro with fast → v4-flash (cheaper sibling)."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("deepseek/deepseek-v4-pro", "fast") == "deepseek/deepseek-v4-flash"

    # ── Legacy model compatibility ───────────────────────────────

    def test_openai_gpt4o_still_maps(self):
        """Legacy gpt-4o still resolves correctly (old tests)."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("openai/gpt-4o", "reasoning") == "openai/gpt-4o"
        assert _resolve_profile_model("openai/gpt-4o", "fast") == "openai/gpt-4o-mini"

    # ── Unknown / fallback ───────────────────────────────────────

    def test_unknown_model_fallback(self):
        """Unknown model returns same model for any profile."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("ollama/llama3", "fast") == "ollama/llama3"
        assert _resolve_profile_model("ollama/llama3", "reasoning") == "ollama/llama3"
        assert _resolve_profile_model("ollama/llama3", "cheap") == "ollama/llama3"

    def test_unknown_profile_returns_base(self):
        """Unknown profile name returns base model."""
        from app.core.router_factory import _resolve_profile_model
        assert _resolve_profile_model("openai/gpt-5.6-sol", "nonexistent_profile") == "openai/gpt-5.6-sol"

    # ── Custom-endpoint providers (needs_api_base) ───────────────

    def test_opencode_go_uses_base_model(self):
        """opencode-go provider uses base model, not gpt-4o-mini."""
        from app.core.router_factory import _resolve_profile_model
        # opencode-go has needs_api_base=True → should skip profile substitution
        result = _resolve_profile_model(
            "openai/deepseek-v4-flash", "fast", provider_id="opencode-go",
        )
        assert result == "openai/deepseek-v4-flash"

    def test_azure_uses_base_model(self):
        """Azure provider uses base model for all profiles."""
        from app.core.router_factory import _resolve_profile_model
        result = _resolve_profile_model(
            "azure/gpt-4o", "fast", provider_id="azure",
        )
        assert result == "azure/gpt-4o"

    def test_standard_openai_still_substitutes(self):
        """Standard OpenAI provider still does profile substitution."""
        from app.core.router_factory import _resolve_profile_model
        result = _resolve_profile_model(
            "openai/gpt-5.6-sol", "fast", provider_id="openai",
        )
        assert result == "openai/gpt-5.6-luna"
