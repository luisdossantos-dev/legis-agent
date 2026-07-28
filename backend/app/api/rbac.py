"""
RBAC + GDPR API endpoints.

User management and audit trail for GDPR compliance.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import (
    AuthContext,
    Permission,
    authenticate_user,
    create_token,
    create_user,
    delete_user,
    get_current_user,
    get_user_by_id,
    get_user_by_username,
    get_user_from_token,
    list_users,
    require_permission,
    revoke_token,
    update_user,
)
from app.core.gdpr import (
    AuditAction,
    check_sensitive_routing,
    export_user_data,
    get_audit_trail,
    log_interaction,
)
from app.core.runtime_config import get_active_model, get_active_provider
from app.models.auth import (
    AuditLogEntry as AuditLogEntryModel,
    GDPRExport,
    UserCreate,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Authentication ──────────────────────────────────────────────

@router.post("/auth/login")
async def login(username: str, password: str, request: Request):
    """
    Authenticate a user and return an API token.

    The token must be sent as `Authorization: Bearer <token>` in subsequent requests.
    """
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token(user.id)

    log_interaction(
        auth=AuthContext(
            user_id=user.id,
            username=user.username,
            role=user.role,
            office=user.office,
            display_name=user.display_name or user.username,
            email=user.email,
        ),
        action=AuditAction.LOGIN,
        ip_address=request.client.host if request.client else "",
    )

    return {
        "token": token,
        "user": UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            office=user.office,
            display_name=user.display_name or user.username,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    }


@router.post("/auth/logout")
async def logout(
    request: Request,
    user: AuthContext = Depends(get_current_user),
    token: Optional[str] = None,
):
    """Revoke the current token."""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if token:
        revoke_token(token)

    log_interaction(user, AuditAction.LOGOUT, ip_address=request.client.host if request.client else "")
    return {"message": "Logged out successfully"}


@router.get("/auth/me")
async def get_me(user: AuthContext = Depends(get_current_user)):
    """Get the current authenticated user's info."""
    return user


# ── User management (admin only) ───────────────────────────────

@router.get("/users", response_model=List[UserResponse])
async def list_all_users(
    user: AuthContext = Depends(require_permission(Permission.ADMIN)),
):
    """List all users (admin only)."""
    return list_users()


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.ADMIN)),
):
    """Get a specific user (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        office=user.office,
        display_name=user.display_name or user.username,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_new_user(
    user_data: UserCreate,
    current_user: AuthContext = Depends(require_permission(Permission.ADMIN)),
    request: Request = None,
):
    """Create a new user (admin only)."""
    result = create_user(user_data)

    log_interaction(
        current_user,
        AuditAction.CREATE,
        resource_type="user",
        resource_id=result.id,
        details=f"Created user '{result.username}' with role '{result.role.value}'",
        ip_address=request.client.host if request and request.client else "",
    )

    return result


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_existing_user(
    user_id: str,
    updates: UserUpdate,
    current_user: AuthContext = Depends(require_permission(Permission.ADMIN)),
    request: Request = None,
):
    """Update a user (admin only)."""
    result = update_user(user_id, updates)

    log_interaction(
        current_user,
        AuditAction.UPDATE,
        resource_type="user",
        resource_id=user_id,
        details=f"Updated user '{result.username}'",
        ip_address=request.client.host if request and request.client else "",
    )

    return result


@router.delete("/users/{user_id}")
async def delete_existing_user(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.ADMIN)),
    request: Request = None,
):
    """Delete/anonymize a user (admin only). GDPR right to erasure."""
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    # Get user info before deletion for audit
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    delete_user(user_id)

    log_interaction(
        current_user,
        AuditAction.FORGET,
        resource_type="user",
        resource_id=user_id,
        details=f"Anonymized user '{user.username}' (right to erasure)",
        ip_address=request.client.host if request and request.client else "",
    )

    return {"message": "User anonymized (right to erasure)"}


# ── GDPR endpoints ──────────────────────────────────────────────

@router.post("/export/{user_id}")
async def export_user_gdpr(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.ADMIN)),
    request: Request = None,
):
    """
    Export all data for a user (GDPR right to portability).

    Admin can export any user. Users can export their own data.
    """
    # Self-service: users can export their own data
    if user_id != current_user.user_id:
        from app.models.auth import ROLE_PERMISSIONS as _role_perms
        if Permission.ADMIN not in _role_perms.get(current_user.role, set()):
            raise HTTPException(status_code=403, detail="Admin permission required to export other users' data")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    export_data = export_user_data(user)

    log_interaction(
        current_user,
        AuditAction.EXPORT,
        resource_type="user",
        resource_id=user_id,
        details=f"GDPR data export for user '{user.username}'",
        ip_address=request.client.host if request and request.client else "",
    )

    return export_data


@router.post("/forget/{user_id}")
async def forget_user_gdpr(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.ADMIN)),
    request: Request = None,
):
    """
    Right to erasure (GDPR Article 17).

    Anonymizes all user data. Admin only.
    """
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot forget yourself")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    delete_user(user_id)

    log_interaction(
        current_user,
        AuditAction.FORGET,
        resource_type="user",
        resource_id=user_id,
        details=f"Right to erasure executed for '{user.username}'",
        ip_address=request.client.host if request and request.client else "",
    )

    return {"message": f"User '{user.username}' has been anonymized (GDPR Article 17)"}


# ── Audit trail ─────────────────────────────────────────────────

@router.get("/audit")
async def get_audit(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    current_user: AuthContext = Depends(require_permission(Permission.ADMIN)),
):
    """Get the full audit trail (admin only)."""
    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    entries = get_audit_trail(
        user_id=user_id,
        action=action_enum,
        limit=limit,
    )

    return {
        "total": len(entries),
        "entries": entries,
    }


@router.get("/audit/case/{case_id}")
async def get_case_audit(
    case_id: str,
    limit: int = 100,
    current_user: AuthContext = Depends(require_permission(Permission.READ)),
):
    """Get audit trail for a specific case/document."""
    entries = get_audit_trail(
        case_id=case_id,
        limit=limit,
    )

    return {
        "case_id": case_id,
        "total": len(entries),
        "entries": entries,
    }


# ── GDPR status ─────────────────────────────────────────────────

@router.get("/gdpr/status")
async def get_gdpr_status(
    document_text: Optional[str] = None,
    current_user: AuthContext = Depends(require_permission(Permission.READ)),
):
    """
    Get GDPR compliance status.

    If document_text is provided, checks if sensitive data in the
    document is being routed to an external API.
    """
    provider = get_active_provider()
    model = get_active_model()

    if document_text:
        routing_check = check_sensitive_routing(
            auth=current_user,
            document_text=document_text,
            current_provider=provider,
            current_model=model,
        )
    else:
        routing_check = {
            "has_sensitive_data": None,
            "current_provider": provider,
            "current_model": model,
            "routed_externally": provider not in ("ollama", "vllm", "local"),
            "gdpr_compliant": True,
        }

    return {
        "status": "compliant" if routing_check.get("gdpr_compliant", True) else "warning",
        "user": {
            "id": current_user.user_id,
            "username": current_user.username,
            "role": current_user.role.value,
            "office": current_user.office,
        },
        "routing": routing_check,
        "audit_enabled": True,
        "audit_file": "logs/audit/audit_trail.jsonl",
    }
