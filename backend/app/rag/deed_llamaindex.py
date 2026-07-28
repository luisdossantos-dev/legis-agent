"""
LlamaIndex retriever for previous notarial deeds.

Indexes previous deed clauses and retrieves similar ones
as reference when drafting new clauses.

Architecture:
  1. Index existing deeds/clauses into a vector store
  2. On request, retrieve top-k similar clauses
  3. Pass retrieved clauses as context to DSPy/LiteLLM
"""

import logging
import os
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy LlamaIndex import
_llama_available = False
try:
    from llama_index.core import Document, VectorStoreIndex
    from llama_index.core.node_parser import SimpleNodeParser
    from llama_index.embeddings.openai import OpenAIEmbedding

    _llama_available = True
except ImportError:
    logger.warning("llama-index not fully installed. Use: pip install 'llama-index>=0.12'")


class DeedRetriever:
    """
    Retriever for previous notarial deeds using LlamaIndex.

    Stores indexed deed clauses and retrieves similar ones
    by semantic similarity.
    """

    def __init__(self) -> None:
        self._index: Optional[Any] = None
        self._parser = SimpleNodeParser.from_defaults(chunk_size=512, chunk_overlap=50) if _llama_available else None
        self._doc_count = 0

    @property
    def is_available(self) -> bool:
        return _llama_available

    @property
    def doc_count(self) -> int:
        return self._doc_count

    async def index_deed(self, deed_text: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Index a deed document for future retrieval.

        Args:
            deed_text: Full text of the deed or clause
            metadata: Optional metadata (act_type, date, parties, etc.)

        Returns:
            Number of chunks indexed
        """
        if not _llama_available:
            logger.warning("LlamaIndex not available, skipping index")
            return 0

        try:
            embed_model = self._get_embed_model()

            if embed_model is None:
                # No valid embedding model — store as plain text
                self._store_plain_text(deed_text, metadata)
                self._doc_count += 1
                logger.info("Deed indexed (plain text): %d chars", len(deed_text))
                return 1

            doc = Document(text=deed_text, metadata=metadata or {})

            if self._index is None:
                self._index = VectorStoreIndex.from_documents(
                    [doc],
                    embed_model=embed_model,
                    show_progress=False,
                )
            else:
                for node in self._parser.get_nodes_from_documents([doc]):
                    self._index.insert(node)

            self._doc_count += 1
            logger.info("Deed indexed (embeddings): %d chars, metadata=%s", len(deed_text), metadata)
            return 1

        except Exception as e:
            logger.warning("Failed to index deed: %s", e)
            return 0

    def _store_plain_text(self, text: str, metadata: Optional[Dict] = None) -> None:
        """Fallback: store deed text in memory without embeddings."""
        if not hasattr(self, '_plain_store'):
            self._plain_store = []
        self._plain_store.append({
            "text": text,
            "metadata": metadata or {},
        })

    async def retrieve_similar(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar deed clauses by semantic similarity.

        Args:
            query: Search query (e.g., "clause de prix vente immobilière")
            top_k: Number of results
            filters: Optional metadata filters

        Returns:
            List of retrieved documents with text and metadata
        """
        # Try embedding-based retrieval first
        if _llama_available and self._index is not None:
            try:
                retriever = self._index.as_retriever(similarity_top_k=top_k)
                if filters:
                    retriever.filters = filters
                nodes = retriever.retrieve(query)
                results = []
                for node in nodes:
                    results.append({
                        "text": node.node.text[:2000],
                        "score": node.score if hasattr(node, "score") else 0.0,
                        "metadata": node.node.metadata if hasattr(node.node, "metadata") else {},
                    })
                logger.info("Retrieved %d similar clauses from embeddings", len(results))
                return results
            except Exception as e:
                logger.warning("Embedding retrieval failed: %s", e)

        # Fallback: plain text keyword matching
        if hasattr(self, '_plain_store') and self._plain_store:
            results = []
            query_lower = query.lower()
            for doc in self._plain_store:
                text = doc["text"]
                if any(word in text.lower() for word in query_lower.split()[:5]):
                    results.append({
                        "text": text[:2000],
                        "score": 0.5,
                        "metadata": doc["metadata"],
                    })
            results = results[:top_k]
            logger.info("Retrieved %d similar clauses from plain text", len(results))
            return results

        logger.info("No deeds indexed yet")
        return []

    async def clear(self) -> None:
        """Clear all indexed deeds."""
        self._index = None
        self._doc_count = 0
        logger.info("Deed index cleared")

    def _get_embed_model(self):
        """Get the embedding model — falls back to simple text split if no valid key."""
        from app.core.runtime_config import get_active_provider

        provider_id = get_active_provider()
        # Only use OpenAI embeddings for OpenAI or generic API keys
        if provider_id not in ("openai",) and provider_id:
            logger.info("Non-OpenAI provider (%s), using simple text index", provider_id)
            return None

        from app.core.runtime_config import get_active_api_key
        api_key = get_active_api_key() or settings.LITELLM_API_KEY
        if api_key and api_key not in ("sk-your-api-key-here", ""):
            try:
                return OpenAIEmbedding(
                    model=settings.EMBEDDING_MODEL,
                    api_key=api_key,
                    dimensions=settings.EMBEDDING_DIMENSIONS,
                )
            except Exception as e:
                logger.warning("Failed to init OpenAI embeddings: %s", e)
        return None


# Singleton retriever
deed_retriever = DeedRetriever()
