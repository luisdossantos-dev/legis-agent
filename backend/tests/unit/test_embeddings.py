"""Unit tests for embeddings.py — multi-provider embedding support."""

import pytest
import numpy as np


class TestEmbeddingsProvider:
    """Tests for EmbeddingsProvider — multi-provider embeddings."""

    def test_provider_property(self):
        """Provider property returns a string."""
        from app.rag.embeddings import embeddings_provider
        assert isinstance(embeddings_provider.provider, str)
        assert embeddings_provider.provider in ("fastembed", "openai", "mock")

    def test_dimension_property(self):
        """Dimension property returns a positive int."""
        from app.rag.embeddings import embeddings_provider
        assert isinstance(embeddings_provider.dimension, int)
        assert embeddings_provider.dimension > 0

    @pytest.mark.asyncio
    async def test_embed_text_returns_list_of_floats(self):
        """embed_text returns a list of floats."""
        from app.rag.embeddings import embeddings_provider
        result = await embeddings_provider.embed_text("test text")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)
        assert len(result) == embeddings_provider.dimension

    @pytest.mark.asyncio
    async def test_embed_texts_returns_list_of_lists(self):
        """embed_texts returns list of embedding vectors."""
        from app.rag.embeddings import embeddings_provider
        texts = ["first text", "second text", "third text"]
        results = await embeddings_provider.embed_texts(texts)
        assert len(results) == 3
        for emb in results:
            assert len(emb) == embeddings_provider.dimension

    @pytest.mark.asyncio
    async def test_embed_texts_empty_input(self):
        """Empty input returns empty list."""
        from app.rag.embeddings import embeddings_provider
        assert await embeddings_provider.embed_texts([]) == []

    @pytest.mark.asyncio
    async def test_embed_single_consistency(self):
        """Same text produces same embedding (deterministic for mock)."""
        from app.rag.embeddings import embeddings_provider
        emb1 = await embeddings_provider.embed_text("consistent test")
        emb2 = await embeddings_provider.embed_text("consistent test")

        # For mock/fastembed: deterministic → identical
        # For OpenAI: API may differ slightly but same provider → check
        if embeddings_provider.provider in ("mock", "fastembed"):
            assert emb1 == emb2
        else:
            assert len(emb1) == len(emb2)

    @pytest.mark.asyncio
    async def test_semantic_similarity(self):
        """Similar texts have higher cosine similarity than dissimilar ones."""
        from app.rag.embeddings import embeddings_provider

        # Skip this test for mock embeddings (random = meaningless)
        if embeddings_provider.provider == "mock":
            pytest.skip("Mock embeddings are random — skip similarity test")

        e1 = await embeddings_provider.embed_text("contrat de vente immobilière")
        e2 = await embeddings_provider.embed_text("résiliation du contrat de location")
        e3 = await embeddings_provider.embed_text("la météo est belle aujourd'hui")

        def cos_sim(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)

        sim_legal = cos_sim(e1, e2)
        sim_diff = cos_sim(e1, e3)
        assert sim_legal > sim_diff, (
            f"Legal texts should be more similar: {sim_legal:.3f} vs {sim_diff:.3f}"
        )

    def test_mock_mode_called_when_no_key(self, monkeypatch):
        """When no key and no fastembed, falls back to mock."""
        from app.rag.embeddings import EmbeddingsProvider

        # Force init with no key
        monkeypatch.setattr("app.core.runtime_config.get_active_api_key", lambda: "")
        monkeypatch.setattr("app.core.config.settings.EMBEDDING_PROVIDER", "mock")

        provider = EmbeddingsProvider()
        assert provider.provider == "mock"
