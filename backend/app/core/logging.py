"""
Centralized error logging and diagnostics for Legis Agent.

Stores structured error records in a local file and provides
an API endpoint to retrieve them for debugging.
"""

import json
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Log storage ──────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "agent_errors.jsonl"
MAX_LOG_ENTRIES = 500


def ensure_log_dir() -> None:
    """Ensure the log directory exists."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def record_error(
    source: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    exc_info: bool = False,
) -> Dict[str, Any]:
    """
    Record a structured error entry.

    Args:
        source: Component name (e.g., "embeddings", "llm", "rag")
        message: Human-readable error message
        details: Optional structured context (status codes, model names, etc.)
        exc_info: If True, captures the current exception traceback

    Returns:
        The error record dict
    """
    ensure_log_dir()

    record: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "message": message,
    }

    if details:
        record["details"] = details

    if exc_info:
        record["traceback"] = traceback.format_exc()

    # Write to JSONL file
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

        # Trim if too many entries
        _trim_log_file()
    except (OSError, UnicodeError) as e:
        logger.warning("Failed to write error log: %s", e)

    return record


def _trim_log_file() -> None:
    """Keep only the last MAX_LOG_ENTRIES entries."""
    try:
        if LOG_FILE.stat().st_size > 1024 * 1024:  # 1MB
            lines = LOG_FILE.read_text().strip().split("\n")
            if len(lines) > MAX_LOG_ENTRIES:
                LOG_FILE.write_text("\n".join(lines[-MAX_LOG_ENTRIES:]) + "\n")
    except (OSError, UnicodeError, ValueError):
        pass


def get_recent_errors(limit: int = 50) -> list[Dict[str, Any]]:
    """Return the most recent error records."""
    ensure_log_dir()

    if not LOG_FILE.exists():
        return []

    try:
        lines = LOG_FILE.read_text().strip().split("\n")
        records = []
        for line in lines[-limit:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records
    except (OSError, UnicodeError) as e:
        logger.warning("Failed to read error log: %s", e)
        return []


def get_error_summary() -> Dict[str, Any]:
    """Return a summary of errors grouped by source."""
    records = get_recent_errors(500)
    summary: Dict[str, Any] = {
        "total": len(records),
        "by_source": {},
        "latest": records[:10] if records else [],
    }

    for r in records:
        source = r.get("source", "unknown")
        if source not in summary["by_source"]:
            summary["by_source"][source] = {"count": 0, "latest": r.get("timestamp", "")}
        summary["by_source"][source]["count"] += 1
        ts = r.get("timestamp", "")
        if ts > summary["by_source"][source]["latest"]:
            summary["by_source"][source]["latest"] = ts

    return summary
