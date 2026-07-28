"""
Correlation / Request ID middleware and utilities.

Provides:
  - A unique request ID for every incoming HTTP request
  - Propagation of X-Request-ID from client headers (if provided)
  - ContextVar for async-safe access to the current request ID
  - FastAPI dependency for use in route handlers and services
  - Logging filter to include request ID in all log entries
  - Response header so clients can reference the ID for support/debugging

Usage in route handlers:
    from app.core.request_id import get_request_id

    @router.get("/example")
    async def example(req_id: str = Depends(get_request_id)):
        logger.info("Processing request %s", req_id)
        ...

Usage in services (without Depends):
    from app.core.request_id import get_current_request_id

    async def some_service():
        req_id = get_current_request_id()
        ...
"""

import logging
import uuid
from contextvars import ContextVar

from fastapi import Request, Depends
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# ── Context variable ──────────────────────────────────
# Holds the current request ID across async boundaries
# (thread-safe, task-local).
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_current_request_id() -> str:
    """Get the current request ID from context (service layer)."""
    return _request_id_var.get()


# ── Logging filter ────────────────────────────────────

class RequestIDFilter(logging.Filter):
    """Injects the current request ID into every log record.

    Add to any logger to get [req_id] in log output:

        handler.addFilter(RequestIDFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_current_request_id()[:8] or "-"
        return True


# ── FastAPI dependency ────────────────────────────────

async def get_request_id(request: Request) -> str:
    """FastAPI dependency that returns the current request ID.

    Use in route handlers when you need the request ID explicitly:

        @router.get("/...")
        async def handler(req_id: str = Depends(get_request_id)):
            ...
    """
    return getattr(request.state, "request_id", get_current_request_id())


# ── Middleware ─────────────────────────────────────────

def _generate_request_id() -> str:
    """Generate a compact, URL-safe request ID."""
    return uuid.uuid4().hex[:12]  # 12 hex chars = 48 bits, plenty for traceability


class RequestIDMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that assigns a correlation ID to every request.

    The ID is:
      1. Taken from the X-Request-ID request header (if the client sent one)
      2. Otherwise generated as a unique hex string

    The ID is:
      - Stored in request.state for route handlers
      - Set in a ContextVar for service-layer access
      - Returned as X-Request-ID response header
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ):
        # ── Resolve request ID ──────────────────────────────
        req_id = request.headers.get("X-Request-ID", "")
        if not req_id or not req_id.strip():
            req_id = _generate_request_id()

        # Set in context for log filter and service layer
        token = _request_id_var.set(req_id)

        # Store in request state for route handlers
        request.state.request_id = req_id

        try:
            response = await call_next(request)
        finally:
            # Restore previous context value (cleanup)
            _request_id_var.reset(token)

        # Return the ID to the client so they can reference it
        response.headers["X-Request-ID"] = req_id

        return response
