"""Unit tests for pure functions in app/rag/retriever.py (_tokenize, _rrf_fuse)."""

from typing import Any, Dict, List

import pytest

from app.rag.retriever import _tokenize, _rrf_fuse


# ── _tokenize ──────────────────────────────────────────────────────


class TestTokenize:
    """Tests for the _tokenize pure function."""

    def test_tokenize_simple_text(self):
        result = _tokenize("Hello world")
        assert result == ["hello", "world"]

    def test_tokenize_french_accents(self):
        result = _tokenize("contrat de vente")
        assert result == ["contrat", "de", "vente"]

    def test_tokenize_empty_string(self):
        result = _tokenize("")
        assert result == []

    def test_tokenize_special_chars(self):
        result = _tokenize("clause-pénale!?")
        assert result == ["clause", "pénale"]

    def test_tokenize_numbers(self):
        result = _tokenize("Article 1.2")
        assert result == ["article", "1", "2"]

    def test_tokenize_mixed_case(self):
        result = _tokenize("HELLO World")
        assert result == ["hello", "world"]


# ── _rrf_fuse ──────────────────────────────────────────────────────


SEMANTIC_SAMPLES: List[Dict[str, Any]] = [
    {"chunk_id": "a", "text": "A", "document_id": "doc1", "search_type": "semantic", "score": 0.9},
    {"chunk_id": "b", "text": "B", "document_id": "doc1", "search_type": "semantic", "score": 0.8},
]

BM25_SAMPLES: List[Dict[str, Any]] = [
    {"chunk_id": "b", "text": "B", "document_id": "doc1", "search_type": "bm25", "score": 5.0},
    {"chunk_id": "c", "text": "C", "document_id": "doc1", "search_type": "bm25", "score": 3.0},
]


class TestRRFFuse:
    """Tests for the _rrf_fuse pure function."""

    def test_rrf_fuse_combines_results(self):
        result = _rrf_fuse(SEMANTIC_SAMPLES, BM25_SAMPLES, top_k=10)
        chunk_ids = {r["chunk_id"] for r in result}
        # Both semantic (a, b) and bm25 (b, c) origins represented
        assert "a" in chunk_ids
        assert "b" in chunk_ids
        assert "c" in chunk_ids
        assert len(result) == 3

    def test_rrf_fuse_deduplicates(self):
        result = _rrf_fuse(SEMANTIC_SAMPLES, BM25_SAMPLES, top_k=10)
        chunk_ids = [r["chunk_id"] for r in result]
        # chunk "b" appears only once
        assert chunk_ids.count("b") == 1

    def test_rrf_fuse_respects_top_k(self):
        result = _rrf_fuse(SEMANTIC_SAMPLES, BM25_SAMPLES, top_k=2)
        assert len(result) <= 2

    def test_rrf_fuse_returns_hybrid_type(self):
        result = _rrf_fuse(SEMANTIC_SAMPLES, BM25_SAMPLES, top_k=10)
        for r in result:
            assert r["search_type"] == "hybrid"

    def test_rrf_fuse_empty_semantic(self):
        result = _rrf_fuse([], BM25_SAMPLES, top_k=10)
        assert len(result) == 2
        assert all(r["search_type"] == "hybrid" for r in result)

    def test_rrf_fuse_empty_bm25(self):
        result = _rrf_fuse(SEMANTIC_SAMPLES, [], top_k=10)
        assert len(result) == 2
        assert all(r["search_type"] == "hybrid" for r in result)

    def test_rrf_fuse_both_empty(self):
        result = _rrf_fuse([], [], top_k=10)
        assert result == []
