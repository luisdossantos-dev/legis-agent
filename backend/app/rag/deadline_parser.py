"""
Deadline extraction and normalization engine.

Pipeline:
  1. Regex patterns extract explicit dates from text
  2. Relative date patterns ("sous 30 jours") → calculate absolute date
  3. LLM fallback for complex/unclear deadlines
  4. Normalize all dates to ISO format YYYY-MM-DD

Supports French formats:
  - "au 31 décembre 2025"
  - "sous 30 jours" → today + 30 days
  - "dans un délai de 15 jours ouvrés" → business days
  - "le 15/01/2026"
  - "avant le 1er mars"
  - "le 31 janvier 2025"
  - "pour le 15 du mois prochain"
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── French month names ────────────────────────────────────────

_FRENCH_MONTHS: Dict[str, int] = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}

# ── Date format patterns (ordered by priority) ───────────────

_DATE_PATTERNS: List[Tuple[str, str, str]] = [
    # "le 15/01/2026"
    (r"(?:le\s+|au\s+|avant\s+le\s+)?(\d{2})/(\d{2})/(\d{4})", "numeric_dmy", "explicit"),
    # "le 2026-01-15"
    (r"(?:le\s+|au\s+|avant\s+le\s+)?(\d{4})-(\d{2})-(\d{2})", "numeric_ymd", "explicit"),
    # "le 31 janvier 2025" / "au 31 décembre 2025"
    (r"(?:le\s+|au\s+|avant\s+le\s+)?(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|novembre|décembre|decembre)\s*(\d{4})?", "french_text", "explicit"),
    # "1er mars 2025" / "1er janvier"
    (r"(?:le\s+|au\s+|avant\s+le\s+)?1er\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|novembre|décembre|decembre)\s*(\d{4})?", "french_first", "explicit"),
    # "avant le 15 mars"
    (r"avant\s+le\s+(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|novembre|décembre|decembre)", "french_before", "explicit"),
]


# ── Relative date patterns ────────────────────────────────────

_RELATIVE_PATTERNS: List[Tuple[str, str]] = [
    # "sous 30 jours" / "sous 15 jours"
    (r"sous\s+(\d+)\s+jours?", "calendar"),
    # "dans un délai de 15 jours" / "dans un délai de 30 jours"
    (r"dans\s+un\s+d[ée]lai\s+de\s+(\d+)\s+jours?", "calendar"),
    # "dans 30 jours" / "dans 15 jours"
    (r"dans\s+(\d+)\s+jours?", "calendar"),
    # "sous 15 jours ouvrés" / "dans 15 jours ouvrés"
    (r"(?:sous|dans)\s+(\d+)\s+jours\s+ouvr[ée]s?", "business"),
    # "dans un délai de 15 jours ouvrés" 
    (r"dans\s+un\s+d[ée]lai\s+de\s+(\d+)\s+jours\s+ouvr[ée]s?", "business"),
    # "pour le 15 du mois prochain" / "pour le 15 du mois suivant"
    (r"pour\s+le\s+(\d{1,2})\s+du\s+mois\s+(prochain|suivant|courant)", "next_month"),
    # "d'ici 15 jours" / "d'ici 30 jours"
    (r"d'ici\s+(\d+)\s+jours?", "calendar"),
    # "sous quinzaine" (15 days)
    (r"sous\s+quinzaine", "fortnight"),
    # "dans la semaine" / "sous huitaine" (7 days)
    (r"(?:dans\s+la\s+semaine|sous\s+huitaine)", "week"),
]


# ── Helper functions ──────────────────────────────────────────


def _next_weekday(d: date, weekday: int = 0) -> date:
    """Get the next occurrence of a weekday (0=Monday)."""
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days_ahead)


def _add_business_days(start: date, days: int) -> date:
    """Add N business days (excluding weekends)."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday-Friday
            added += 1
    return current


def _parse_french_month(month_str: str) -> Optional[int]:
    """Parse a French month name to an integer (1-12)."""
    return _FRENCH_MONTHS.get(month_str.lower())


def _match_explicit_patterns(text: str) -> List[Dict[str, Any]]:
    """Extract explicit date mentions using regex patterns."""
    results = []

    for pattern, pattern_type, source in _DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE):
            groups = match.groups()

            try:
                if pattern_type == "numeric_dmy":
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    if year < 100:
                        year += 2000
                    parsed = date(year, month, day)
                elif pattern_type == "numeric_ymd":
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    parsed = date(year, month, day)
                elif pattern_type == "french_text":
                    day = int(groups[0])
                    month = _parse_french_month(groups[1])
                    year = int(groups[2]) if groups[2] else date.today().year
                    if month is None:
                        continue
                    parsed = date(year, month, day)
                elif pattern_type == "french_first":
                    month = _parse_french_month(groups[0])
                    year = int(groups[1]) if groups[1] else date.today().year
                    if month is None:
                        continue
                    parsed = date(year, month, 1)
                elif pattern_type == "french_before":
                    day = int(groups[0])
                    month = _parse_french_month(groups[1])
                    if month is None:
                        continue
                    year = date.today().year
                    parsed = date(year, month, day)
                    if parsed < date.today():
                        parsed = date(year + 1, month, day)
                else:
                    continue

                # Avoid duplicates
                if any(r["date"] == parsed.isoformat() for r in results):
                    continue

                context_start = max(0, match.start() - 30)
                context_end = min(len(text), match.end() + 30)

                results.append({
                    "date": parsed.isoformat(),
                    "matched_text": match.group().strip(),
                    "context": text[context_start:context_end].strip(),
                    "source": source,
                    "pattern": pattern_type,
                })

            except (ValueError, IndexError):
                continue

    return results


def _match_relative_patterns(text: str) -> List[Dict[str, Any]]:
    """Extract relative date references and calculate absolute dates."""
    today = date.today()
    results = []

    for pattern, unit in _RELATIVE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE):
            matched_text = match.group().strip()

            # Avoid duplicates
            if any(r["matched_text"] == matched_text for r in results):
                continue

            try:
                if unit == "fortnight":
                    parsed = today + timedelta(days=15)
                elif unit == "week":
                    parsed = today + timedelta(days=7)
                elif unit == "next_month":
                    day = int(match.group(1))
                    next_month = today.month + 1 if today.month < 12 else 1
                    next_year = today.year if today.month < 12 else today.year + 1
                    try:
                        parsed = date(next_year, next_month, day)
                    except ValueError:
                        parsed = date(next_year, next_month, 1)
                elif unit == "business":
                    days = int(match.group(1))
                    parsed = _add_business_days(today, days)
                else:  # calendar
                    days = int(match.group(1))
                    parsed = today + timedelta(days=days)
            except (ValueError, IndexError):
                continue

            context_start = max(0, match.start() - 30)
            context_end = min(len(text), match.end() + 30)

            results.append({
                "date": parsed.isoformat(),
                "matched_text": matched_text,
                "context": text[context_start:context_end].strip(),
                "source": "relative",
                "relative_days": (parsed - today).days,
            })

    return results


# ── LLM fallback ──────────────────────────────────────────────

_DEADLINE_LLM_PROMPT = """Extract ALL deadlines or dates mentioned in this text.

For each date found, output:
- The exact date in YYYY-MM-DD format
- The text that contains the date
- What the deadline is for (type: signing, payment, submission, meeting, other)

If a date is relative (e.g., "sous 30 jours" or "within 30 days"), calculate the absolute date.

If no dates are found, output an empty JSON array.

Output ONLY valid JSON array, no other text.

Example:
[
  {"date": "2025-12-31", "matched_text": "au 31 décembre 2025", "purpose": "signing"},
  {"date": "2024-08-15", "matched_text": "dans 30 jours", "purpose": "payment"}
]"""


async def _llm_extract_deadlines(text: str) -> List[Dict[str, Any]]:
    """
    Use LLM to extract deadlines when regex patterns fail.
    """
    from app.core.llm import llm_complete

    max_chars = 2000
    truncated = text[:max_chars]

    messages = [
        {"role": "system", "content": _DEADLINE_LLM_PROMPT},
        {"role": "user", "content": f"Text: {truncated}"},
    ]

    response = await llm_complete(messages, max_tokens=1024, temperature=0.1)

    if not response.strip():
        return []

    try:
        import json
        # Try to find JSON array in response
        json_match = re.search(r"\[[\s\S]*\]", response)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response)

        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug("LLM deadline parsing failed: %s", e)
        return []


# ── Public API ────────────────────────────────────────────────


async def extract_deadlines(
    text: str,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    Extract all deadlines and dates from text.

    Pipeline:
    1. Regex: extract explicit dates
    2. Regex: extract relative dates → calculate absolute
    3. LLM (optional): fallback for complex cases

    Args:
        text: The text to analyze
        use_llm: Whether to use LLM fallback

    Returns:
        Dict with extracted deadlines and metadata
    """
    results: List[Dict[str, Any]] = []

    # Step 1: Explicit date patterns
    explicit = _match_explicit_patterns(text)
    results.extend(explicit)

    # Step 2: Relative date patterns
    relative = _match_relative_patterns(text)
    results.extend(relative)

    # Step 3: LLM fallback
    llm_results = []
    if use_llm:
        llm_results = await _llm_extract_deadlines(text)
        # Add LLM results that aren't already found by regex
        existing_dates = {r["date"] for r in results}
        for r in llm_results:
            if r.get("date") not in existing_dates:
                results.append({
                    "date": r.get("date", ""),
                    "matched_text": r.get("matched_text", ""),
                    "context": "",
                    "source": "llm",
                    "purpose": r.get("purpose", "unknown"),
                })

    # Sort by date
    results.sort(key=lambda r: r.get("date", ""))

    # Find the nearest future deadline
    today = date.today()
    nearest = None
    for r in results:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if d >= today:
                if nearest is None or d < datetime.strptime(nearest["date"], "%Y-%m-%d").date():
                    nearest = r
        except (ValueError, KeyError):
            continue

    return {
        "deadlines": results,
        "total": len(results),
        "nearest_deadline": nearest,
        "sources": {
            "explicit": len(explicit),
            "relative": len(relative),
            "llm": len(llm_results),
        },
    }
