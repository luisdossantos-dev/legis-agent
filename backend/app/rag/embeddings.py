"""
Multi-provider embeddings with local lightweight support.

Providers (in priority order):
  1. fastembed (local ONNX, ~33-117 MB, works offline, no torch)
  2. OpenAI text-embedding-3-small (API, requires key)
  3. Deterministic mock (dev mode, no deps needed)

The provider is auto-detected: fastembed is used when no OpenAI
key is configured; OpenAI is used when a valid key exists.
"""

import logging
from typing import List, Optional

import numpy as np

from app.core.config import settings
from app.core.logging import record_error

logger = logging.getLogger(__name__)

# Default model for each provider
_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"  # 70 MB, general purpose (handles French well)
_FASTEMBED_DIM = 384
_OPENAI_MODEL = "text-embedding-3-small"
_OPENAI_DIM = 1536


class EmbeddingsProvider:
    """Multi-provider embeddings with automatic fallback.

    Provider selection:
      - ``EMBEDDING_PROVIDER=fastembed`` or no API key → local ONNX model
      - ``EMBEDDING_PROVIDER=openai`` + valid key → OpenAI API
      - ``EMBEDDING_PROVIDER=mock`` or any failure → deterministic mock
    """

    def __init__(self) -> None:
        self._client: Optional[object] = None  # OpenAI client or fastembed model
        self._impl: str = "mock"
        self._auth_failed = False
        self._init_provider()

    def _init_provider(self) -> None:
        """Select and initialise the best available embedding provider."""
        from app.core.runtime_config import get_active_api_key

        provider_setting = settings.EMBEDDING_PROVIDER or "auto"

        # 1. Try fastembed (local, lightweight, no API key needed)
        if provider_setting in ("auto", "fastembed"):
            if self._try_fastembed():
                return

        # 2. Try OpenAI (requires valid key)
        key = (get_active_api_key() or settings.LITELLM_API_KEY).strip()
        if provider_setting in ("auto", "openai") and key and key != "sk-your-api-key-here":
            if self._try_openai(key):
                return

        # 3. Fallback: mock
        self._impl = "mock"
        logger.info(
            "Embeddings: using mock mode. "
            "Install fastembed (`pip install legis-agent[embed]`) or configure an OpenAI key."
        )

    def _try_fastembed(self) -> bool:
        """Try to initialise fastembed (local ONNX embeddings)."""
        try:
            from fastembed import TextEmbedding

            model_name = _FASTEMBED_MODEL
            logger.info("Embeddings: loading fastembed model %s...", model_name)
            self._client = TextEmbedding(model_name=model_name)
            self._impl = "fastembed"
            logger.info("Embeddings: fastembed ready (%s, %d dim)", model_name, _FASTEMBED_DIM)
            return True
        except ImportError:
            logger.debug("fastembed not installed — try: pip install fastembed")
        except Exception as e:
            logger.warning("fastembed init failed: %s", e)
        return False

    def _try_openai(self, api_key: str) -> bool:
        """Try to initialise the OpenAI embedding client."""
        try:
            from openai import OpenAI as OpenAIEmbed
            import httpx
            http_client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
            self._client = OpenAIEmbed(api_key=api_key, http_client=http_client)
            self._impl = "openai"
            logger.info("Embeddings: using OpenAI (%s, %d dim)", _OPENAI_MODEL, _OPENAI_DIM)
            return True
        except Exception as e:
            logger.warning("OpenAI embedding init failed: %s", e)
        return False

    # ── Public API ─────────────────────────────────────────────

    @property
    def provider(self) -> str:
        """Current provider name (fastembed | openai | mock)."""
        return self._impl

    @property
    def dimension(self) -> int:
        """Embedding dimension for the current provider."""
        if self._impl == "fastembed":
            return _FASTEMBED_DIM
        elif self._impl == "openai":
            return settings.EMBEDDING_DIMENSIONS or _OPENAI_DIM
        return settings.EMBEDDING_DIMENSIONS or _OPENAI_DIM

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (one per input text)
        """
        if not texts:
            return []

        if self._impl == "fastembed":
            return await self._embed_fastembed(texts)
        elif self._impl == "openai":
            return await self._embed_openai(texts)

        return self._mock_embeddings(texts)

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        results = await self.embed_texts([text])
        return results[0] if results else []

    # ── Provider implementations ───────────────────────────────

    async def _embed_fastembed(self, texts: List[str]) -> List[List[float]]:
        """Embed with local fastembed model (synchronous, runs in thread pool)."""
        import asyncio

        loop = asyncio.get_event_loop()

        def _run() -> List[List[float]]:
            # fastembed.embed() returns a generator of numpy arrays
            embeddings = list(self._client.embed(texts))  # type: ignore[union-attr]
            return [emb.tolist() for emb in embeddings]

        try:
            return await loop.run_in_executor(None, _run)
        except Exception as e:
            logger.error("fastembed error: %s. Falling back to mock.", e)
            self._impl = "mock"
            return self._mock_embeddings(texts)

    async def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Embed with OpenAI API."""
        if self._auth_failed:
            return self._mock_embeddings(texts)

        try:
            from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1.0, min=1.0, max=10.0),
                retry=retry_if_exception_type((ConnectionError, TimeoutError)),
                reraise=True,
            )
            def _call_embeddings():
                return self._client.embeddings.create(  # type: ignore[union-attr]
                    model=_OPENAI_MODEL,
                    input=texts,
                    dimensions=settings.EMBEDDING_DIMENSIONS,
                )

            import asyncio
            response = await asyncio.to_thread(_call_embeddings)
            return [item.embedding for item in response.data]

        except Exception as e:
            self._auth_failed = True
            error_msg = str(e)
            record_error(
                source="embeddings",
                message=f"OpenAI embedding failed: {error_msg[:200]}",
            )
            logger.error("OpenAI embedding failed: %s. Falling back to mock.", error_msg[:100])
            self._impl = "mock"
            return self._mock_embeddings(texts)

    # ── Mock fallback ──────────────────────────────────────────

    def _mock_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Deterministic mock embeddings for development."""
        dim = self.dimension
        rng = np.random.RandomState(42)
        return [rng.randn(dim).tolist() for _ in texts]


# Singleton
embeddings_provider = EmbeddingsProvider()
