"""
Query expansion for better retrieval coverage.

Generates alternative phrasings of the user query using a lightweight
LLM call (profile="fast"), then each variation is searched independently
and results are fused with RRF.

This improves recall when the user's wording doesn't match the document
terminology (e.g., "rupture" vs "résiliation", "achat" vs "acquisition").
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a legal search query expander.
Generate {num} alternative phrasings of the given query for a legal document search.

Rules:
- Keep the core legal meaning intact
- Use synonyms where appropriate (e.g., rupture→résiliation, vente→cession, contrat→convention)
- Vary the structure (question form, keyword form, phrase form)
- Never add information not present in the original query
- Output ONLY valid JSON array of strings: ["variant 1", "variant 2", ...]
- Each variant must be in the same language as the original query"""


async def expand_query(
    query: str,
    num_expansions: int = 2,
) -> List[str]:
    """Generate alternative phrasings of a query using a fast LLM call.

    Args:
        query: The original user query.
        num_expansions: Number of alternative phrasings to generate (1-4).

    Returns:
        List of query variations (excluding the original).
        Returns empty list on any error (graceful degradation).
    """
    if not query.strip():
        return []

    num_expansions = max(1, min(num_expansions, 4))

    try:
        from app.core.llm import llm_complete

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT.format(num=num_expansions)},
            {"role": "user", "content": query},
        ]

        response = await llm_complete(
            messages=messages,
            profile="fast",
            temperature=0.3,
        )

        # Parse JSON array from response
        variants = _parse_json_list(response)

        # Validate: must be strings, different from original, reasonable length
        valid = []
        for v in variants:
            v = v.strip()
            if (
                v
                and v.lower() != query.lower()
                and 5 < len(v) < 300
                and v not in valid
            ):
                valid.append(v)

        if valid:
            logger.debug(
                "Query expansion: '%s' → %s",
                query[:60],
                [f"'{v[:40]}...'" for v in valid],
            )
        else:
            logger.debug("Query expansion returned no valid variants for: %s", query[:60])

        return valid

    except Exception as e:
        logger.debug("Query expansion failed (non-critical): %s", e)
        return []


def _parse_json_list(text: str) -> List[str]:
    """Parse a JSON array of strings from LLM output."""
    # Try to find a JSON array in the response
    import re

    # First, try direct JSON parse
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        except json.JSONDecodeError:
            pass

    # Fallback: extract array with regex
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        except (json.JSONDecodeError, ValueError):
            pass

    # Last resort: split by newlines and look for list items
    lines = text.split("\n")
    # Only use fallback if there are multiple lines — single-line non-JSON is not a list
    if len(lines) <= 1:
        return []
    result = []
    for line in lines:
        line = line.strip().strip('"- ')
        if line and not line.startswith(("[", "]", "{", "}")):
            result.append(line)

    return result[:4]
