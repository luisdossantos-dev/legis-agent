"""
Langfuse configuration — disabled when no credentials are available.

Prevents the 401 Unauthorized errors from the OTel exporter
that spam the logs when no Langfuse API keys are configured.
"""

import logging
import os
from functools import wraps
from typing import Any, Callable, TypeVar

from app.core.config import settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Determine if Langfuse credentials are present
_has_credentials = bool(
    settings.LANGFUSE_PUBLIC_KEY.strip()
    and settings.LANGFUSE_SECRET_KEY.strip()
)


def observe(**kwargs: Any) -> Callable[[F], F]:
    """
    Conditional Langfuse observe decorator.

    If Langfuse credentials are configured, wraps the function
    with Langfuse tracing. Otherwise, returns the function unchanged.
    """
    if _has_credentials:
        from langfuse import observe as _langfuse_observe
        return _langfuse_observe(**kwargs)

    def passthrough(func: F) -> F:
        return func

    return passthrough


def init_langfuse() -> None:
    """Initialize Langfuse if credentials are available."""
    if not _has_credentials:
        logger.info(
            "Langfuse: no credentials configured. Tracing disabled."
        )
        return

    try:
        from langfuse import Langfuse

        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

        Langfuse()
        logger.info("Langfuse tracing enabled.")
    except Exception as e:
        logger.warning("Langfuse initialization failed: %s", e)
