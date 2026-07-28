"""
Dynamic top_k selection + content compression for RAG.

Adjusts the number of chunks to retrieve based on query complexity,
and compresses low-relevance chunks to fit context windows.

Query complexity factors:
  - Length (more chars → more complex)
  - Legal terminology density
  - Question vs keyword form

Compression strategy:
  - Top-ranked chunks: keep full text
  - Lower-ranked chunks: truncate to key sentences
  - Total context kept under a configurable token budget
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Legal terms indicating complex queries
_LEGAL_TERMS = {
    "contrat", "clause", "résiliation", "résilier", "litige", "tribunal",
    "juridiction", "notaire", "acte", "vente", "acquéreur", "vendeur",
    "hypothèque", "prêt", "créance", "débiteur", "créancier",
    "nullité", "prescription", "délai", "forclusion", "appel",
    "cession", "bail", "indemnité", "dommages", "intérêts",
    "condition suspensive", "condition résolutoire", "préjudice",
    "signature", "authentique", "enregistrement", "publicité foncière",
}

# Characters per token (conservative estimate for French text)
_CHARS_PER_TOKEN = 5

# Default context budget in tokens
_DEFAULT_TOKEN_BUDGET = 3000

# Minimum and maximum chunks
_MIN_CHUNKS = 2
_MAX_CHUNKS = 12


def compute_complexity(query: str) -> float:
    """Compute query complexity score (0.0 to 1.0).

    Factors:
      - Normalised length (longer → more complex)
      - Legal term density
      - Question structure (questions tend to be more specific)
    """
    if not query.strip():
        return 0.0

    query_lower = query.lower()
    words = query_lower.split()
    num_words = len(words)

    # 1. Length factor (sigmoid-like: 5 words → 0.3, 15 words → 0.7, 30+ → 1.0)
    length_factor = min(1.0, num_words / 25.0)

    # 2. Legal term density
    legal_count = sum(1 for term in _LEGAL_TERMS if term in query_lower)
    legal_density = min(1.0, legal_count / max(num_words * 0.3, 1.0))

    # 3. Question factor
    is_question = any(query_lower.startswith(q) for q in ("what", "how", "why", "when", "where", "qui", "quoi", "comment", "pourquoi", "quand", "où", "est-ce"))
    question_factor = 0.2 if is_question else 0.0

    # Weighted combination
    score = 0.4 * length_factor + 0.4 * legal_density + 0.2 * question_factor
    return min(1.0, max(0.0, score))


def compute_dynamic_top_k(
    query: str,
    min_k: int = _MIN_CHUNKS,
    max_k: int = _MAX_CHUNKS,
) -> int:
    """Compute the optimal number of chunks for a given query.

    Args:
        query: The search query.
        min_k: Minimum chunks to always retrieve.
        max_k: Maximum chunks to ever retrieve.

    Returns:
        Number of chunks to retrieve (between min_k and max_k).
    """
    complexity = compute_complexity(query)
    # Map complexity [0, 1] → top_k [min_k, max_k]
    k = min_k + int(complexity * (max_k - min_k))
    return max(min_k, min(max_k, k))


def compress_chunks(
    chunks: List[Dict[str, Any]],
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
    chars_per_token: int = _CHARS_PER_TOKEN,
) -> List[Dict[str, Any]]:
    """Compress low-ranked chunks to fit within a token budget.

    Strategy:
      - Top 2 chunks: keep full text
      - Middle chunks: keep first 75% of text
      - Bottom chunks: keep first 50% of text
      - If still over budget: progressively truncate from bottom

    Args:
        chunks: Ranked list of result dicts (must have "text" and "score" keys).
        token_budget: Maximum total tokens for all chunks combined.

    Returns:
        Compressed chunks with original ranking preserved.
    """
    if not chunks:
        return []

    char_budget = token_budget * chars_per_token
    compressed: List[Dict[str, Any]] = []

    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        text_len = len(text)

        if i < 2:
            # Keep top 2 chunks at full length
            compressed.append(chunk)
        elif i < len(chunks) // 2:
            # Middle chunks: truncate to 75%
            limit = int(text_len * 0.75)
            compressed.append({**chunk, "text": text[:limit] + " [...]", "compressed": True})
        else:
            # Bottom chunks: truncate to 50%
            limit = int(text_len * 0.50)
            compressed.append({**chunk, "text": text[:limit] + " [...]", "compressed": True})

    # Check total budget and progressively truncate from bottom if needed
    total_chars = sum(len(c["text"]) for c in compressed)
    if total_chars <= char_budget:
        return compressed

    # Truncate from bottom up until we fit
    for i in range(len(compressed) - 1, -1, -1):
        if total_chars <= char_budget:
            break
        chunk = compressed[i]
        text = chunk["text"]
        target = int(len(text) * 0.5)
        if target < 100:
            continue  # Don't make chunks too small
        saved = len(text) - target
        compressed[i] = {**chunk, "text": text[:target] + " [...]", "compressed": True}
        total_chars -= saved

    # Last resort: hard truncate context
    if total_chars > char_budget:
        # Remove lowest-ranked chunks one by one
        while len(compressed) > _MIN_CHUNKS and total_chars > char_budget:
            removed = compressed.pop()
            total_chars -= len(removed["text"])

    logger.debug(
        "Compressed %d chunks to ~%d tokens (budget=%d)",
        len(compressed),
        total_chars // chars_per_token,
        token_budget,
    )

    return compressed


def prepare_context_for_llm(
    chunks: List[Dict[str, Any]],
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
) -> str:
    """Prepare compressed chunk text for LLM context.

    Concatenates chunks with separators, respecting token budget.

    Args:
        chunks: Ranked chunks from search (may have been compressed).
        token_budget: Maximum token budget for the assembled context.

    Returns:
        Formatted context string ready for LLM injection.
    """
    compressed = compress_chunks(chunks, token_budget)
    fragments = []
    for i, chunk in enumerate(compressed):
        tag = f"[Fragment {i+1}]"
        if chunk.get("compressed"):
            tag += " (resumido)"
        fragments.append(f"{tag}\n{chunk['text']}")

    return "\n\n---\n\n".join(fragments)
