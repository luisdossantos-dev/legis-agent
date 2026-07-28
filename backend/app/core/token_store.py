"""
Token store — file-based JSON persistence for API tokens.

Handles:
- Token creation (random "lgt_" prefixed tokens)
- Token revocation
- Token-to-user resolution
- File-based storage with atomic writes
"""

import json
import logging
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.models.auth import UserInDB
from app.core.user_store import get_user_by_id

logger = logging.getLogger(__name__)

# ── File paths ──────────────────────────────────────────────────

TOKENS_DIR = Path(__file__).resolve().parent.parent.parent / "config"
TOKENS_FILE = TOKENS_DIR / "tokens.json"


def _ensure_dir() -> None:
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)


def _load_tokens() -> Dict[str, Any]:
    """Load active tokens from JSON file."""
    _ensure_dir()
    if not TOKENS_FILE.exists():
        return {"tokens": {}}
    try:
        return json.loads(TOKENS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"tokens": {}}


def _save_tokens(data: Dict[str, Any]) -> None:
    """Save tokens to JSON file atomically."""
    _ensure_dir()
    tmp = TOKENS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(TOKENS_FILE)


# ── Public API ──────────────────────────────────────────────────


def create_token(user_id: str) -> str:
    """Create an API token for a user."""
    token = "lgt_" + secrets.token_hex(24)
    tokens = _load_tokens()
    tokens.setdefault("tokens", {})[token] = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_tokens(tokens)
    return token


def revoke_token(token: str) -> None:
    """Revoke an API token."""
    tokens = _load_tokens()
    tokens.setdefault("tokens", {}).pop(token, None)
    _save_tokens(tokens)


def get_user_from_token(token: str) -> Optional[UserInDB]:
    """Resolve a token to a user."""
    tokens = _load_tokens()
    entry = tokens.get("tokens", {}).get(token)
    if not entry:
        return None
    return get_user_by_id(entry["user_id"])
