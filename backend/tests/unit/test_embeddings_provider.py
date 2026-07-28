"""Unit tests for the EmbeddingsProvider class."""

import pytest

from app.rag.embeddings import EmbeddingsProvider


@pytest.mark.asyncio
class TestEmbeddingsProviderMockMode:
    """Tests for EmbeddingsProvider operating in mock mode."""

    @pytest.fixture
    def mock_provider(self, monkeypatch):
        monkeypatch.setattr("app.rag.embeddings.settings.EMBEDDING_PROVIDER", "mock")
        return EmbeddingsProvider()

    async def test_provider_is_mock(self, mock_provider):
        assert mock_provider.provider == "mock"

    async def test_embed_texts_returns_vectors(self, mock_provider):
        result = await mock_provider.embed_texts(["hello"])
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])

    async def test_embed_texts_deterministic(self, mock_provider):
        result1 = await mock_provider.embed_texts(["hello world"])
        result2 = await mock_provider.embed_texts(["hello world"])
        assert result1 == result2

    async def test_embed_texts_empty_list(self, mock_provider):
        result = await mock_provider.embed_texts([])
        assert result == []

    async def test_embed_text_single(self, mock_provider):
        result = await mock_provider.embed_text("hello")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    async def test_dimension_matches(self, mock_provider):
        assert mock_provider.dimension > 0


@pytest.mark.asyncio
class TestEmbeddingsProviderDimension:
    """Tests for embedding dimension consistency."""

    @pytest.fixture
    def mock_provider_128(self, monkeypatch):
        monkeypatch.setattr("app.rag.embeddings.settings.EMBEDDING_PROVIDER", "mock")
        monkeypatch.setattr("app.rag.embeddings.settings.EMBEDDING_DIMENSIONS", 128)
        return EmbeddingsProvider()

    async def test_mock_dimension(self, mock_provider_128):
        assert mock_provider_128.dimension == 128

    async def test_mock_embedding_length_matches_dimension(self, mock_provider_128):
        result = await mock_provider_128.embed_texts(["hello", "world"])
        for vec in result:
            assert len(vec) == 128
