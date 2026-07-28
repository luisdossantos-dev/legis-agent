"""
Security API endpoints.
GET /api/security/status — Show security layer status.
POST /api/security/scan — Scan text for injection patterns.
GET /api/security/csrf-token — Get a CSRF token.
GET /api/security/audit-log — Get recent audit log entries.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from pydantic import BaseModel

from app.core.security import (
    GUARD_SYSTEM_PROMPT,
    MAX_CHARS,
    audit_log,
    detect_injection_attempt,
    sanitize_text,
)
from app.core.gdpr import _load_audit_entries

logger = logging.getLogger(__name__)

router = APIRouter()


class ScanRequest(BaseModel):
    text: str


# ── In-memory CSRF token store ──────────────────────────────────

_csrf_tokens: dict = {}


@router.get("/status")
async def security_status():
    """Show the status of the security layer."""
    guard_len = len(GUARD_SYSTEM_PROMPT)

    return {
        "guard_prompt_active": True,
        "guard_prompt_length": guard_len,
        "max_input_chars": MAX_CHARS,
        "sanitization_active": True,
        "audit_logging_active": True,
        "injection_patterns_monitored": 6,
        "description": {
            "layer_1": "Guard prompt injected into every system message",
            "layer_2": "Null bytes, control chars stripped; truncated to 128K chars",
            "layer_3": "Full interaction audit logging to Langfuse (if configured)",
        },
    }


@router.post("/scan")
async def scan_for_injection(req: ScanRequest):
    """
    Scan text for potential prompt injection patterns.

    Returns which patterns were detected (if any) and the sanitized text.
    This is a diagnostic endpoint — does not modify or block anything.
    """
    result = detect_injection_attempt(req.text)
    sanitized = sanitize_text(req.text)

    return {
        "original_length": len(req.text),
        "sanitized_length": len(sanitized),
        "injection_detected": result is not None,
        "matched_pattern": result,
        "snippet": sanitized[:200] if len(sanitized) > 200 else sanitized,
    }


@router.get("/csrf-token")
async def get_csrf_token():
    """
    Generate and return a CSRF token.

    The token is stored in memory and can be validated
    for subsequent state-changing requests.
    """
    token = str(uuid.uuid4())
    _csrf_tokens[token] = datetime.now(timezone.utc).isoformat()

    # Prune old tokens (keep at most 1000)
    if len(_csrf_tokens) > 1000:
        keys = sorted(_csrf_tokens.keys(), key=lambda k: _csrf_tokens[k])
        for k in keys[:-500]:
            del _csrf_tokens[k]

    return {
        "csrf_token": token,
        "expires_in": "session",
        "usage": "Include as X-CSRF-Token header in state-changing requests",
    }


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(default=50, ge=1, le=500, description="Number of entries to return"),
):
    """
    Get recent audit log entries.

    Returns the most recent audit log entries from the GDPR audit trail.
    """
    entries = _load_audit_entries(limit=limit)
    return {
        "total_returned": len(entries),
        "entries": entries,
    }
