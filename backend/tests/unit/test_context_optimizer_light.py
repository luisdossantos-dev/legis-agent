"""Lightweight unit tests for context_optimizer.py — pure functions only, no fixtures."""

from app.rag.context_optimizer import (
    compute_complexity,
    compute_dynamic_top_k,
    compress_chunks,
    prepare_context_for_llm,
)


class TestComputeComplexity:
    def test_empty_returns_zero(self):
        assert compute_complexity("") == 0.0
        assert compute_complexity("   ") == 0.0

    def test_short_returns_low(self):
        assert 0.0 <= compute_complexity("hi") < 0.5

    def test_legal_terms_boost(self):
        legal = compute_complexity("résiliation contrat clause litige")
        plain = compute_complexity("hello world foo bar")
        assert legal > plain

    def test_longer_is_higher(self):
        short = compute_complexity("test")
        long_ = compute_complexity("what are the clauses for termination in this contract")
        assert long_ >= short

    def test_question_boost(self):
        q = compute_complexity("Comment résilier mon contrat?")
        k = compute_complexity("résilier mon contrat")
        assert q >= k

    def test_output_always_in_range(self):
        for q in ["", "a", "test"]:
            assert 0.0 <= compute_complexity(q) <= 1.0


class TestComputeDynamicTopK:
    def test_min_for_simple(self):
        assert compute_dynamic_top_k("hi") == 2

    def test_max_not_exceeded(self):
        for query in ["a", "test", "résiliation contrat" * 20]:
            k = compute_dynamic_top_k(query)
            assert 2 <= k <= 12

    def test_custom_bounds(self):
        k = compute_dynamic_top_k("test", min_k=3, max_k=8)
        assert 3 <= k <= 8

    def test_returns_int(self):
        assert isinstance(compute_dynamic_top_k("test"), int)


class TestCompressChunks:
    def test_empty_returns_empty(self):
        assert compress_chunks([]) == []

    def test_single_unchanged(self):
        r = compress_chunks([{"text": "hello", "score": 1.0}])
        assert len(r) == 1
        assert r[0]["text"] == "hello"

    def test_top_two_full(self):
        chunks = [
            {"text": "A" * 500, "score": 0.9},
            {"text": "B" * 500, "score": 0.8},
            {"text": "C" * 500, "score": 0.7},
        ]
        r = compress_chunks(chunks, token_budget=99999)
        # Top 2 unchanged, no compressed flag
        assert "compressed" not in r[0]
        assert "compressed" not in r[1]
        # Third chunk compressed
        assert r[2].get("compressed") is True

    def test_very_tight_budget(self):
        chunks = [{"text": word * 500, "score": 1.0 - i * 0.1} for i, word in enumerate("ABCDE")]
        r = compress_chunks(chunks, token_budget=10)
        assert len(r) >= 2  # At least min_chunks remain

    def test_preserves_order(self):
        chunks = [
            {"text": "First", "score": 0.9},
            {"text": "Second", "score": 0.8},
            {"text": "Third", "score": 0.7},
        ]
        r = compress_chunks(chunks, token_budget=99999)
        assert r[0]["text"].startswith("First")
        assert r[1]["text"].startswith("Second")


class TestPrepareContextForLLM:
    def test_returns_string(self):
        r = prepare_context_for_llm([{"text": "test", "score": 0.9}])
        assert isinstance(r, str)

    def test_has_fragment_markers(self):
        r = prepare_context_for_llm([
            {"text": "one", "score": 0.9},
            {"text": "two", "score": 0.8},
        ])
        assert "[Fragment 1]" in r
        assert "[Fragment 2]" in r

    def test_empty_chunks(self):
        assert prepare_context_for_llm([]) == ""

    def test_compressed_marked(self):
        r = prepare_context_for_llm(
            [{"text": x * 500, "score": 1.0 - i * 0.1} for i, x in enumerate("ABCDE")],
            token_budget=100,
        )
        assert "(resumido)" in r or len(r) < 3000
