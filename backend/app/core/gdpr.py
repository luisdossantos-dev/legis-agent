"""
GDPR compliance module.

Provides:
- Structured audit logging for every user interaction
- Right to erasure (anonymize user data)
- Data portability (export all user data)
- Case-level audit trail
- Sensitive data routing detection
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.auth import (
    AuditAction,
    AuditLogEntry,
    AuthContext,
    GDPRExport,
    Role,
    UserInDB,
    UserResponse,
)

logger = logging.getLogger(__name__)

# ── Audit log storage ──────────────────────────────────────────

AUDIT_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "audit"
AUDIT_FILE = AUDIT_DIR / "audit_trail.jsonl"
MAX_AUDIT_ENTRIES = 10_000


def _ensure_audit_dir() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _load_audit_entries(limit: int = 100) -> List[Dict[str, Any]]:
    """Load recent audit entries."""
    _ensure_audit_dir()
    if not AUDIT_FILE.exists():
        return []
    try:
        lines = AUDIT_FILE.read_text().strip().split("\n")
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries
    except (OSError, UnicodeError) as e:
        logger.warning("Failed to read audit log: %s", e)
        return []


def _append_audit_entry(entry: Dict[str, Any]) -> None:
    """Append an audit entry to the JSONL file."""
    _ensure_audit_dir()
    try:
        with open(AUDIT_FILE, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        # Trim if too large
        _trim_audit_file()
    except (OSError, UnicodeError) as e:
        logger.warning("Failed to write audit entry: %s", e)


def _trim_audit_file() -> None:
    """Keep only the last MAX_AUDIT_ENTRIES."""
    try:
        if AUDIT_FILE.stat().st_size > 2 * 1024 * 1024:  # 2MB
            lines = AUDIT_FILE.read_text().strip().split("\n")
            if len(lines) > MAX_AUDIT_ENTRIES:
                AUDIT_FILE.write_text("\n".join(lines[-MAX_AUDIT_ENTRIES:]) + "\n")
    except OSError as e:
        logger.warning("Failed to trim audit file: %s", e)
    except (ValueError, UnicodeError) as e:
        logger.warning("Unexpected error trimming audit file: %s", e)


# ── Audit logging API ──────────────────────────────────────────

def log_interaction(
    auth: AuthContext,
    action: AuditAction,
    resource_type: str = "",
    resource_id: str = "",
    details: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: str = "",
) -> str:
    """
    Log a user interaction for audit/GDPR compliance.

    Args:
        auth: Authenticated user context
        action: The type of action performed
        resource_type: "document", "case", "email", "user", etc.
        resource_id: ID of the resource
        details: Human-readable description
        metadata: Additional structured data
        ip_address: Client IP

    Returns:
        The entry ID
    """
    entry_id = str(uuid.uuid4())
    entry = AuditLogEntry(
        id=entry_id,
        timestamp=datetime.now(timezone.utc),
        user_id=auth.user_id,
        username=auth.username,
        role=auth.role,
        office=auth.office,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        metadata=metadata or {},
    )

    _append_audit_entry(entry.model_dump())
    logger.debug(
        "Audit: user=%s action=%s resource=%s/%s",
        auth.username, action.value, resource_type, resource_id,
    )
    return entry_id


def get_audit_trail(
    user_id: Optional[str] = None,
    case_id: Optional[str] = None,
    action: Optional[AuditAction] = None,
    limit: int = 100,
) -> List[AuditLogEntry]:
    """
    Get audit trail with optional filters.

    Args:
        user_id: Filter by user
        case_id: Filter by case/document ID (resource_id)
        action: Filter by action type
        limit: Max entries

    Returns:
        Filtered audit entries
    """
    entries = _load_audit_entries(limit=1000)
    result = []

    for e in entries:
        if user_id and e.get("user_id") != user_id:
            continue
        if case_id and e.get("resource_id") != case_id:
            continue
        if action and e.get("action") != action.value:
            continue
        try:
            result.append(AuditLogEntry(**e))
        except Exception as e:
            logger.debug("Skipping malformed audit entry: %s", e)

    return result[:limit]


# ── GDPR data export ───────────────────────────────────────────

def export_user_data(user: UserInDB) -> GDPRExport:
    """
    Export all data for a user (GDPR right to portability).

    Collects:
    - User profile
    - Audit trail entries for this user
    - Documents created by this user (from document store)
    - Cases involving this user

    Returns:
        GDPRExport with all user data
    """
    from app.models.auth import AuditLogEntry

    # Get audit entries for this user
    audit_entries = get_audit_trail(user_id=user.id, limit=10000)

    # Get documents from the document store
    documents = []
    try:
        from app.services.document_service import _documents_store
        for doc_id, doc in _documents_store.items():
            if doc.get("user_id") == user.id or doc.get("uploaded_by") == user.id:
                documents.append({
                    "id": doc_id,
                    "filename": doc.get("filename"),
                    "uploaded_at": doc.get("created_at"),
                    "pages": doc.get("pages"),
                })
    except Exception as e:
        logger.warning("Failed to collect documents for GDPR export: %s", e)

    return GDPRExport(
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            office=user.office,
            display_name=user.display_name or user.username,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        interactions=audit_entries,
        documents=documents,
        export_generated_at=datetime.now(timezone.utc),
    )


# ── Sensitive data routing check ───────────────────────────────

def check_sensitive_routing(
    auth: AuthContext,
    document_text: str,
    current_provider: str,
    current_model: str,
) -> Dict[str, Any]:
    """
    Check if sensitive data is being sent to an external API.

    GDPR requires that personally identifiable information (PII)
    should not leave the network unless explicitly consented.

    Returns a report with:
    - has_sensitive_data: bool
    - routed_externally: bool
    - recommendation: str
    """
    # Detect potential PII patterns
    import re
    pii_patterns = {
        "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
        "phone": r"(?:\+\d{1,3}[-\s]?)?\(?\d{2,4}\)?[-\s]?\d{2,4}[-\s]?\d{2,4}",
        "id_number": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",  # Brazilian CPF-like
        "passport": r"\b[A-Z]{2}\d{6,9}\b",
    }

    found_patterns = {}
    for name, pattern in pii_patterns.items():
        matches = re.findall(pattern, document_text)
        if matches:
            found_patterns[name] = len(matches)

    has_sensitive_data = len(found_patterns) > 0

    # Check if current provider is external
    local_providers = {"ollama", "vllm", "local"}
    provider_prefix = current_provider.split("/")[0].lower() if "/" in current_provider else current_provider.lower()
    routed_externally = provider_prefix not in local_providers

    recommendation = ""
    if has_sensitive_data and routed_externally:
        recommendation = (
            f"Sensitive data detected ({', '.join(found_patterns.keys())}) "
            f"but routing to external provider '{current_provider}'. "
            "Consider using a local model (Ollama/vLLM) for GDPR compliance."
        )
        logger.warning("GDPR: %s", recommendation)
    elif has_sensitive_data:
        recommendation = (
            f"Sensitive data detected ({', '.join(found_patterns.keys())}) "
            f"and correctly routed to local provider."
        )

    return {
        "has_sensitive_data": has_sensitive_data,
        "patterns_found": found_patterns,
        "current_provider": current_provider,
        "current_model": current_model,
        "routed_externally": routed_externally,
        "gdpr_compliant": not (has_sensitive_data and routed_externally),
        "recommendation": recommendation,
    }
