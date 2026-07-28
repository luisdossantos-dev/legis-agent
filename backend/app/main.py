"""
Legis Agent — FastAPI Backend
Main entry point with lifespan management.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from starlette.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import act_generation, agents, cases, clause_review, conversations, deeds, documents, dynamic_templates, email, email_action, email_classifier, observability, orchestrator, pdf_extraction, rbac, routing_endpoint, security, system, timeline
from app.core.config import settings
from app.core.langfuse import init_langfuse
from app.core.profiler import add_profiling_middleware
from app.core.rate_limit import limiter
from app.core.request_id import RequestIDFilter, RequestIDMiddleware
from app.core.security_headers import add_https_redirect_middleware, add_security_headers_middleware

# ── Logging configuration ────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
)

# Add request ID filter to the root logger so every log entry
# includes the current correlation ID (visible in journald, files, etc.)
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIDFilter())

# Suppress noisy third-party loggers
for noisy_logger in [
    "opentelemetry",
    "LiteLLM",
    "LiteLLM Router",
    "LiteLLM Proxy",
    "httpx",
    "httpcore",
    "openai._base_client",
]:
    logging.getLogger(noisy_logger).setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("🚀 Legis Agent backend starting...")
    logger.info(f"   Vector store: {settings.VECTOR_STORE_PROVIDER}")
    logger.info(f"   Primary model: {settings.LITELLM_MODEL}")

    # Initialize Langfuse (no-op if no credentials configured)
    init_langfuse()

    yield
    logger.info("👋 Legis Agent backend stopped.")


app = FastAPI(
    title="Legis Agent API",
    description="API for legal/notarial document analysis and drafting",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Request correlation ID (outermost middleware) ────────────
# Assigns a unique X-Request-ID to every request, logs it, and
# returns it in the response header. Placed first so the ID is
# available to all downstream middleware and route handlers.
app.add_middleware(RequestIDMiddleware)

# ── Rate limiting ────────────────────────────────────────────
# Role-aware rate limiter with slowapi.
# Admins: 200/min, Stagiaires: 20/min.
# A middleware extracts the user role and sets request.state.auth_role
# so the rate limiter's key function can use it.


@app.middleware("http")
async def _inject_auth_role_for_ratelimit(request: Request, call_next):
    """Extract user role from auth context and inject into request state."""
    # Check if auth middleware already set the auth context
    auth_ctx = getattr(request.state, "auth_context", None)
    if auth_ctx and hasattr(auth_ctx, "role"):
        request.state.auth_role = auth_ctx.role.value if hasattr(auth_ctx.role, "value") else str(auth_ctx.role)
    else:
        # Fallback: check header (dev mode)
        request.state.auth_role = request.headers.get("X-User-Role", "")
    return await call_next(request)


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Response compression for large payloads (>1 KB) ─────────
# Compresses JSON responses (analysis results, clause reviews,
# document lists) to reduce bandwidth.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS — allow connections from the Tauri frontend and dev servers.
# Origins are explicitly listed in settings.CORS_ORIGINS.
# Methods and headers are restricted to what the application needs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-User-Id",
        "X-User-Role",
        "X-User-Office",
        "X-User-Name",
    ],
)

# ── Security headers middleware ────────────────────────────
# Added after CORS so that preflight responses also get headers.
# Sets X-Content-Type-Options, X-Frame-Options, HSTS, CSP,
# Referrer-Policy, and Permissions-Policy on every response.
add_security_headers_middleware(app)

# ── Request timing / profiling middleware (outermost) ───────
# Logs execution time for every request. Warns on requests
# exceeding 5s (slow) or 30s (critical).
add_profiling_middleware(app)

# ── HTTPS redirect middleware ───────────────────────────────
# Only active when ENFORCE_HTTPS=True (local dev: False).
add_https_redirect_middleware(app)

# Register routers — all under settings.API_PREFIX for versioning.
_api = settings.API_PREFIX
app.include_router(documents.router, prefix=f"{_api}/documents", tags=["documents"])
app.include_router(agents.router, prefix=f"{_api}/agents", tags=["agents"])
app.include_router(system.router, prefix=f"{_api}/system", tags=["system"])
app.include_router(email.router, prefix=f"{_api}/email", tags=["email"])  # drafting
app.include_router(email_classifier.router, prefix=f"{_api}/email", tags=["email"])  # classification
app.include_router(email_action.router, prefix=f"{_api}/email", tags=["email"])  # actions
app.include_router(dynamic_templates.router, prefix=f"{_api}/templates", tags=["templates"])
app.include_router(timeline.router, prefix=f"{_api}/timeline", tags=["timeline"])
app.include_router(act_generation.router, prefix=f"{_api}/acts", tags=["acts"])
app.include_router(deeds.router, prefix=f"{_api}/deeds", tags=["deeds"])
app.include_router(clause_review.router, prefix=f"{_api}/clauses", tags=["clauses"])
app.include_router(pdf_extraction.router, prefix=f"{_api}/pdf", tags=["pdf"])
app.include_router(cases.router, prefix=f"{_api}/cases", tags=["cases"])
app.include_router(orchestrator.router, prefix=f"{_api}/orchestrator", tags=["orchestrator"])
app.include_router(conversations.router, prefix=f"{_api}/conversations", tags=["conversations"])
app.include_router(security.router, prefix=f"{_api}/security", tags=["security"])
app.include_router(routing_endpoint.router, prefix=f"{_api}/routing", tags=["routing"])
app.include_router(observability.router, prefix=f"{_api}/observability", tags=["observability"])
app.include_router(rbac.router, prefix=f"{_api}/rbac", tags=["rbac"])


@app.get("/health")
@limiter.exempt
async def health(request: Request):
    """Health check endpoint for the Tauri sidecar."""
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    # Check if port is already in use
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((settings.HOST, settings.PORT))
        sock.close()
    except OSError:
        logger.warning(
            "Port %d already in use. Is the backend already running?",
            settings.PORT,
        )
        logger.info("Attempting to start anyway (uvicorn may retry)...")

    ssl_kwargs = {}
    if settings.SSL_CERTFILE and settings.SSL_KEYFILE:
        ssl_kwargs["ssl_certfile"] = settings.SSL_CERTFILE
        ssl_kwargs["ssl_keyfile"] = settings.SSL_KEYFILE

    if ssl_kwargs:
        logger.info("🔒 TLS enabled with certfile=%s", settings.SSL_CERTFILE)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        **ssl_kwargs,
    )
