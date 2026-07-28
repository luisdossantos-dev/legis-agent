"""
Runtime configuration manager.

Stores API keys and provider settings in a JSON file
so the user can update them at runtime via the UI without
needing to restart the backend.

Keys set here override the static .env values at runtime.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "runtime.json"

# ── Supported providers ──────────────────────────────────────
#
# Each provider config specifies:
#   - litellm_prefix: The prefix LiteLLM uses to route the request
#     (e.g. "openai", "anthropic", "google", "azure", "openrouter")
#   - models: List of short model names (prefix is added automatically
#     when building the LiteLLM model list)
#   - fields: Form fields shown in the UI settings panel
#   - defaults: Default values for extra fields (api_base, etc.)
#   - needs_api_base: If True, the litellm config includes api_base
#
PROVIDER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "docs_url": "https://platform.openai.com/api-keys",
        "env_key": "LITELLM_API_KEY",
        "litellm_prefix": "openai",
        "default_model": "gpt-5.6-sol",
        "models": [
            "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
            "gpt-5.5-instant", "gpt-5.5-thinking",
        ],
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "sk-..."},
        ],
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "docs_url": "https://console.anthropic.com/",
        "env_key": "ANTHROPIC_API_KEY",
        "litellm_prefix": "anthropic",
        "default_model": "claude-sonnet-5-20250609",
        "models": [
            "claude-sonnet-5-20250609", "claude-opus-5-20250720",
            "claude-fable-5-20250609", "claude-opus-4.8-20260625",
        ],
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "sk-ant-..."},
        ],
    },
    "google": {
        "label": "Google (Gemini)",
        "docs_url": "https://aistudio.google.com/apikey",
        "env_key": "GEMINI_API_KEY",
        "litellm_prefix": "google",
        "default_model": "gemini-3.6-flash-001",
        "models": [
            "gemini-3.6-flash-001", "gemini-3.5-flash-001",
            "gemini-3.5-flash-lite-001",
        ],
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "AIza..."},
        ],
    },
    "azure": {
        "label": "Microsoft Azure",
        "docs_url": "https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub",
        "env_key": "AZURE_API_KEY",
        "litellm_prefix": "azure",
        "default_model": "gpt-5.6-sol",
        "models": ["gpt-5.6-sol", "gpt-5.6-luna"],
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "..."},
            {"key": "api_base", "label": "Endpoint URL", "type": "text", "placeholder": "https://<resource>.openai.azure.com"},
            {"key": "api_version", "label": "API Version", "type": "text", "placeholder": "2024-10-21"},
        ],
        "defaults": {"api_base": "", "api_version": "2024-10-21"},
        "needs_api_base": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "docs_url": "https://openrouter.ai/keys",
        "env_key": "OPENROUTER_API_KEY",
        "litellm_prefix": "openrouter",
        "default_model": "openai/gpt-5.6-sol",
        "models": [
            "openai/gpt-5.6-sol", "openai/gpt-5.6-luna",
            "anthropic/claude-sonnet-5-20250609", "google/gemini-3.6-flash-001",
        ],
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "sk-or-..."},
        ],
    },
    "opencode-go": {
        "label": "OpenCode Go",
        "docs_url": "https://opencode.ai/auth",
        "env_key": "OPENCODE_API_KEY",
        # Uses OpenAI-compatible API — LiteLLM routes via "openai/" prefix + api_base
        "litellm_prefix": "openai",
        "default_model": "deepseek-v4-flash",
        "models": [
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "qwen3.7-max",
            "qwen3.7-plus",
            "kimi-k3",
            "kimi-k2.7-code",
            "mimo-v2.5-pro",
            "mimo-v2.5",
            "glm-5.2",
            "glm-5.1",
            "minimax-m3",
            "minimax-m2.7",
        ],
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "ocg_..."},
            {"key": "api_base", "label": "API Base URL", "type": "text", "placeholder": "https://opencode.ai/zen/go/v1"},
        ],
        "defaults": {"api_base": "https://opencode.ai/zen/go/v1"},
        "needs_api_base": True,
    },
}

DEFAULT_PROVIDER = "openai"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_raw() -> Dict[str, Any]:
    _ensure_config_dir()
    if not CONFIG_FILE.exists():
        return {"provider": DEFAULT_PROVIDER, "providers": {}}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load runtime config: %s", e)
        return {"provider": DEFAULT_PROVIDER, "providers": {}}


def _save_raw(data: Dict[str, Any]) -> None:
    _ensure_config_dir()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(CONFIG_FILE)


# ── Public API ───────────────────────────────────────────────

def get_active_provider() -> str:
    """Get the currently selected provider ID."""
    return _load_raw().get("provider", DEFAULT_PROVIDER)


def get_provider_config(provider_id: str) -> Dict[str, Any]:
    """Get the saved config for a specific provider."""
    data = _load_raw()
    providers = data.get("providers", {})
    return providers.get(provider_id, {})


def get_active_api_key() -> str:
    """Get the API key for the currently active provider."""
    provider_id = get_active_provider()
    provider_cfg = get_provider_config(provider_id)
    key = provider_cfg.get("api_key", "")
    if key:
        return key
    # Fall back to .env
    from app.core.config import settings
    return settings.LITELLM_API_KEY


def get_active_model() -> str:
    """Get the LiteLLM-compatible model name for the active provider.
    Returns e.g. "openai/gpt-4o" or "openai/deepseek-v4-flash".

    Strips any unknown prefix from saved model names (e.g. the
    old "opencode-go/" format) and replaces it with the provider's
    litellm_prefix so LiteLLM can route correctly.
    """
    provider_id = get_active_provider()
    pconf = PROVIDER_CONFIGS.get(provider_id, {})
    prefix = pconf.get("litellm_prefix", "openai")

    provider_cfg = get_provider_config(provider_id)
    model = provider_cfg.get("model", "").strip()

    if not model:
        model = pconf.get("default_model", "gpt-4o")

    # If model contains a prefix like "opencode-go/model" or "openai/model":
    if "/" in model:
        parts = model.split("/", 1)
        bare_model = parts[1]
        # Only keep the saved prefix if it matches the expected litellm_prefix
        if parts[0] == prefix:
            return model
        # Otherwise, use the correct prefix (e.g. "openai/" instead of "opencode-go/")
        return f"{prefix}/{bare_model}"

    return f"{prefix}/{model}"


def get_active_api_base() -> Optional[str]:
    """Get the API base URL for the currently active provider (if applicable)."""
    provider_id = get_active_provider()
    provider_cfg = get_provider_config(provider_id)
    saved = provider_cfg.get("api_base", "") or ""
    if saved:
        return saved
    return PROVIDER_CONFIGS.get(provider_id, {}).get("defaults", {}).get("api_base") or None


def set_active_provider(provider_id: str) -> None:
    """Set the active provider."""
    data = _load_raw()
    data["provider"] = provider_id
    _save_raw(data)
    logger.info("Active provider set to: %s", provider_id)


def update_provider_config(provider_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update config for a specific provider."""
    data = _load_raw()
    providers = data.setdefault("providers", {})
    if provider_id not in providers:
        providers[provider_id] = {}
    providers[provider_id].update(updates)
    # If this is the active provider, also set the provider in data
    if "provider" not in updates:
        data["provider"] = provider_id
    _save_raw(data)
    logger.info("Provider config updated: %s (%d fields)", provider_id, len(updates))
    return providers[provider_id]


def get_all() -> Dict[str, Any]:
    """Get the full runtime config."""
    return _load_raw()


def has_valid_api_key(provider_id: Optional[str] = None) -> bool:
    """Check if a valid API key exists for the given or active provider."""
    pid = provider_id or get_active_provider()
    cfg = get_provider_config(pid)
    key = cfg.get("api_key", "").strip()
    if key and key not in ("sk-your-api-key-here", ""):
        return True
    # Fall back to .env check
    from app.core.config import settings
    env_key = settings.LITELLM_API_KEY.strip()
    return bool(env_key) and env_key not in ("sk-your-api-key-here", "")


def config_status() -> Dict[str, Any]:
    """Return a summary of what's configured."""
    active = get_active_provider()
    return {
        "active_provider": active,
        "llm_available": has_valid_api_key(),
        "providers": {
            pid: {"configured": bool(get_provider_config(pid).get("api_key"))}
            for pid in PROVIDER_CONFIGS
        },
    }


def get_provider_list() -> List[Dict[str, Any]]:
    """Return the list of available providers with their metadata."""
    result = []
    for pid, cfg in PROVIDER_CONFIGS.items():
        saved = get_provider_config(pid)
        prefix = cfg.get("litellm_prefix", "openai")
        # Build full model names with prefix for display
        display_models = [
            f"{prefix}/{m}" if "/" not in m else m
            for m in cfg["models"]
        ]
        saved_model = saved.get("model", "")
        if saved_model and "/" in saved_model:
            # Strip any old/wrong prefix and use the provider's prefix
            bare = saved_model.split("/", 1)[1]
            current_display = f"{prefix}/{bare}"
        elif saved_model:
            current_display = f"{prefix}/{saved_model}"
        else:
            current_display = f"{prefix}/{cfg['default_model']}"
        result.append({
            "id": pid,
            "label": cfg["label"],
            "litellm_prefix": prefix,
            "docs_url": cfg["docs_url"],
            "default_model": f"{prefix}/{cfg['default_model']}" if "/" not in cfg['default_model'] else cfg['default_model'],
            "models": display_models,
            "fields": cfg["fields"],
            "defaults": cfg.get("defaults", {}),
            "configured": bool(saved.get("api_key")),
            "current_model": current_display,
        })
    return result
