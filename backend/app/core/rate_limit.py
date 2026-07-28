"""
Rate limiting configuration for the Legis Agent API.

Uses slowapi with role-aware key function.
Admins get higher limits, stagiaires get lower limits.
"""

from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.auth import Role

# ── Role-based limits ─────────────────────────────────────────
# These are applied per-route via decorators.
# The default limits apply when no decorator overrides them.
DEFAULT_LIMITS = [
    "100/minute",
    "1000/hour",
]

# Per-role limits (used by SlowAPIMiddleware custom logic)
ROLE_LIMITS: dict[str, list[str]] = {
    Role.ADMIN.value:      ["200/minute", "2000/hour"],
    Role.NOTAIRE.value:    ["100/minute", "1000/hour"],
    Role.ASSISTANT.value:  ["60/minute",  "600/hour"],
    Role.STAGIAIRE.value:  ["20/minute",  "200/hour"],
}


def _role_key_func(request) -> str:
    """Return a rate-limit key that includes the user's role.

    If the request has an authenticated user context, the role is
    extracted from it. Otherwise, falls back to the IP address.
    """
    # Try to get auth context from request state (set by middleware)
    role = getattr(request.state, "auth_role", None)
    if role:
        return f"role:{role}:{get_remote_address(request)}"

    # Try X-User-Role header (dev mode)
    header_role = request.headers.get("X-User-Role", "")
    if header_role:
        return f"role:{header_role}:{get_remote_address(request)}"

    # Fallback to IP
    return get_remote_address(request)


limiter = Limiter(
    key_func=_role_key_func,
    default_limits=DEFAULT_LIMITS,
    enabled=True,
)
