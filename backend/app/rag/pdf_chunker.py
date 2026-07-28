"""
Semantic chunking for French notarial documents (PDF-specific).

Delegates to the enhanced chunker in app.rag.chunker, which provides
comprehensive French notarial section detection, sentence-aware
splitting, and section context tracking.

Maintained as a separate entry point for PDF extraction callers.
"""

import logging
from typing import List, Tuple

from app.rag.chunker import chunk_by_sections as _base_chunk

logger = logging.getLogger(__name__)


def chunk_by_sections(text: str, min_chunk_size: int = 200, max_chunk_size: int = 2000) -> List[Tuple[str, int]]:
    """Split legal text into semantic chunks (delegates to app.rag.chunker).

    Args:
        text: Full document text
        min_chunk_size: Minimum characters per chunk
        max_chunk_size: Maximum characters per chunk (unused, kept for compat)

    Returns:
        List of (chunk_text, chunk_index) tuples
    """
    return _base_chunk(text, min_chunk_size=min_chunk_size)
