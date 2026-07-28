"""
Multi-model router for email drafting.

Uses the same active provider as the main LLM system,
so the user's configured API key is respected.

Thin wrapper around the shared LiteLLM Router factory.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.runtime_config import PROVIDER_CONFIGS, get_active_model, get_active_provider
from app.core.router_factory import CachedRouter, _build_litellm_router, _build_shared_model_list

logger = logging.getLogger(__name__)


def _build_email_router() -> Optional[Any]:
    """Build a single-model LiteLLM Router for email drafting."""
    model_list = _build_shared_model_list(
        model_names=["primary"],
        extra_params={
            "max_tokens": 4096,
            "temperature": 0.3,
        },
    )
    if not model_list:
        return None
    return _build_litellm_router(
        model_list=model_list,
        num_retries=1,
        timeout=30,
    )


# Lazy router with config hash for cache invalidation
_email_router = CachedRouter(name="email", build_fn=_build_email_router)


def invalidate_email_router_cache() -> None:
    """Force the email router to be rebuilt on the next call."""
    _email_router.invalidate()


async def get_router() -> Optional[Any]:
    """Get or create the email router singleton."""
    return await _email_router.get()


def get_available_models() -> List[Dict[str, Any]]:
    """Return the list of configured models for debugging/UI."""
    provider_id = get_active_provider()
    pconf = PROVIDER_CONFIGS.get(provider_id, {})
    return [
        {
            "name": "primary",
            "model": get_active_model(),
            "provider": provider_id,
            "cost_tier": "configured",
            "best_for": ["all"],
            "max_tokens": 4096,
        }
    ]
