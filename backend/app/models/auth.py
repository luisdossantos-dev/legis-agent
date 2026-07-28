"""
RBAC + GDPR Pydantic models.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


# ── Roles & Permissions ────────────────────────────────────────

class Role(str, Enum):
    """User roles in the system."""
    NOTAIRE = "notaire"
    ASSISTANT = "assistant"
    STAGIAIRE = "stagiaire"
    ADMIN = "admin"


class Permission(str, Enum):
    """Granular permissions."""
    READ = "read"          # View documents, analyses, cases
    WRITE = "write"        # Create/update documents, cases
    DRAFT = "draft"        # Draft emails, acts (but cannot finalize)
    FINALIZE = "finalize"  # Approve/finalize documents
    DELETE = "delete"      # Delete documents, cases
    ADMIN = "admin"        # Manage users, system config


# ── Role → Permissions matrix ──────────────────────────────────

ROLE_PERMISSIONS: Dict[Role, set[Permission]] = {
    Role.NOTAIRE: {
        Permission.READ,
        Permission.WRITE,
        Permission.DRAFT,
        Permission.FINALIZE,
        Permission.DELETE,
    },
    Role.ASSISTANT: {
        Permission.READ,
        Permission.WRITE,
        Permission.DRAFT,
    },
    Role.STAGIAIRE: {
        Permission.READ,
    },
    Role.ADMIN: {
        Permission.READ,
        Permission.WRITE,
        Permission.DRAFT,
        Permission.FINALIZE,
        Permission.DELETE,
        Permission.ADMIN,
    },
}


# ── User models ────────────────────────────────────────────────

class UserBase(BaseModel):
    """Base user fields."""
    username: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    email: str = Field(..., max_length=128)
    role: Role = Role.STAGIAIRE
    office: str = Field(default="main", max_length=64)
    display_name: str = Field(default="", max_length=128)
    is_active: bool = True


class UserCreate(UserBase):
    """Create user request."""
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Update user request."""
    email: Optional[str] = None
    role: Optional[Role] = None
    office: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserInDB(UserBase):
    """User as stored in DB (includes hashed password)."""
    id: str
    hashed_password: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class UserResponse(BaseModel):
    """User as returned by API (no password)."""
    id: str
    username: str
    email: str
    role: Role
    office: str
    display_name: str
    is_active: bool
    created_at: datetime


# ── Auth context (attached to request state) ───────────────────

class AuthContext(BaseModel):
    """Authenticated user context attached to every request."""
    user_id: str
    username: str
    role: Role
    office: str
    display_name: str = ""
    email: str = ""


# ── Audit / GDPR models ───────────────────────────────────────

class AuditAction(str, Enum):
    """Types of auditable actions."""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    LOGIN = "login"
    LOGOUT = "logout"
    ANALYSIS = "analysis"
    DRAFT = "draft"
    FINALIZE = "finalize"
    CHAT = "chat"
    FORGET = "forget"


class AuditLogEntry(BaseModel):
    """A single audit log entry."""
    id: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)
    user_id: str
    username: str
    role: Role
    office: str
    action: AuditAction
    resource_type: str = ""  # "document", "case", "email", "user", etc.
    resource_id: str = ""
    details: str = ""
    ip_address: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GDPRExport(BaseModel):
    """Full GDPR data export for a user."""
    user: UserResponse
    interactions: List[AuditLogEntry] = []
    documents: List[Dict[str, Any]] = []
    cases: List[Dict[str, Any]] = []
    emails: List[Dict[str, Any]] = []
    export_generated_at: datetime = Field(default_factory=_utcnow)
