"""Unit tests for reranker.py — cross-encoder reranker with graceful fallback."""

import pytest


class TestReranker:
    """Tests for Reranker class."""

    def test_reranker_initialized(self):
        """Reranker singleton exists with correct defaults."""
        from app.rag.reranker import reranker
        assert reranker is not None
        assert hasattr(reranker, "rerank")

    @pytest.mark.asyncio
    async def test_rerank_empty_results(self):
        """Empty results returns empty list."""
        from app.rag.reranker import reranker
        result = await reranker.rerank("test query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_no_model_graceful(self):
        """When no model loaded, returns results as-is with reranked=False."""
        from app.rag.reranker import reranker
        results = [
            {"text": "Document about contracts.", "score": 0.9, "chunk_id": "1"},
            {"text": "Document about sales.", "score": 0.8, "chunk_id": "2"},
        ]
        # Force skip real model loading
        if hasattr(reranker, '_model'):
            reranker._model = None
            reranker._available = False

        result = await reranker.rerank("contract law", results, top_k=2)
        assert len(result) == 2
        for r in result:
            assert "reranked" in r
            assert r["reranked"] is False

    def test_rerank_candidates_constant(self):
        """_RERANK_CANDIDATES is a reasonable positive number."""
        from app.rag.reranker import _RERANK_CANDIDATES
        assert isinstance(_RERANK_CANDIDATES, int)
        assert _RERANK_CANDIDATES >= 5
        assert _RERANK_CANDIDATES <= 100


class TestRetrieverWithRerank:
    """Integration tests for retriever.search with rerank flag."""

    @pytest.mark.asyncio
    async def test_search_with_rerank_flag(self):
        """search() accepts rerank parameter without error."""
        from app.rag.retriever import vector_store
        doc_id = "test-rerank-flag"
        await vector_store.index_document(doc_id, ["Test chunk one.", "Test chunk two."])
        try:
            results = await vector_store.search(
                "test query", document_id=doc_id, top_k=2, rerank=True, hybrid=False,
                mmr=False, expand_query_bool=False,
            )
            # Should not crash
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"search with rerank=True raised: {e}")

    @pytest.mark.asyncio
    async def test_search_without_rerank(self):
        """search() works with rerank=False."""
        from app.rag.retriever import vector_store
        doc_id = "test-norerank"
        await vector_store.index_document(doc_id, ["Alpha chunk.", "Beta chunk."])
        results = await vector_store.search(
            "test", document_id=doc_id, top_k=2, rerank=False,
            hybrid=False, mmr=False, expand_query_bool=False,
        )
        assert len(results) == 2
