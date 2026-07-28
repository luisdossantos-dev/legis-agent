"""
Semantic chunking for French notarial documents.

Splits legal text into semantic chunks by detecting document structure
(TITRES, CHAPITRES, SECTIONS, Articles, Clauses) and respecting
sentence boundaries. Each chunk carries its section header context
for better retrieval.

Supports French notarial documents (primary), Spanish legal documents
(fallback), and generic text (last resort).
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Section header patterns (French notarial primary) ──────────

_SECTION_PATTERNS = [
    # Roman numeral sections (I., II., III., etc.)
    r"(?:^|\n)(I{1,3}|IV|V|VI{0,3}|IX|X)[\.\)]\s+(?:[A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ][A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\s\-]+)",
    # Articles
    r"(?:^|\n)(?:Article\s+)(?:premier|1er|1|première)\b",
    r"(?:^|\n)(?:Article\s+)(\d+)\b",
    # French parties / parts
    r"(?:^|\n)(?:PREMIÈRE|DEUXIÈME|TROISIÈME|QUATRIÈME|CINQUIÈME|SIXIÈME|SEPTIÈME|HUITIÈME|NEUVIÈME|DIXIÈME)\s+(?:PARTIE|PART)",
    # French chapters / titles / sections
    r"(?:^|\n)(?:CHAPITRE|TITRE|SECTION|PARAGRAPHE)\s+(?:PREMIER|PREMIÈRE|I{1,3}|IV|V|VI{0,3}|IX|X|\d+)",
    r"(?:^|\n)(?:CHAPITRE|TITRE|SECTION|PARAGRAPHE)\s+(?:UNIQUE|PRÉLIMINAIRE|PRELIMINAIRE)",
    # French clauses
    r"(?:^|\n)(?:Clause|CLause|CLAUSE)\s+(?:préliminaire|préalable|première|unique|\d+)",
    # Notarial recitals
    r"(?:^|\n)(?:CONSIDÉRANT|CONSIDERANT|ATTENDU|VU|VUES|VU QUE|ATTENDU QUE)\s",
    r"(?:^|\n)(?:ENTRE\s+(?:LES\s+)?SOUSSIGNÉS?\b|ENTRE\s+LES\s+PARTIES\b)",
    # Notarial closing
    r"(?:^|\n)(?:FAIT\s+(?:à|A)\s|SIGNÉ\s+(?:à|A)\s|SIGNATURE\b)",
    # Common sections
    r"(?:^|\n)(?:DÉSIGNATION|DESIGNATION|OBJET|OBJET\s*:)\s",
    r"(?:^|\n)(?:STIPULATION|STIPULATIONS)\s",
    # Spanish fallback patterns
    r"(?:^|\n)(?:Artículo|Art\.|Sección|SECCIÓN|Cláusula|CAPÍTULO|TÍTULO)\s+\d+",
    r"(?:^|\n)(?:PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA|SÉPTIMA|OCTAVA|NOVENA|DÉCIMA)[\.\-\s)]",
]

_COMPILED_SECTION_RE = re.compile(
    "|".join(_SECTION_PATTERNS),
    re.MULTILINE | re.IGNORECASE,
)

# Sentence boundary (for clean cuts)
_SENTENCE_END_RE = re.compile(r"([.!?])\s+")

# Minimum chars for a standalone chunk
_MIN_CHUNK_CHARS = 100


def chunk_by_sections(
    text: str,
    min_chunk_size: int = 200,
) -> List[Tuple[str, int]]:
    """Split legal text into semantic chunks with section context.

    Pipeline:
      1. Detect section boundaries (French notarial structure)
      2. Split into sections with header tracking
      3. Subdivide oversized sections at sentence boundaries
      4. Carry section header forward for context
      5. Add overlap between consecutive chunks

    Args:
        text: Full document text
        min_chunk_size: Minimum characters per chunk

    Returns:
        List of (chunk_text_with_context, chunk_index)
    """
    if not text or not text.strip():
        return []

    # Step 1: Detect section boundaries
    sections = _split_by_sections(text)

    # Step 2: Merge undersized consecutive sections
    sections = _merge_small_sections(sections, settings.CHUNK_SIZE // 2)

    # Step 3: Build chunks from sections
    chunks: List[Tuple[str, str, int]] = []  # (text, section_header, index)

    for i, (header, body) in enumerate(sections):
        if not body.strip():
            continue

        body_len = len(body)
        if body_len <= settings.CHUNK_SIZE:
            # Small enough — keep as one chunk with header context
            chunks.append((body.strip(), header, len(chunks)))
        else:
            # Too large — subdivide at sentence boundaries
            sub_chunks = _split_at_sentence_boundary(body, settings.CHUNK_SIZE, _MIN_CHUNK_CHARS)
            for sub in sub_chunks:
                chunks.append((sub.strip(), header, len(chunks)))

    # If no sections were detected, fall back to paragraph splitting
    if len(chunks) <= 1 and len(text) > settings.CHUNK_SIZE:
        chunks = _fallback_chunking(text)

    # Step 3: Add section context and overlap
    chunks = _add_context_and_overlap(chunks)

    # Step 4: Enforce minimum size (merge tiny trailing chunks)
    chunks = _merge_tiny_chunks(chunks, _MIN_CHUNK_CHARS)

    logger.info(
        "Chunker: %d chars → %d chunks (%.0f avg)",
        len(text),
        len(chunks),
        len(text) / max(len(chunks), 1),
    )

    # Return compatible format: (text, index)
    return [(c[0], c[2]) for c in chunks]


# ── Section detection ──────────────────────────────────────────


def _split_by_sections(text: str) -> List[Tuple[str, str]]:
    """Split text into (section_header, body) pairs.

    The first entry has an empty header (preamble before first section).
    Each subsequent entry pairs a detected section header with its body
    (everything from the header to the next section).
    """
    matches = list(_COMPILED_SECTION_RE.finditer(text))

    if not matches:
        return [("", text)]

    sections: List[Tuple[str, str]] = []

    # Preamble before first section
    if matches[0].start() > 0:
        preamble = text[:matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))

    # Each section: header + body (until next match)
    for i, match in enumerate(matches):
        header = text[match.start():match.end()].strip()

        # Body starts after this header, ends at next header (or end of text)
        body_start = match.end()
        if i + 1 < len(matches):
            body = text[body_start:matches[i + 1].start()].strip()
        else:
            body = text[body_start:].strip()

        sections.append((header, body))

    return sections


def _merge_small_sections(
    sections: List[Tuple[str, str]],
    min_combined: int = 400,
) -> List[Tuple[str, str]]:
    """Merge consecutive sections whose combined size is below min_combined.

    Preserves section headers. Does NOT merge across top-level boundaries
    (CHAPITRE, TITRE, PARTIE, FAIT) to keep logical document structure.
    """
    if len(sections) <= 1:
        return sections

    # Headers that represent major document divisions (never merge across)
    _TOP_LEVEL = re.compile(
        r"^(?:CHAPITRE|TITRE|PARTIE|SECTION|FAIT|SIGNÉ|SIGNATURE)",
        re.IGNORECASE,
    )

    merged: List[Tuple[str, str]] = []
    current_header = ""
    current_body = ""

    for header, body in sections:
        # Detect if this is a top-level boundary
        is_top_level = bool(header and _TOP_LEVEL.match(header.strip()))

        if not current_body:
            # Start new accumulation
            current_header = header
            current_body = body
        elif is_top_level:
            # Never merge across top-level boundaries
            merged.append((current_header, current_body))
            current_header = header
            current_body = body
        elif len(current_body) + len(body) < min_combined:
            # Still small enough to merge
            current_body += "\n\n" + body
            if not current_header and header:
                current_header = header
        else:
            # Large enough — flush current and start new
            merged.append((current_header, current_body))
            current_header = header
            current_body = body

    # Flush last accumulated section
    if current_body:
        merged.append((current_header, current_body))

    return merged


# ── Sentence-aware splitting ───────────────────────────────────


def _split_at_sentence_boundary(
    text: str,
    max_size: int,
    min_size: int,
) -> List[str]:
    """Split text at sentence boundaries, respecting max_size."""
    if len(text) <= max_size:
        return [text]

    # Find sentence split points
    splits = []
    for match in _SENTENCE_END_RE.finditer(text):
        splits.append(match.end())

    if len(splits) <= 1:
        # No good sentence boundaries — fall back to paragraph split
        return _split_by_paragraphs(text, max_size, min_size)

    chunks = []
    start = 0

    for split_pos in splits:
        if split_pos - start >= max_size:
            # This sentence would exceed max_size
            if split_pos - start >= min_size:
                chunks.append(text[start:split_pos].strip())
                start = split_pos

    # Remaining text
    remaining = text[start:].strip()
    if remaining:
        if len(remaining) >= min_size or not chunks:
            chunks.append(remaining)
        else:
            # Merge with last chunk
            chunks[-1] += "\n" + remaining

    # If resulting chunks are still too large, force split at max_size
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_size:
            final_chunks.append(chunk)
        else:
            # Last resort: split at paragraph
            sub = _split_by_paragraphs(chunk, max_size, min_size)
            final_chunks.extend(sub)

    return final_chunks if final_chunks else [text]


def _split_by_paragraphs(text: str, max_size: int, min_size: int) -> List[str]:
    """Split text by double newlines, grouping up to max_size."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = []

    for para in paragraphs:
        if not current:
            current.append(para)
        elif len("\n\n".join(current + [para])) <= max_size:
            current.append(para)
        else:
            chunk = "\n\n".join(current)
            if len(chunk) >= min_size:
                chunks.append(chunk)
            current = [para]

    if current:
        chunk = "\n\n".join(current)
        if chunks and len(chunk) < min_size:
            chunks[-1] += "\n\n" + chunk
        else:
            chunks.append(chunk)

    return chunks if chunks else [text]


# ── Context and overlap ────────────────────────────────────────


def _add_context_and_overlap(
    chunks: List[Tuple[str, str, int]],
) -> List[Tuple[str, str, int]]:
    """Prepend section header context and add overlap between chunks.

    Each chunk gets its section header prepended (if available).
    Overlap: last OVERLAP_CHARS of previous chunk carried forward.
    """
    if not chunks:
        return chunks

    OVERLAP_CHARS = settings.CHUNK_OVERLAP  # 200
    result: List[Tuple[str, str, int]] = []
    prev_tail = ""
    prev_header = ""

    for text, header, idx in chunks:
        # Track the most recent non-empty header
        if header:
            prev_header = header

        # Build context prefix
        prefix = ""
        if prev_header:
            prefix = f"[{prev_header}]\n"

        # Add overlap from previous chunk
        if prev_tail:
            prefix = prev_tail + "\n...\n" + prefix

        chunk_text = prefix + text if prefix else text
        result.append((chunk_text, prev_header, idx))

        # Save tail for next chunk's overlap
        prev_tail = text[-OVERLAP_CHARS:] if len(text) > OVERLAP_CHARS else text

    return result


# ── Post-processing ────────────────────────────────────────────


def _merge_tiny_chunks(
    chunks: List[Tuple[str, str, int]],
    min_size: int,
) -> List[Tuple[str, str, int]]:
    """Merge chunks smaller than min_size into the previous chunk."""
    if len(chunks) <= 1:
        return chunks

    result: List[Tuple[str, str, int]] = []
    for text, header, idx in chunks:
        if result and len(text) < min_size:
            # Merge into previous chunk
            prev_text, prev_header, prev_idx = result[-1]
            merged = prev_text + "\n\n" + text
            result[-1] = (merged, prev_header, prev_idx)
        else:
            result.append((text, header, idx))

    return result


# ── Fallback (no sections detected) ────────────────────────────


def _fallback_chunking(text: str) -> List[Tuple[str, str, int]]:
    """Fallback: split by paragraphs, then by size with overlap."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    if not paragraphs:
        # No paragraphs either — split by size
        return _fallback_by_size(text)

    chunks: List[Tuple[str, str, int]] = []
    current = ""
    idx = 0

    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= settings.CHUNK_SIZE:
            current += "\n\n" + para
        else:
            if len(current) >= _MIN_CHUNK_CHARS:
                chunks.append((current, "", idx))
                idx += 1
            current = para

    if current:
        chunks.append((current, "", idx))

    # If still only one chunk, force size-based split
    if len(chunks) <= 1 and len(text) > settings.CHUNK_SIZE:
        return _fallback_by_size(text)

    return chunks


def _fallback_by_size(text: str) -> List[Tuple[str, str, int]]:
    """Last resort: split by word count with overlap."""
    words = text.split()
    chunks: List[Tuple[str, str, int]] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + settings.CHUNK_SIZE, len(words))
        chunk = " ".join(words[start:end])
        if chunk:
            chunks.append((chunk, "", idx))
            idx += 1
        start = end - settings.CHUNK_OVERLAP
        if start >= len(words):
            break

    return chunks if chunks else [(text, "", 0)]


# ── Metadata extraction (for advanced callers) ─────────────────


def chunk_with_metadata(text: str, min_chunk_size: int = 200) -> List[Dict[str, Any]]:
    """Like chunk_by_sections but returns rich metadata per chunk.

    Returns:
        List of dicts with keys:
          - text: chunk text with context
          - index: chunk index
          - section: detected section header (or "")
          - start_char: character offset in original text
          - end_char: end character offset
    """
    sections = _split_by_sections(text)
    chunks: List[Dict[str, Any]] = []

    char_offset = 0
    for header, body in sections:
        if not body.strip():
            char_offset += len(header) + len(body)
            continue

        chunks.append({
            "text": body.strip(),
            "index": len(chunks),
            "section": header,
            "start_char": char_offset,
            "end_char": char_offset + len(body),
        })
        char_offset += len(header) + len(body)

    return chunks
