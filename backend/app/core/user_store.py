"""
User store — file-based JSON persistence for user accounts.

Handles:
- Password hashing and verification (SHA-256 + salt)
- User CRUD (create, read, update, delete/anonymize)
- File-based storage with atomic writes
- Default admin account creation on first run
"""

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import settings as _settings
from app.models.auth import (
    Role,
    UserCreate,
    UserInDB,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)

# ── File paths ──────────────────────────────────────────────────

USERS_DIR = Path(__file__).resolve().parent.parent.parent / "config"
USERS_FILE = USERS_DIR / "users.json"

# Default admin credentials (created on first run if no users exist)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@legisagent.local"

# The initial admin password is derived from:
#   1. settings.ADMIN_PASSWORD (env ADMIN_PASSWORD) if set
#   2. A random 24-character token generated at first run
# It is NEVER hardcoded in source code.
_ADMIN_PASSWORD: str | None = None  # populated once at first _ensure_default_admin()


# ── Filesystem helpers ─────────────────────────────────────────


def _ensure_dir() -> None:
    USERS_DIR.mkdir(parents=True, exist_ok=True)


def _load_raw() -> Dict[str, Any]:
    """Load users from JSON file."""
    _ensure_dir()
    if not USERS_FILE.exists():
        return {"users": []}
    try:
        return json.loads(USERS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load users file: %s", e)
        return {"users": []}


def _save_raw(data: Dict[str, Any]) -> None:
    """Save users to JSON file atomically."""
    _ensure_dir()
    tmp = USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.rename(USERS_FILE)


# ── Password helpers ───────────────────────────────────────────


def _hash_password(password: str) -> str:
    """Hash a password with SHA-256 + salt."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    if ":" not in hashed:
        return False
    salt, h = hashed.split(":", 1)
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == h


# ── Conversion helpers ─────────────────────────────────────────


def _row_to_user_in_db(u: dict) -> UserInDB:
    """Convert a raw user dict to a UserInDB model."""
    return UserInDB(
        id=u["id"],
        username=u["username"],
        email=u.get("email", ""),
        role=Role(u["role"]),
        office=u.get("office", "main"),
        display_name=u.get("display_name", ""),
        is_active=u.get("is_active", True),
        hashed_password=u["hashed_password"],
        created_at=(
            datetime.fromisoformat(u["created_at"]) if "created_at" in u else datetime.utcnow()
        ),
        updated_at=(
            datetime.fromisoformat(u["updated_at"]) if "updated_at" in u else datetime.utcnow()
        ),
    )


def _row_to_user_response(u: dict) -> UserResponse:
    """Convert a raw user dict to a UserResponse model."""
    return UserResponse(
        id=u["id"],
        username=u["username"],
        email=u.get("email", ""),
        role=Role(u["role"]),
        office=u.get("office", "main"),
        display_name=u.get("display_name", ""),
        is_active=u.get("is_active", True),
        created_at=(
            datetime.fromisoformat(u["created_at"]) if "created_at" in u else datetime.utcnow()
        ),
    )


# ── Default admin bootstrap ────────────────────────────────────


def _ensure_default_admin() -> None:
    """
    Create default admin user if no users exist.

    The password is:
      1. From env ADMIN_PASSWORD if set and non-empty
      2. A cryptographically random 24-char token generated on first run

    The password is logged ONCE at startup. No password is ever hardcoded.
    """
    global _ADMIN_PASSWORD

    data = _load_raw()
    if not data.get("users"):
        env_password = _settings.ADMIN_PASSWORD.strip() if _settings.ADMIN_PASSWORD else ""
        if env_password:
            password = env_password
            source = "ADMIN_PASSWORD env var"
        else:
            password = secrets.token_urlsafe(24)
            source = "randomly generated"

        _ADMIN_PASSWORD = password

        admin_user = {
            "id": str(uuid.uuid4()),
            "username": DEFAULT_ADMIN_USERNAME,
            "email": DEFAULT_ADMIN_EMAIL,
            "role": Role.ADMIN.value,
            "office": "main",
            "display_name": "Administrator",
            "is_active": True,
            "hashed_password": _hash_password(password),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        data["users"] = [admin_user]
        _save_raw(data)

        border = "═" * 60
        logger.info(
            "\n%s\n"
            "  👤 Default admin user created\n"
            "  Username: %s\n"
            "  Password: %s  (%s)\n"
            "  Email:    %s\n"
            "  IMPORTANT: Change this password after first login\n"
            "%s",
            border,
            DEFAULT_ADMIN_USERNAME,
            password,
            source,
            DEFAULT_ADMIN_EMAIL,
            border,
        )


# Initialize default admin on import
_ensure_default_admin()


# ── Public API ──────────────────────────────────────────────────


def list_users() -> List[UserResponse]:
    """List all users."""
    data = _load_raw()
    return [_row_to_user_response(u) for u in data.get("users", [])]


def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    """Get a user by ID."""
    data = _load_raw()
    for u in data.get("users", []):
        if u["id"] == user_id:
            return _row_to_user_in_db(u)
    return None


def get_user_by_username(username: str) -> Optional[UserInDB]:
    """Get a user by username."""
    data = _load_raw()
    for u in data.get("users", []):
        if u["username"] == username:
            return _row_to_user_in_db(u)
    return None


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate a user by username and password."""
    user = get_user_by_username(username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not _verify_password(password, user.hashed_password):
        return None
    return user


def create_user(user_data: UserCreate) -> UserResponse:
    """Create a new user."""
    data = _load_raw()

    for u in data.get("users", []):
        if u["username"] == user_data.username:
            raise HTTPException(status_code=409, detail="Username already exists")

    new_user = {
        "id": str(uuid.uuid4()),
        "username": user_data.username,
        "email": user_data.email,
        "role": user_data.role.value,
        "office": user_data.office,
        "display_name": user_data.display_name or user_data.username,
        "is_active": user_data.is_active,
        "hashed_password": _hash_password(user_data.password),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    data.setdefault("users", []).append(new_user)
    _save_raw(data)
    logger.info("User created: %s (role=%s)", user_data.username, user_data.role.value)
    return _row_to_user_response(new_user)


def update_user(user_id: str, updates: UserUpdate) -> UserResponse:
    """Update an existing user."""
    data = _load_raw()
    for i, u in enumerate(data.get("users", [])):
        if u["id"] == user_id:
            if updates.email is not None:
                u["email"] = updates.email
            if updates.role is not None:
                u["role"] = updates.role.value
            if updates.office is not None:
                u["office"] = updates.office
            if updates.display_name is not None:
                u["display_name"] = updates.display_name
            if updates.is_active is not None:
                u["is_active"] = updates.is_active
            if updates.password is not None:
                u["hashed_password"] = _hash_password(updates.password)
            u["updated_at"] = datetime.utcnow().isoformat()
            data["users"][i] = u
            _save_raw(data)
            logger.info("User updated: %s", u["username"])
            return _row_to_user_response(u)

    raise HTTPException(status_code=404, detail="User not found")


def delete_user(user_id: str) -> None:
    """Delete a user (right to erasure — anonymize instead of delete)."""
    data = _load_raw()
    for i, u in enumerate(data.get("users", [])):
        if u["id"] == user_id:
            anonymized = {
                "id": u["id"],
                "username": f"deleted-{u['id'][:8]}",
                "email": f"deleted-{u['id'][:8]}@anon.local",
                "role": "stagiaire",
                "office": "deleted",
                "display_name": "Deleted User",
                "is_active": False,
                "hashed_password": _hash_password(secrets.token_hex(16)),
                "created_at": u.get("created_at", datetime.utcnow().isoformat()),
                "updated_at": datetime.utcnow().isoformat(),
            }
            data["users"][i] = anonymized
            _save_raw(data)
            logger.info("User anonymized (right to erasure): %s", u["id"])
            return
    raise HTTPException(status_code=404, detail="User not found")


def get_admin_password() -> str | None:
    """
    Return the generated admin password, or None if it has not been initialised.

    Only intended for testing and first-run setup. In production the password
    is only visible in the startup log and should be changed immediately.
    """
    return _ADMIN_PASSWORD


def has_users_configured() -> bool:
    """Check if any users exist in the system."""
    return len(list_users()) > 0
