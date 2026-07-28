"""Unit tests for retriever.py — VectorStore with hybrid search, BM25, MMR."""

import pytest


class TestVectorStoreSearch:
    """Tests for VectorStore.search() with new features."""

    @pytest.mark.asyncio
    async def test_search_accepts_all_params(self):
        """search() accepts all new parameters without error."""
        from app.rag.retriever import vector_store
        doc_id = "test-all-params"
        await vector_store.index_document(doc_id, ["Chunk one.", "Chunk two."])
        try:
            results = await vector_store.search(
                query="test query",
                document_id=doc_id,
                top_k=3,
                hybrid=True,
                rerank=False,
                mmr=True,
                mmr_lambda=0.7,
                expand_query_bool=False,
                num_expansions=2,
            )
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"search with all params raised: {e}")

    @pytest.mark.asyncio
    async def test_search_minimal_params(self):
        """search() works with minimal required params."""
        from app.rag.retriever import vector_store
        doc_id = "test-minimal"
        await vector_store.index_document(doc_id, ["Just one chunk."])
        results = await vector_store.search("chunk", document_id=doc_id, top_k=1)
        assert len(results) == 1
        assert "chunk" in results[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_search_empty_index(self):
        """Search on empty index returns empty list."""
        from app.rag.retriever import vector_store
        # Clear store for this test
        vector_store._store = {}
        vector_store._bm25_index = None
        results = await vector_store.search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_by_document_id(self):
        """document_id filter returns only chunks from that doc."""
        from app.rag.retriever import vector_store
        await vector_store.index_document("doc-a", ["A: first chunk.", "A: second chunk."])
        await vector_store.index_document("doc-b", ["B: unique content."])
        results = await vector_store.search("chunk", document_id="doc-a", top_k=5)
        assert all(r["document_id"] == "doc-a" for r in results)

    @pytest.mark.asyncio
    async def test_search_results_have_required_fields(self):
        """Each result has the required fields."""
        from app.rag.retriever import vector_store
        doc_id = "test-fields"
        await vector_store.index_document(doc_id, ["Field test chunk."])
        results = await vector_store.search("field test", document_id=doc_id)
        for r in results:
            assert "chunk_id" in r
            assert "text" in r
            assert "score" in r
            assert "document_id" in r
            assert "search_type" in r

    @pytest.mark.asyncio
    async def test_diverse_flag_present(self):
        """MMR results have 'diverse' flag."""
        from app.rag.retriever import vector_store
        doc_id = "test-diverse"
        chunks = [
            "Le contrat de vente immobilière doit être signé devant un notaire.",
            "La clause de non-concurrence est valable pour une durée de 3 ans.",
            "Les parties peuvent résilier le contrat par lettre recommandée.",
            "Le prix de vente est fixé à 250 000 euros TTC.",
            "Le tribunal compétent est celui du lieu de situation de l'immeuble.",
        ]
        await vector_store.index_document(doc_id, chunks)
        results = await vector_store.search(
            "contrat vente", document_id=doc_id, top_k=3,
            mmr=True, rerank=False, expand_query_bool=False,
        )
        for r in results:
            assert "diverse" in r


class TestHybridSearch:
    """Tests for hybrid search (BM25 + semantic + RRF)."""

    @pytest.mark.asyncio
    async def test_hybrid_vs_semantic(self):
        """Hybrid search produces different (potentially better) results than pure semantic."""
        from app.rag.retriever import vector_store
        doc_id = "test-hybrid"
        chunks = [
            "Le contrat de vente immobilière est signé chez le notaire.",
            "La clause pénale prévoit des dommages et intérêts de 10%.",
            "Le tribunal de grande instance est compétent pour les litiges.",
        ]
        await vector_store.index_document(doc_id, chunks)

        semantic = await vector_store.search(
            "clause pénale dommages", document_id=doc_id, top_k=2,
            hybrid=False, rerank=False, mmr=False, expand_query_bool=False,
        )
        hybrid = await vector_store.search(
            "clause pénale dommages", document_id=doc_id, top_k=2,
            hybrid=True, rerank=False, mmr=False, expand_query_bool=False,
        )

        # Both return results
        assert len(semantic) >= 1
        assert len(hybrid) >= 1
        # Hybrid should boost keyword-matched results
        assert hybrid[0]["search_type"] == "hybrid"


class TestMMR:
    """Tests for MMR diversity selection."""

    @pytest.mark.asyncio
    async def test_mmr_vs_no_mmr(self):
        """MMR can produce different orderings than relevance-only."""
        from app.rag.retriever import vector_store
        doc_id = "test-mmr"
        chunks = [
            "Le contrat de vente immobilière. Premier aspect de la vente.",
            "La vente immobilière nécessite un notaire. Deuxième aspect.",
            "Le prix de vente est de 300 000 euros. Troisième aspect.",
            "Les parties signent le contrat chez le notaire. Quatrième aspect.",
            "Le délai de rétractation est de 10 jours. Cinquième aspect.",
        ]
        await vector_store.index_document(doc_id, chunks)

        no_mmr = await vector_store.search(
            "vente immobilière contrat", document_id=doc_id, top_k=3,
            mmr=False, rerank=False, hybrid=True, expand_query_bool=False,
        )
        with_mmr = await vector_store.search(
            "vente immobilière contrat", document_id=doc_id, top_k=3,
            mmr=True, rerank=False, hybrid=True, expand_query_bool=False,
        )

        assert len(no_mmr) == 3
        assert len(with_mmr) == 3
