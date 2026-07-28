"""
Performance profiling utilities.

Provides request timing middleware and a decorator for tracking
execution times of critical paths. Slow requests are logged
as warnings for bottleneck identification.
"""

import logging
import time
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Thresholds for slow request warnings
SLOW_REQUEST_WARN_MS = 5000   # warn on requests > 5s
CRITICAL_REQUEST_WARN_MS = 30000  # critical warning > 30s


class RequestTimingMiddleware:
    """
    ASGI middleware that logs request duration.

    Warnings are emitted for requests exceeding thresholds,
    making performance bottlenecks observable without a
    dedicated profiling dashboard.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")

        await self.app(scope, receive, send)

        elapsed_ms = (time.monotonic() - start) * 1000

        if elapsed_ms > CRITICAL_REQUEST_WARN_MS:
            logger.warning(
                "🐢 CRITICAL slow request: %s %s — %.0fms",
                method, path, elapsed_ms,
            )
        elif elapsed_ms > SLOW_REQUEST_WARN_MS:
            logger.info(
                "🐢 Slow request: %s %s — %.0fms",
                method, path, elapsed_ms,
            )
        else:
            logger.debug(
                "Request: %s %s — %.0fms",
                method, path, elapsed_ms,
            )


def add_profiling_middleware(app: FastAPI) -> None:
    """
    Register the request timing middleware.

    Registered as the outermost middleware so it captures the
    full request/response cycle including all other middleware.
    """
    app.add_middleware(RequestTimingMiddleware)


def timed(logger_name: str = __name__) -> Callable:
    """
    Decorator that logs the execution time of an async function.

    Usage:
        @timed("app.core.llm")
        async def llm_complete(...):
            ...
    """
    _logger = logging.getLogger(logger_name)

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000
                if elapsed_ms > SLOW_REQUEST_WARN_MS:
                    _logger.warning(
                        "⏱ %s took %.0fms",
                        func.__name__, elapsed_ms,
                    )
                else:
                    _logger.debug(
                        "⏱ %s took %.0fms",
                        func.__name__, elapsed_ms,
                    )
        return wrapper
    return decorator
