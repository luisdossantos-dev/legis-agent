"""
Shared LiteLLM Router factory.

Extracts the common pattern of building, caching, and invalidating a LiteLLM
Router so that the main LLM module and the email-drafting module don't
duplicate the same logic.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.runtime_config import (
    PROVIDER_CONFIGS,
    get_active_api_base,
    get_active_api_key,
    get_active_model,
    get_active_provider,
    get_provider_config,
    has_valid_api_key,
)

logger = logging.getLogger(__name__)


def _has_valid_api_key() -> bool:
    """Check if a valid API key is available (runtime or .env)."""
    if has_valid_api_key():
        return True
    # Also check settings directly (belt-and-suspenders)
    from app.core.config import settings
    key = settings.LITELLM_API_KEY.strip()
    return bool(key) and key not in ("sk-your-api-key-here", "")


def _resolve_api_key() -> str:
    """Get the active API key — runtime config takes precedence."""
    key = get_active_api_key()
    if key:
        return key
    from app.core.config import settings
    return settings.LITELLM_API_KEY


def _config_hash() -> str:
    """Compute a hash of the current provider config for cache invalidation."""
    raw = json.dumps({
        "provider": get_active_provider(),
        "model": get_active_model(),
        "api_key": (_resolve_api_key() or "")[-8:],
        "api_base": get_active_api_base(),
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Profile-aware model resolution ─────────────────────────────
# Maps each base model to faster/cheaper alternatives per profile.
# Supports all major providers; unknown models fall back gracefully.

_MODEL_FAMILIES: Dict[str, Dict[str, str]] = {
    # ── OpenAI (2026) ────────────────────────────────────────────
    "openai/gpt-5.6-sol":           {"reasoning": "openai/gpt-5.6-sol",      "fast": "openai/gpt-5.6-luna",   "cheap": "openai/gpt-5.6-luna"},
    "openai/gpt-5.6-terra":         {"reasoning": "openai/gpt-5.6-terra",    "fast": "openai/gpt-5.6-luna",   "cheap": "openai/gpt-5.6-luna"},
    "openai/gpt-5.6-luna":          {"reasoning": "openai/gpt-5.6-luna",     "fast": "openai/gpt-5.6-luna",   "cheap": "openai/gpt-5.6-luna"},
    "openai/gpt-5.5-instant":       {"reasoning": "openai/gpt-5.5-thinking",  "fast": "openai/gpt-5.5-instant", "cheap": "openai/gpt-5.5-instant"},
    "openai/gpt-5.5-thinking":      {"reasoning": "openai/gpt-5.5-thinking",  "fast": "openai/gpt-5.5-instant", "cheap": "openai/gpt-5.5-instant"},
    "openai/gpt-5.4-nano":          {"reasoning": "openai/gpt-5.4-nano",     "fast": "openai/gpt-5.4-nano",   "cheap": "openai/gpt-5.4-nano"},
    # Legacy OpenAI (still in API, being phased out of ChatGPT)
    "openai/gpt-4o":                {"reasoning": "openai/gpt-4o",           "fast": "openai/gpt-4o-mini",    "cheap": "openai/gpt-4o-mini"},
    "openai/gpt-4o-mini":           {"reasoning": "openai/gpt-4o-mini",      "fast": "openai/gpt-4o-mini",    "cheap": "openai/gpt-4o-mini"},

    # ── Anthropic (2026) ────────────────────────────────────────
    "anthropic/claude-fable-5":     {"reasoning": "anthropic/claude-fable-5",  "fast": "anthropic/claude-sonnet-5", "cheap": "anthropic/claude-sonnet-5"},
    "anthropic/claude-opus-5":      {"reasoning": "anthropic/claude-opus-5",   "fast": "anthropic/claude-sonnet-5", "cheap": "anthropic/claude-sonnet-5"},
    "anthropic/claude-sonnet-5":    {"reasoning": "anthropic/claude-sonnet-5",  "fast": "anthropic/claude-sonnet-5", "cheap": "anthropic/claude-sonnet-5"},
    "anthropic/claude-opus-4.8":    {"reasoning": "anthropic/claude-opus-4.8",  "fast": "anthropic/claude-sonnet-5", "cheap": "anthropic/claude-sonnet-5"},
    "anthropic/claude-opus-4.7":    {"reasoning": "anthropic/claude-opus-4.7",  "fast": "anthropic/claude-sonnet-5", "cheap": "anthropic/claude-sonnet-5"},
    "anthropic/claude-sonnet-4":    {"reasoning": "anthropic/claude-sonnet-4",  "fast": "anthropic/claude-sonnet-5", "cheap": "anthropic/claude-sonnet-5"},
    # Legacy Anthropic (cheapest available)
    "anthropic/claude-3.5-haiku":   {"reasoning": "anthropic/claude-3.5-haiku", "fast": "anthropic/claude-3.5-haiku", "cheap": "anthropic/claude-3.5-haiku"},
    "anthropic/claude-3-haiku":     {"reasoning": "anthropic/claude-3-haiku",   "fast": "anthropic/claude-3-haiku",   "cheap": "anthropic/claude-3-haiku"},

    # ── Google Gemini (2026) ────────────────────────────────────
    "google/gemini-3.6-flash":       {"reasoning": "google/gemini-3.6-flash",       "fast": "google/gemini-3.6-flash",        "cheap": "google/gemini-3.5-flash-lite"},
    "google/gemini-3.5-flash":       {"reasoning": "google/gemini-3.5-flash",       "fast": "google/gemini-3.5-flash",        "cheap": "google/gemini-3.5-flash-lite"},
    "google/gemini-3.5-flash-lite":  {"reasoning": "google/gemini-3.5-flash-lite",  "fast": "google/gemini-3.5-flash-lite",   "cheap": "google/gemini-3.5-flash-lite"},
    # Legacy Gemini
    "google/gemini-2.0-flash":       {"reasoning": "google/gemini-2.0-flash",       "fast": "google/gemini-2.0-flash",        "cheap": "google/gemini-2.5-flash"},
    "google/gemini-2.5-flash":       {"reasoning": "google/gemini-2.5-flash",       "fast": "google/gemini-2.5-flash",        "cheap": "google/gemini-2.0-flash-lite"},

    # ── DeepSeek (2026) ─────────────────────────────────────────
    "deepseek/deepseek-v4-flash":   {"reasoning": "deepseek/deepseek-v4-flash", "fast": "deepseek/deepseek-v4-flash", "cheap": "deepseek/deepseek-v4-flash"},
    "deepseek/deepseek-v4-pro":     {"reasoning": "deepseek/deepseek-v4-pro",   "fast": "deepseek/deepseek-v4-flash", "cheap": "deepseek/deepseek-v4-flash"},
    "deepseek/deepseek-chat":       {"reasoning": "deepseek/deepseek-v4-flash", "fast": "deepseek/deepseek-v4-flash", "cheap": "deepseek/deepseek-v4-flash"},
    "deepseek/deepseek-reasoner":   {"reasoning": "deepseek/deepseek-v4-flash", "fast": "deepseek/deepseek-v4-flash", "cheap": "deepseek/deepseek-v4-flash"},

    # ── Mistral (2026) ──────────────────────────────────────────
    "mistral/mistral-large-3":      {"reasoning": "mistral/mistral-large-3", "fast": "mistral/mistral-small-4", "cheap": "mistral/mistral-small-4"},
    "mistral/mistral-small-4":      {"reasoning": "mistral/mistral-small-4", "fast": "mistral/mistral-small-4", "cheap": "mistral/mistral-small-4"},
    "mistral/mistral-large":        {"reasoning": "mistral/mistral-large",   "fast": "mistral/mistral-small-4", "cheap": "mistral/mistral-small-4"},
    "mistral/mistral-small":        {"reasoning": "mistral/mistral-small",   "fast": "mistral/mistral-small-4", "cheap": "mistral/mistral-small-4"},

    # ── Groq (2026) ─────────────────────────────────────────────
    "groq/llama-3.3-70b":           {"reasoning": "groq/llama-3.3-70b",     "fast": "groq/llama-3.1-8b",      "cheap": "groq/llama-3.1-8b"},
    "groq/llama-3.1-8b":            {"reasoning": "groq/llama-3.1-8b",      "fast": "groq/llama-3.1-8b",      "cheap": "groq/llama-3.1-8b"},
    "groq/qwen-3.6-27b":            {"reasoning": "groq/qwen-3.6-27b",      "fast": "groq/llama-3.1-8b",      "cheap": "groq/llama-3.1-8b"},
}

# Provider-level defaults for unknown models (matched by prefix).
# Providers with ``needs_api_base`` (custom endpoints) are excluded
# so their models aren't substituted with OpenAI/Anthropic variants.
# (handled at the top of _resolve_profile_model).
_PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "openai/":     {"reasoning": None, "fast": "openai/gpt-5.6-luna", "cheap": "openai/gpt-5.6-luna"},
    "anthropic/":  {"reasoning": None, "fast": "anthropic/claude-3.5-haiku", "cheap": "anthropic/claude-3.5-haiku"},
    "google/":     {"reasoning": None, "fast": None, "cheap": None},
    "deepseek/":   {"reasoning": None, "fast": "deepseek/deepseek-v4-flash", "cheap": "deepseek/deepseek-v4-flash"},
    "mistral/":    {"reasoning": None, "fast": "mistral/mistral-small-4", "cheap": "mistral/mistral-small-4"},
    "groq/":       {"reasoning": None, "fast": "groq/llama-3.1-8b", "cheap": "groq/llama-3.1-8b"},
}


def _resolve_profile_model(
    base_model: str,
    profile: str,
    provider_id: Optional[str] = None,
) -> str:
    """Resolve a model name for the given profile.

    Args:
        base_model: The user-configured model (e.g. "openai/gpt-4o").
        profile: The routing profile ("reasoning", "fast", "cheap", etc.).
        provider_id: The active provider ID (e.g. "openai", "opencode-go").
            When set, checks if the provider uses a custom API endpoint;
            custom-endpoint providers always use the base model.

    Returns:
        The model name to use for this profile. Falls back to base_model
        when no alternative is known for the given provider/model.
    """
    # 0. Custom-endpoint providers (e.g. opencode-go, Azure) use their
    #    own model inventory — don't substitute with generic models.
    if provider_id:
        pconf = PROVIDER_CONFIGS.get(provider_id)
        if pconf and pconf.get("needs_api_base"):
            return base_model

    # 1. Exact model match
    if base_model in _MODEL_FAMILIES:
        alternatives = _MODEL_FAMILIES[base_model]
        if profile in alternatives:
            return alternatives[profile]
        return base_model

    # 2. Provider prefix match (for unknown models within known providers)
    for prefix, defaults in _PROVIDER_DEFAULTS.items():
        if base_model.startswith(prefix):
            if profile in defaults and defaults[profile] is not None:
                return defaults[profile]
            return base_model

    # 3. Unknown provider — use base model for everything
    return base_model


def _build_shared_model_list(
    model_names: List[str],
    extra_params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build a LiteLLM model list for the given model names.

    Each entry shares the same provider config (api_key, api_base, etc.).

    Args:
        model_names: One or more model_name values for the Router.
        extra_params: Extra litellm params to merge (e.g. temperature override).

    Returns:
        Model list suitable for LiteLLM Router, or empty list if no valid key.
    """
    api_key = _resolve_api_key()
    if not api_key or api_key in ("sk-your-api-key-here", ""):
        return []

    api_base = get_active_api_base()
    provider_id = get_active_provider()

    base_params: Dict[str, Any] = {
        "api_key": api_key,
    }
    if api_base:
        base_params["api_base"] = api_base

    pcfg = get_provider_config(provider_id)
    if "api_version" in pcfg:
        base_params["api_version"] = pcfg["api_version"]

    # Apply overrides from the caller
    if extra_params:
        base_params.update(extra_params)

    model_list = []
    provider_id = get_active_provider()
    for name in model_names:
        params = dict(base_params)
        # Resolve per-profile model (fast → gpt-4o-mini, reasoning → gpt-4o, etc.)
        resolved_model = _resolve_profile_model(
            get_active_model(), name, provider_id=provider_id,
        )
        params["model"] = resolved_model
        model_list.append({
            "model_name": name,
            "litellm_params": params,
        })

    # Log the profile→model mapping for debugging
    logger.debug(
        "Model list built: %s",
        {m["model_name"]: m["litellm_params"]["model"] for m in model_list},
    )
    return model_list


def _build_litellm_router(
    model_list: List[Dict[str, Any]],
    num_retries: int = 3,
    retry_after: float = 1.0,
    timeout: int = 60,
) -> Any:
    """Instantiate a LiteLLM Router with the given model list and options.

    Args:
        model_list: Model list from _build_shared_model_list (or equivalent).
        num_retries: Number of retries on transient failures.
        retry_after: Base delay before first retry (seconds).
        timeout: Request timeout in seconds.

    Returns:
        A litellm.Router instance, or None if no model list was provided.
    """
    if not model_list:
        return None

    from litellm import Router

    return Router(
        model_list=model_list,
        num_retries=num_retries,
        retry_after=retry_after,
        timeout=timeout,
    )


class CachedRouter:
    """Lazy-initialised LiteLLM Router with config-hash cache invalidation.

    Usage:
        router = CachedRouter(
            name="my_router",
            build_fn=lambda: build_model_and_router(...),
        )

        r = await router.get()  # returns Router or None
        router.invalidate()     # force rebuild on next get()
    """

    def __init__(
        self,
        name: str,
        build_fn: Any,
    ) -> None:
        """
        Args:
            name: Human-readable name for logging.
            build_fn: A zero-argument callable that returns a Router or None.
        """
        self.name = name
        self._build_fn = build_fn
        self._router: Any = None
        self._cached_hash: Optional[str] = None

    def invalidate(self) -> None:
        """Force the router to be rebuilt on the next call."""
        if self._router is not None:
            self._router = None
            self._cached_hash = None
            logger.debug("Router '%s' cache invalidated", self.name)

    async def get(self) -> Any:
        """Return the cached Router, rebuilding if the config has changed."""
        if not _has_valid_api_key():
            return None

        current_hash = _config_hash()

        if self._router is not None and current_hash != self._cached_hash:
            logger.info(
                "Router '%s': config changed (hash: %s -> %s), rebuilding",
                self.name, self._cached_hash, current_hash,
            )
            self._router = None

        if self._router is None:
            self._router = self._build_fn()
            if self._router is not None:
                self._cached_hash = current_hash
                logger.info(
                    "Router '%s' created: provider=%s, model=%s",
                    self.name, get_active_provider(), get_active_model(),
                )

        return self._router
