"""
LiteLLM routing API endpoints.
GET /api/routing/status — Show multi-provider routing configuration.
"""

import logging

from fastapi import APIRouter

from app.core.routing import ALL_PROFILES, PROFILE_DESCRIPTIONS, get_profile_config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
async def routing_status():
    """Show the multi-provider routing configuration."""
    config = get_profile_config()

    # Check the active provider
    from app.core.runtime_config import get_active_provider, config_status

    provider_id = get_active_provider()

    return {
        "active_provider": provider_id,
        "provider_config": config_status(),
        "routing_strategy": config.get("strategy", "auto"),
        "criteria": config.get("criteria", []),
        "profiles": [
            {
                "name": p,
                "description": PROFILE_DESCRIPTIONS.get(p, ""),
                "available": config.get("profiles", {}).get(p, {}).get("available", False),
                "model_name": p,
            }
            for p in ALL_PROFILES
        ],
        "notes": {
            "auto_select": "llm_complete() auto-selects the best profile based on criteria",
            "override": "Pass profile=, model=, sensitivity=, language=, urgent=, or prefer_cheap= to override",
        },
    }
