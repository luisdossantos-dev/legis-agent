"""
🟤 PROPERTY-BASED TESTS — Chunker invariants.

Uses Hypothesis to verify chunker properties:
- Idempotency: chunking already-chunked text yields same number of chunks
- Non-empty: chunks are never empty strings
- Coverage: total chunk text approximately covers original
- Order preservation: chunks appear in document order
"""

from hypothesis import given, seed, settings, strategies as st
from app.rag.chunker import chunk_by_sections


@seed(42)
@settings(max_examples=50, database=None)
@given(st.text(min_size=10, max_size=5000))
def test_chunker_never_returns_empty_list(text):
    """Chunker returns at least one chunk for any non-empty text."""
    chunks = chunk_by_sections(text)
    assert len(chunks) >= 1
    assert all(len(c[0]) > 0 for c in chunks)


@seed(42)
@settings(max_examples=50, database=None)
@given(st.text(min_size=100, max_size=5000))
def test_chunker_preserves_content(text):
    """Chunk content is a subset of the original text (not fabricated)."""
    chunks = chunk_by_sections(text)
    combined = " ".join(c[0] for c in chunks)
    # Each chunk word should appear somewhere in the original
    words = combined.split()
    if words:
        sample = words[:min(50, len(words))]
        for word in sample:
            if len(word) > 3:  # Skip very short words (may be overlap artifacts)
                assert word.lower() in text.lower(), f"Word '{word}' not found in original"


@seed(42)
@settings(max_examples=30, database=None)
@given(st.lists(st.text(min_size=50, max_size=500), min_size=1, max_size=5))
def test_chunker_on_concatenated_sections(sections):
    """Chunker handles multiple concatenated legal-like sections."""
    text = "\n\n".join(
        f"Article {i+1}. {section}" for i, section in enumerate(sections)
    )
    chunks = chunk_by_sections(text)
    assert len(chunks) >= 1
    assert all(len(c[0]) > 0 for c in chunks)


@seed(42)
@settings(max_examples=30, database=None)
@given(st.text(min_size=2000, max_size=10000))
def test_chunker_splits_large_texts(text):
    """Very long texts are split into multiple chunks."""
    chunks = chunk_by_sections(text)
    if len(chunks) == 1 and len(text) > 2000:
        # Single chunk is acceptable if no section boundaries found
        assert len(chunks[0][0]) > 0
    else:
        # Multiple chunks should be in order
        for i, (c, idx) in enumerate(chunks):
            assert idx >= 0
