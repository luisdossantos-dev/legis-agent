"""
Security headers middleware for the Legis Agent API.

Adds security-related HTTP headers to every response:
  - X-Content-Type-Options: nosniff       — prevents MIME type sniffing
  - X-Frame-Options: DENY                 — prevents clickjacking
  - Strict-Transport-Security             — enforces HTTPS (in production)
  - Content-Security-Policy               — restricts resource loading
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.responses import RedirectResponse

from app.core.config import settings


async def _https_redirect_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Redirect HTTP → HTTPS when ENFORCE_HTTPS is enabled.

    Must be registered as the outermost middleware so the redirect
    happens before any other processing (CORS, headers, etc.).
    Only active when settings.ENFORCE_HTTPS is True (local dev is False).
    """
    if settings.ENFORCE_HTTPS:
        url = request.url
        if url.scheme == "http" and url.port != 443:
            secure_url = url.replace(scheme="https", port=443)
            return RedirectResponse(url=str(secure_url), status_code=307)
    return await call_next(request)


async def _security_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Apply security headers to every outgoing response."""
    response = await call_next(request)

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Clickjacking protection
    response.headers["X-Frame-Options"] = "DENY"

    # Enforce HTTPS (browsers ignore on plain http connections)
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )

    # Restrict content loading — JSON API only needs minimal CSP
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )

    # No referrer information
    response.headers["Referrer-Policy"] = "no-referrer"

    # Disable sensitive browser APIs
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    # Cache-Control for GET responses to non-sensitive static data.
    # The system/config endpoint is polled every 5s by the frontend,
    # so the 2-second max-age reduces redundant requests.
    if request.method == "GET" and response.status_code == 200:
        path = request.url.path
        if path.startswith("/api/") and path not in (
            "/api/documents/",
            "/api/system/logs",
            "/api/observability/stats",
        ):
            # Static data endpoints: templates, types, models, schemas
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "max-age=30"

    return response


def add_https_redirect_middleware(app: FastAPI) -> None:
    """
    Register the HTTP→HTTPS redirect middleware.

    Registered as the outermost middleware so the redirect runs before
    all other processing (CORS, security headers, rate limiting).
    The middleware is a no-op when ENFORCE_HTTPS=False (local dev).
    """
    _ = app.middleware("http")(_https_redirect_middleware)


def add_security_headers_middleware(app: FastAPI) -> None:
    """
    Register a middleware that attaches security headers to every response.

    Must be registered AFTER CORS middleware so that CORS preflight
    responses also get the security headers.
    """

    # Register the middleware — all responses get security headers.
    _ = app.middleware("http")(_security_headers_middleware)
