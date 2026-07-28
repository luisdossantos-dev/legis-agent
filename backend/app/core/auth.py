"""
RBAC (Role-Based Access Control) module — FastAPI integration.

Provides FastAPI dependencies for extracting the current user from requests
and checking permissions. The actual user and token storage lives in
user_store.py and token_store.py respectively.

Re-exports all public symbols from user_store and token_store for
backward compatibility with existing imports.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings as _settings
from app.core.user_store import (  # noqa: F401 — re-export for callers
    authenticate_user,
    create_user,
    delete_user,
    get_admin_password,
    get_user_by_id,
    get_user_by_username,
    has_users_configured,
    list_users,
    update_user,
)
from app.core.token_store import (  # noqa: F401 — re-export for callers
    create_token,
    get_user_from_token,
    revoke_token,
)
from app.models.auth import (
    ROLE_PERMISSIONS,
    AuthContext,
    Permission,
    Role,
    UserInDB,
)

logger = logging.getLogger(__name__)


# ── FastAPI auth scheme ────────────────────────────────────────

# Support both Bearer token and X- headers
security = HTTPBearer(auto_error=False)


def _auth_context_from_user(user: UserInDB) -> AuthContext:
    """Build an AuthContext from a UserInDB."""
    return AuthContext(
        user_id=user.id,
        username=user.username,
        role=user.role,
        office=user.office,
        display_name=user.display_name or user.username,
        email=user.email,
    )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthContext:
    """
    FastAPI dependency: extract the current authenticated user.

    Resolution order:
    1. Authorization: Bearer <token> header — validates against stored tokens
    2. X-User-Id + X-User-Role headers — ONLY if ENABLE_HEADER_AUTH=True (dev mode)
    3. Open mode — when no users exist yet (first-run setup)

    In production (ENABLE_HEADER_AUTH=False by default), only Bearer token
    authentication is accepted. The X-Header bypass is never available.
    """
    # Method 1: Bearer token (always available)
    if credentials:
        token = credentials.credentials
        user = get_user_from_token(token)
        if user:
            return _auth_context_from_user(user)

    # Method 2: X-Headers — ONLY when explicitly enabled for development
    if _settings.ENABLE_HEADER_AUTH:
        user_id = request.headers.get("X-User-Id")
        user_role = request.headers.get("X-User-Role")
        if user_id and user_role:
            user = get_user_by_id(user_id)
            if user:
                return _auth_context_from_user(user)
            # Virtual context for dev/testing
            try:
                role = Role(user_role)
            except ValueError:
                role = Role.STAGIAIRE
            logger.warning(
                "Header auth used (dev mode): user=%s role=%s",
                user_id, role.value,
            )
            return AuthContext(
                user_id=user_id,
                username=user_id,
                role=role,
                office=request.headers.get("X-User-Office", "main"),
                display_name=request.headers.get("X-User-Name", user_id),
            )

    # Method 3: Open mode (no users configured at all)
    users = list_users()
    if not users:
        return AuthContext(
            user_id="open",
            username="open",
            role=Role.ADMIN,
            office="main",
            display_name="Open Access",
        )

    # No valid auth provided and header auth is disabled
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a valid Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ── Permission check dependency ─────────────────────────────────


class PermissionDenied(Exception):
    """Raised when a user lacks the required permission."""
    pass


def require_permission(permission: Permission):
    """
    FastAPI dependency factory: require a specific permission.

    Usage:
        @router.get("/documents")
        async def list_docs(user: AuthContext = Depends(require_permission(Permission.READ))):
            ...
    """
    async def _check(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        allowed = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in allowed:
            logger.warning(
                "Permission denied: user=%s role=%s needed=%s",
                user.username, user.role.value, permission.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required. User role '{user.role.value}' lacks it.",
            )
        return user
    return _check


async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[AuthContext]:
    """
    FastAPI dependency: extract user if authenticated, return None otherwise.

    Unlike get_current_user(), this NEVER raises 401 — it returns None
    when no valid auth is provided. Useful for endpoints that work in
    both authenticated and anonymous modes.
    """
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


def get_auth_context(request: Request) -> Optional[AuthContext]:
    """Extract auth context from request state (set by middleware)."""
    if hasattr(request.state, "auth_context"):
        return request.state.auth_context
    return None
