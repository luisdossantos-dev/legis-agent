"""
Security API endpoints.
GET /api/security/status — Show security layer status.
POST /api/security/scan — Scan text for injection patterns.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import (
    GUARD_SYSTEM_PROMPT,
    MAX_CHARS,
    audit_log,
    detect_injection_attempt,
    sanitize_text,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ScanRequest(BaseModel):
    text: str


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
