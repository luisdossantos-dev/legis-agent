"""
Agent tools with Pydantic validation, cost guards, and retry logic.

Each tool has:
  - Pydantic schema for parameter validation
  - Cost threshold (estimated USD)
  - Retry decorator with exponential backoff
"""

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Tool schemas (Pydantic) ───────────────────────────────────


class AnalyzeDocumentParams(BaseModel):
    """Analyze a legal document."""
    document_text: str = Field(..., min_length=10, max_length=50000, description="Full document text")
    document_id: str = Field(default="", description="Document ID")
    query: str = Field(default="Analyze this legal document.", description="Analysis focus")


class DraftResponseParams(BaseModel):
    """Draft a legal response."""
    query: str = Field(..., min_length=1, max_length=2000, description="User query")
    context_chunks: List[str] = Field(default_factory=list, description="Relevant document fragments")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class ReviewClauseParams(BaseModel):
    """Review a notarial clause."""
    clause_text: str = Field(..., min_length=10, max_length=10000, description="Clause text")
    clause_type: str = Field(default="autre", description="prix, delai, condition_suspensive, etc.")
    context: str = Field(default="", description="Other clauses from same document")


class FormatDocumentParams(BaseModel):
    """Format a document for output."""
    content: str = Field(..., min_length=10, max_length=50000, description="Document content")
    format_type: str = Field(default="docx", description="docx | txt | html")
    title: str = Field(default="Document", description="Document title")


# ── Cost thresholds ────────────────────────────────────────────

COST_THRESHOLDS: Dict[str, float] = {
    "analyze_document": 0.10,   # $0.10 max for analysis (longer output)
    "draft_response": 0.05,     # $0.05 max for drafting
    "review_clause": 0.03,      # $0.03 max for clause review
    "format_document": 0.02,    # $0.02 max for formatting
}

# Estimated tokens per tool call (output only; input is calculated dynamically)
ESTIMATED_TOKENS: Dict[str, int] = {
    "analyze_document": 1000,
    "draft_response": 800,
    "review_clause": 500,
    "format_document": 200,
}


def estimate_cost(tool_name: str, params: Dict[str, Any]) -> float:
    """
    Estimate the cost of a tool call based on input size and model pricing.
    Uses gpt-4o pricing: $2.50/1M input, $10.00/1M output.

    Returns estimated USD cost.
    """
    base_tokens = ESTIMATED_TOKENS.get(tool_name, 1000)

    # Add extra tokens for text content
    extra_tokens = 0
    for key in ["document_text", "context_chunks", "clause_text", "content"]:
        if key in params and isinstance(params[key], str):
            extra_tokens += len(params[key]) / 4  # ~4 chars per token
        elif key in params and isinstance(params[key], list):
            for item in params[key]:
                if isinstance(item, str):
                    extra_tokens += len(item) / 4

    total_tokens = int(extra_tokens) + 500  # +500 for prompt overhead
    input_cost = (total_tokens / 1_000_000) * 2.50
    output_cost = (base_tokens / 1_000_000) * 10.00
    return round(input_cost + output_cost, 6)


def check_cost_guard(tool_name: str, params: Dict[str, Any]) -> Optional[str]:
    """
    Check if a tool call exceeds its cost threshold.

    Returns:
        Error message if blocked, None if allowed.
    """
    estimated = estimate_cost(tool_name, params)
    threshold = COST_THRESHOLDS.get(tool_name, 0.01)

    if estimated > threshold:
        msg = (
            f"⚠️ Cost guard blocked '{tool_name}': "
            f"estimated ${estimated:.6f} exceeds threshold ${threshold:.2f}"
        )
        logger.warning(msg)
        return msg

    return None


# ── Retry decorator ────────────────────────────────────────────


class MaxRetriesExceeded(Exception):
    """Raised when all retry attempts fail."""
    pass


async def retry_with_backoff(
    func: Callable,
    args: tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 3.0,
) -> Any:
    """
    Execute a function with exponential backoff retry.

    Delays: 1s → 3s → 9s (max 3 retries)

    Args:
        func: Async function to call
        args: Positional arguments
        kwargs: Keyword arguments
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        backoff_factor: Multiplier for each retry

    Returns:
        Function result

    Raises:
        MaxRetriesExceeded if all attempts fail
    """
    kwargs = kwargs or {}
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("Retry attempt %d/%d for %s", attempt, max_retries, func.__name__)
            return await func(*args, **kwargs)

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                base = base_delay * (backoff_factor ** (attempt - 1))
                # Add jitter: random between 50% and 100% of the base delay
                # Prevents thundering herd when multiple clients retry simultaneously
                jitter = base * (0.5 + random.random() * 0.5)
                delay = min(jitter, 30.0)  # cap at 30 seconds
                logger.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                    attempt, max_retries, func.__name__, str(e)[:100], delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All %d retries failed for %s: %s",
                    max_retries, func.__name__, str(e)[:200],
                )

    raise MaxRetriesExceeded(
        f"Function '{func.__name__}' failed after {max_retries} retries. "
        f"Last error: {last_error}"
    ) from last_error


# ── Tool registry ──────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "analyze_document": {
        "description": "Analyze a legal document and extract structured information",
        "params_schema": AnalyzeDocumentParams,
        "cost_threshold": COST_THRESHOLDS["analyze_document"],
        "estimated_tokens": ESTIMATED_TOKENS["analyze_document"],
    },
    "draft_response": {
        "description": "Draft a legal response or document based on context",
        "params_schema": DraftResponseParams,
        "cost_threshold": COST_THRESHOLDS["draft_response"],
        "estimated_tokens": ESTIMATED_TOKENS["draft_response"],
    },
    "review_clause": {
        "description": "Review a notarial clause for risks and missing elements",
        "params_schema": ReviewClauseParams,
        "cost_threshold": COST_THRESHOLDS["review_clause"],
        "estimated_tokens": ESTIMATED_TOKENS["review_clause"],
    },
    "format_document": {
        "description": "Format a document for output (DOCX, HTML, etc.)",
        "params_schema": FormatDocumentParams,
        "cost_threshold": COST_THRESHOLDS["format_document"],
        "estimated_tokens": ESTIMATED_TOKENS["format_document"],
    },
}


def get_tool_names() -> List[str]:
    """Get list of available tool names."""
    return list(TOOL_REGISTRY.keys())


def validate_tool_params(tool_name: str, params: Dict[str, Any]) -> Optional[str]:
    """
    Validate tool parameters against the Pydantic schema.

    Args:
        tool_name: Name of the tool
        params: Parameters to validate

    Returns:
        Error message if invalid, None if valid.
    """
    schema = TOOL_REGISTRY.get(tool_name, {}).get("params_schema")
    if not schema:
        return f"Unknown tool: '{tool_name}'"

    try:
        schema(**params)
        return None
    except (ImportError, TypeError, ValueError) as e:
        return f"Parameter validation error for '{tool_name}': {str(e)[:200]}"
