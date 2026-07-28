"""Unit tests for context_optimizer.py — dynamic top_k + compression.

Tests compute_complexity, compute_dynamic_top_k, compress_chunks,
and prepare_context_for_llm in isolation.
"""

import pytest
from typing import Any, Dict, List


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def sample_chunks() -> List[Dict[str, Any]]:
    """Five chunks of decreasing relevance."""
    return [
        {"text": "Le contrat de vente immobilière doit être signé devant un notaire.", "score": 0.95},
        {"text": "La clause de non-concurrence est valable pour une durée de 3 ans. Elle doit être limitée.", "score": 0.85},
        {"text": "Les parties peuvent résilier le contrat par lettre recommandée avec accusé de réception.", "score": 0.70},
        {"text": "Le prix de vente est fixé à 250 000 euros TTC payable comptant.", "score": 0.55},
        {"text": "Le tribunal compétent est celui du lieu de situation de l'immeuble.", "score": 0.40},
    ]


# ── compute_complexity ──────────────────────────────────────────

class TestComputeComplexity:
    """Tests for compute_complexity(query)."""

    def test_empty_query(self):
        """Empty/blank query returns 0.0."""
        from app.rag.context_optimizer import compute_complexity
        assert compute_complexity("") == 0.0
        assert compute_complexity("   ") == 0.0
        assert compute_complexity("\t\n") == 0.0

    def test_short_simple_query(self):
        """Short query with no legal terms returns low complexity."""
        from app.rag.context_optimizer import compute_complexity
        score = compute_complexity("hello world")
        assert 0.0 <= score <= 0.3

    def test_legal_query_high_complexity(self):
        """Query with legal terms returns higher complexity."""
        from app.rag.context_optimizer import compute_complexity
        score = compute_complexity("résiliation contrat clause litige tribunal")
        assert score > 0.3  # Multiple legal terms

    def test_long_complex_query(self):
        """Long query returns high complexity."""
        from app.rag.context_optimizer import compute_complexity
        long_query = "Quelles sont les clauses de résiliation dans ce contrat de vente immobilière avec condition suspensive"
        score = compute_complexity(long_query)
        assert score > 0.4

    def test_question_query(self):
        """Question-form query gets a boost."""
        from app.rag.context_optimizer import compute_complexity
        question = "Comment puis-je résilier mon contrat?"
        keyword = "résilier mon contrat"
        assert compute_complexity(question) > compute_complexity(keyword)

    def test_output_range(self):
        """Output is always in [0.0, 1.0]."""
        from app.rag.context_optimizer import compute_complexity
        queries = ["", "a", "test", "résiliation contrat" * 10, "a" * 1000]
        for q in queries:
            score = compute_complexity(q)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for query {q[:20]}"

    def test_french_legal_terms_counted(self):
        """French legal terms like 'notaire', 'vente', 'prêt' increase complexity."""
        from app.rag.context_optimizer import compute_complexity
        legal = compute_complexity("contrat de vente devant notaire")
        plain = compute_complexity("bonjour comment allez vous")
        assert legal > plain


# ── compute_dynamic_top_k ───────────────────────────────────────

class TestComputeDynamicTopK:
    """Tests for compute_dynamic_top_k(query)."""

    def test_min_chunks_for_simple_query(self):
        """Simple query returns min_k chunks."""
        from app.rag.context_optimizer import compute_dynamic_top_k
        k = compute_dynamic_top_k("hi")
        assert k == 2  # min_k

    def test_max_chunks_for_very_complex_query(self):
        """Very complex query approaches max_k."""
        from app.rag.context_optimizer import compute_dynamic_top_k
        k = compute_dynamic_top_k(
            "Quelles sont les clauses de résiliation pour litige entre vendeur et acquéreur "
            "dans un contrat de vente immobilière avec condition suspensive de prêt"
        )
        assert 4 <= k <= 12

    def test_custom_bounds(self):
        """Custom min_k and max_k are respected."""
        from app.rag.context_optimizer import compute_dynamic_top_k
        k = compute_dynamic_top_k("test", min_k=1, max_k=5)
        assert 1 <= k <= 5

    def test_monotonic(self):
        """Longer / more legal queries should not get fewer chunks than short ones."""
        from app.rag.context_optimizer import compute_dynamic_top_k
        short = compute_dynamic_top_k("hello")
        long_ = compute_dynamic_top_k("résiliation contrat de vente avec clause pénale")
        assert long_ >= short

    def test_output_is_int(self):
        """Return value is always an integer."""
        from app.rag.context_optimizer import compute_dynamic_top_k
        assert isinstance(compute_dynamic_top_k("test"), int)


# ── compress_chunks ─────────────────────────────────────────────

class TestCompressChunks:
    """Tests for compress_chunks(chunks, token_budget)."""

    def test_empty_chunks_returns_empty(self):
        """Empty list returns empty list."""
        from app.rag.context_optimizer import compress_chunks
        assert compress_chunks([]) == []

    def test_top_two_kept_full(self, sample_chunks):
        """Top 2 chunks are kept at full length."""
        from app.rag.context_optimizer import compress_chunks
        result = compress_chunks(sample_chunks, token_budget=99999)
        assert result[0]["text"] == sample_chunks[0]["text"]
        assert result[1]["text"] == sample_chunks[1]["text"]
        assert "compressed" not in result[0]
        assert "compressed" not in result[1]

    def test_bottom_chunks_compressed(self, sample_chunks):
        """Bottom chunks are marked as compressed and shortened."""
        from app.rag.context_optimizer import compress_chunks
        result = compress_chunks(sample_chunks, token_budget=99999)
        for i in range(2, len(result)):
            assert result[i].get("compressed"), f"Chunk {i} should be compressed"
            assert " [...]" in result[i]["text"]

    def test_tight_budget_truncates_more(self, sample_chunks):
        """Very tight budget removes chunks from the bottom."""
        from app.rag.context_optimizer import compress_chunks
        # Very small budget (1 token)
        result = compress_chunks(sample_chunks, token_budget=1)
        assert len(result) < len(sample_chunks)  # Some were removed
        assert len(result) >= 2  # At least min_chunks remain

    def test_preserves_order(self, sample_chunks):
        """Chunk order is preserved after compression."""
        from app.rag.context_optimizer import compress_chunks
        result = compress_chunks(sample_chunks, token_budget=99999)
        for i, r in enumerate(result):
            assert r["text"].startswith(sample_chunks[i]["text"][:20])

    def test_score_preserved(self, sample_chunks):
        """Score field is preserved through compression."""
        from app.rag.context_optimizer import compress_chunks
        result = compress_chunks(sample_chunks, token_budget=99999)
        for i, r in enumerate(result):
            assert r["score"] == sample_chunks[i]["score"]

    def test_single_chunk(self):
        """Single chunk is returned unchanged."""
        from app.rag.context_optimizer import compress_chunks
        chunks = [{"text": "Test content", "score": 1.0}]
        result = compress_chunks(chunks)
        assert len(result) == 1
        assert result[0]["text"] == "Test content"

    def test_min_chunks_respected_under_budget_pressure(self, sample_chunks):
        """At least min_chunks (2) remain even with very tight budget."""
        from app.rag.context_optimizer import compress_chunks
        result = compress_chunks(sample_chunks, token_budget=1)
        assert len(result) >= 2


# ── prepare_context_for_llm ─────────────────────────────────────

class TestPrepareContextForLLM:
    """Tests for prepare_context_for_llm(chunks, token_budget)."""

    def test_returns_string(self, sample_chunks):
        """Output is always a string."""
        from app.rag.context_optimizer import prepare_context_for_llm
        ctx = prepare_context_for_llm(sample_chunks)
        assert isinstance(ctx, str)

    def test_contains_fragment_markers(self, sample_chunks):
        """Output contains [Fragment N] markers."""
        from app.rag.context_optimizer import prepare_context_for_llm
        ctx = prepare_context_for_llm(sample_chunks)
        assert "[Fragment 1]" in ctx
        assert "[Fragment 2]" in ctx

    def test_compressed_fragments_marked(self, sample_chunks):
        """Compressed chunks have (resumido) tag."""
        from app.rag.context_optimizer import prepare_context_for_llm
        ctx = prepare_context_for_llm(sample_chunks, token_budget=100)
        assert "(resumido)" in ctx

    def test_empty_chunks(self):
        """Empty chunks return empty string."""
        from app.rag.context_optimizer import prepare_context_for_llm
        assert prepare_context_for_llm([]) == ""

    def test_respects_token_budget(self, sample_chunks):
        """Total chars in output respect token budget."""
        from app.rag.context_optimizer import prepare_context_for_llm
        budget = 500  # 500 tokens = 2500 chars
        ctx = prepare_context_for_llm(sample_chunks, token_budget=budget)
        # Allow some overhead for markers + separators
        assert len(ctx) <= budget * 5 + 500
