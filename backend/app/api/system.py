"""
System API endpoints.
GET /api/system/logs — View recent error logs.
GET /api/system/logs/summary — Error summary grouped by source.
GET /api/system/config — View current runtime configuration and available providers.
POST /api/system/config — Update runtime configuration.
POST /api/system/config/provider — Set active provider and its config.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.cache import cached_result, cache_get, cache_set
from app.core.email_llm import invalidate_email_router_cache
from app.core.llm import invalidate_router_cache
from app.core.logging import get_error_summary, get_recent_errors
from app.core.runtime_config import (
    PROVIDER_CONFIGS,
    config_status as _config_status,
    get_all,
    get_provider_list,
    get_provider_config,
    set_active_provider,
    update_provider_config,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/logs")
async def list_logs(limit: int = 50):
    """Return recent error log entries."""
    return {"logs": get_recent_errors(limit=limit)}


@router.get("/logs/summary")
async def logs_summary():
    """Return error summary grouped by source."""
    return get_error_summary()


# Cache for the config endpoint (invalidated on config updates)
_config_cache = cached_result(ttl_seconds=2)


@router.get("/providers")
async def list_providers():
    """Return the list of available LLM providers with their metadata."""
    return {"providers": get_provider_list()}


@router.get("/config")
async def get_config():
    """Return current runtime configuration, provider list, and status (cached 2s)."""
    cached = cache_get(_config_cache)
    if cached is not None:
        return JSONResponse(content=cached, headers={"Cache-Control": "max-age=2"})

    data = {
        "runtime": get_all(),
        "providers": get_provider_list(),
        "status": _config_status(),
    }
    cache_set(_config_cache, data)
    return JSONResponse(content=data, headers={"Cache-Control": "max-age=2"})


@router.post("/config")
async def update_config(updates: Dict[str, Any]):
    """
    Legacy endpoint: update runtime configuration.

    Deprecated — use POST /config/provider for provider-specific config.
    """
    allowed_keys = {"embedding_mode"}
    sanitized = {k: v for k, v in updates.items() if k in allowed_keys}
    if not sanitized:
        raise HTTPException(status_code=400, detail="No valid config keys provided.")
    from app.core.runtime_config import _save_raw, _load_raw
    data = _load_raw()
    data.update(sanitized)
    _save_raw(data)
    return {"updated": list(sanitized.keys()), "status": _config_status()}


@router.post("/config/provider")
async def set_provider(body: Dict[str, Any]):
    # Invalidate config cache on provider change
    _config_cache["value"] = None
    """
    Set the active provider and/or update its configuration.

    Request body:
    {
        "provider": "openai",              // provider ID to activate
        "api_key": "sk-...",               // optional: new API key
        "model": "openai/gpt-4o",          // optional: model override
        "api_base": "https://...",         // optional: custom endpoint
        "api_version": "2024-..."          // optional: API version (Azure)
    }
    """
    provider_id = body.get("provider", "")
    if not provider_id:
        raise HTTPException(status_code=400, detail="'provider' field is required.")

    if provider_id not in PROVIDER_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider_id}'. Available: {', '.join(PROVIDER_CONFIGS.keys())}",
        )

    # Build provider config update
    provider_fields = {f["key"] for f in PROVIDER_CONFIGS[provider_id]["fields"]}
    provider_update = {}
    for key in provider_fields:
        if key in body and body[key] is not None:
            provider_update[key] = str(body[key]).strip()
    if "model" in body and body["model"]:
        provider_update["model"] = str(body["model"]).strip()

    # Save
    if provider_update:
        update_provider_config(provider_id, provider_update)
    set_active_provider(provider_id)

    log_safe = {k: (v[:12] + "..." if "key" in k and len(v) > 16 else v) for k, v in provider_update.items()}
    logger.info("Provider '%s' configured: %s", provider_id, log_safe)

    # Invalidate LLM router caches so the new config takes effect immediately
    invalidate_router_cache()
    invalidate_email_router_cache()

    return {
        "provider": provider_id,
        "updated": list(provider_update.keys()),
        "status": _config_status(),
    }
