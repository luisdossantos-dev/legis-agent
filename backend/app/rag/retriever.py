"""
Retriever for hybrid semantic + keyword search.

Uses Reciprocal Rank Fusion (RRF) to combine:
  - Semantic search (cosine similarity on embeddings)
  - Keyword search (BM25 Okapi)

Falls back gracefully when BM25 has no data or embeddings are mocked.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from numpy.linalg import norm

from app.core.config import settings
from app.rag.embeddings import embeddings_provider
from app.rag.reranker import reranker, _RERANK_CANDIDATES
from app.rag.query_expansion import expand_query

logger = logging.getLogger(__name__)


# ── BM25 tokenizer (French + English aware) ─────────────────────

def _tokenize(text: str) -> List[str]:
    """Tokenize text for BM25. Handles French accented characters."""
    return re.findall(r"\w+", text.lower())


# ── Reciprocal Rank Fusion ─────────────────────────────────────

_RRF_K = 60  # Standard RRF constant


def _rrf_fuse(
    semantic_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Fuse two ranked result lists using Reciprocal Rank Fusion.

    Args:
        semantic_results: Ranked list from semantic search.
        bm25_results: Ranked list from BM25 keyword search.
        top_k: Number of results to return after fusion.

    Returns:
        Fused result list, sorted by RRF score descending.
    """
    scores: Dict[str, float] = {}

    for rank, r in enumerate(semantic_results):
        scores[r["chunk_id"]] = 1.0 / (_RRF_K + rank + 1)

    for rank, r in enumerate(bm25_results):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (_RRF_K + rank + 1)

    # Build a lookup by chunk_id so we can reconstruct result dicts
    chunk_map: Dict[str, Dict[str, Any]] = {}
    for r in semantic_results:
        chunk_map[r["chunk_id"]] = r
    for r in bm25_results:
        if r["chunk_id"] not in chunk_map:
            chunk_map[r["chunk_id"]] = r

    # Sort by fused score, deduplicate
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    results: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for chunk_id, score in ranked:
        if chunk_id in seen or chunk_id not in chunk_map:
            continue
        entry = dict(chunk_map[chunk_id])
        entry["score"] = round(score, 4)
        entry["search_type"] = "hybrid"
        results.append(entry)
        seen.add(chunk_id)
        if len(results) >= top_k:
            break

    return results


# ── Vector Store ────────────────────────────────────────────────


class VectorStore:
    """Vector store with hybrid semantic + BM25 search.

    Supports multiple backends:
      - memory (default): in-memory dict + BM25Okapi index
      - pinecone: Pinecone managed index (stub — not yet implemented)
      - pgvector: PostgreSQL + pgvector (stub — not yet implemented)
    """

    def __init__(self) -> None:
        self.provider = settings.VECTOR_STORE_PROVIDER
        self._store: Dict[str, Any] = {}  # chunk_id → chunk data

        # BM25 index (built lazily from _store)
        self._bm25_index: Any = None
        self._bm25_chunk_ids: List[str] = []

        self._init_store()

    def _init_store(self) -> None:
        if self.provider == "pinecone":
            self._init_pinecone()
        elif self.provider == "pgvector":
            self._init_pgvector()
        else:
            logger.info("Vector store: using in-memory storage (dev mode)")

    def _init_pinecone(self) -> None:
        try:
            from pinecone import Pinecone

            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            self._index = pc.Index(settings.PINECONE_INDEX_NAME)
            logger.info("Vector store: Pinecone initialized")
        except ImportError:
            logger.warning("Pinecone not installed, falling back to in-memory store")
            self.provider = "memory"

    def _init_pgvector(self) -> None:
        try:
            from sqlalchemy import create_engine
            self._engine = create_engine(settings.DATABASE_URL)
            logger.info("Vector store: pgvector initialized")
        except ImportError:
            logger.warning("SQLAlchemy not installed, falling back to in-memory store")
            self.provider = "memory"

    # ── BM25 index management ──────────────────────────────────

    def _rebuild_bm25_index(self) -> None:
        """Rebuild the BM25 Okapi index from the current in-memory store."""
        from rank_bm25 import BM25Okapi

        texts: List[str] = []
        self._bm25_chunk_ids = []
        for chunk_id, data in self._store.items():
            texts.append(data["text"])
            self._bm25_chunk_ids.append(chunk_id)

        if texts:
            tokenized_corpus = [_tokenize(t) for t in texts]
            self._bm25_index = BM25Okapi(tokenized_corpus)
            logger.debug("BM25 index rebuilt: %d documents", len(texts))
        else:
            self._bm25_index = None

    # ── Document indexing ──────────────────────────────────────

    async def index_document(
        self,
        document_id: str,
        chunks: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Index document chunks into the vector store.

        Also rebuilds the BM25 index so keyword search is immediately available.

        Args:
            document_id: Document ID
            chunks: List of text chunks
            metadata: Additional metadata

        Returns:
            Number of indexed chunks
        """
        if self.provider == "pinecone":
            return await self._index_pinecone(document_id, chunks, metadata)
        elif self.provider == "pgvector":
            return await self._index_pgvector(document_id, chunks, metadata)
        else:
            return await self._index_memory(document_id, chunks, metadata)

    async def _index_memory(
        self,
        document_id: str,
        chunks: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            embedding = await embeddings_provider.embed_text(chunk)
            self._store[chunk_id] = {
                "document_id": document_id,
                "chunk_index": i,
                "text": chunk,
                "embedding": embedding,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        # Rebuild BM25 index so keyword search works immediately
        self._rebuild_bm25_index()

        logger.info("Indexed %d chunks in memory for doc %s", len(chunks), document_id)
        return len(chunks)

    async def _index_pinecone(self, document_id: str, chunks: List[str],
                               metadata: Optional[Dict[str, Any]] = None) -> int:
        logger.info("Pinecone index not yet implemented (dev mode)")
        return await self._index_memory(document_id, chunks, metadata)

    async def _index_pgvector(self, document_id: str, chunks: List[str],
                               metadata: Optional[Dict[str, Any]] = None) -> int:
        logger.info("pgvector index not yet implemented (dev mode)")
        return await self._index_memory(document_id, chunks, metadata)

    # ── Search ─────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        hybrid: bool = True,
        rerank: bool = True,
        mmr: bool = True,
        mmr_lambda: float = 0.7,
        expand_query_bool: bool = True,
        num_expansions: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Search for chunks relevant to a query.

        Pipeline:
          0. Query expansion (optional) → original + 2-3 variations
          1. For each variation: hybrid search → rerank → MMR
          2. Fusion: combine results via max-score aggregation

        Args:
            query: Query text
            top_k: Number of results to return
            document_id: Filter by document (optional)
            hybrid: If True, use hybrid semantic + BM25 search
            rerank: If True, apply cross-encoder reranking
            mmr: If True, apply MMR diversity selection
            mmr_lambda: MMR lambda (0=diversity, 1=relevance)
            expand_query_bool: If True, expand query with LLM-generated variations
            num_expansions: Number of alternative phrasings (1-4)

        Returns:
            List of results with text, score, search_type, and metadata flags
        """
        if self.provider in ("pinecone", "pgvector"):
            query_embedding = await embeddings_provider.embed_text(query)
            if self.provider == "pinecone":
                return await self._search_pinecone(query_embedding, top_k, document_id)
            return await self._search_pgvector(query_embedding, top_k, document_id)

        # ── Stage 0: Query expansion ──────────────────────────
        queries = [query]
        if expand_query_bool:
            expansions = await expand_query(query, num_expansions)
            queries.extend(expansions)

        # ── Search each query variation and fuse ──────────────
        all_results: Dict[str, Dict[str, Any]] = {}  # chunk_id → best result

        for q in queries:
            query_embedding = await embeddings_provider.embed_text(q)

            # Stage 1: initial retrieval
            pool_size = max(_RERANK_CANDIDATES, top_k * 4)
            initial_k = pool_size if (rerank or mmr) else top_k

            if hybrid and self._bm25_index is not None:
                results = self._search_hybrid(q, query_embedding, initial_k, document_id)
            else:
                results = self._search_memory(query_embedding, initial_k, document_id)

            if not results:
                continue

            # Stage 2: cross-encoder reranking
            if rerank:
                results = await reranker.rerank(q, results, initial_k)

            # Stage 3: MMR diversity
            if mmr and len(results) > top_k:
                results = self._mmr_select(results, query_embedding, top_k, mmr_lambda)

            # Fuse: keep the best score per chunk_id across all variations
            for r in results:
                cid = r["chunk_id"]
                if cid not in all_results or r["score"] > all_results[cid]["score"]:
                    r["from_expansion"] = q != query
                    all_results[cid] = r

        # Sort by score descending and return top_k
        fused = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)

        logger.debug(
            "Query expansion: %d query%s → %d unique chunks → top-%d",
            len(queries),
            "s" if len(queries) > 1 else "",
            len(fused),
            top_k,
        )

        return fused[:top_k]

    # ── Hybrid search (semantic + BM25 + RRF) ──────────────────

    def _search_hybrid(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Hybrid search: semantic (top_k*2) + BM25 (top_k*2) → RRF → top_k."""
        candidates = top_k * 2  # Get more candidates for better fusion

        semantic_results = self._search_memory(query_embedding, candidates, document_id)
        bm25_results = self._search_bm25(query, candidates, document_id)

        if not bm25_results:
            # BM25 returned nothing — fall back to pure semantic
            for r in semantic_results:
                r["search_type"] = "semantic"
            return semantic_results[:top_k]

        logger.debug(
            "Hybrid search: %d semantic + %d bm25 candidates → RRF → top-%d",
            len(semantic_results),
            len(bm25_results),
            top_k,
        )

        return _rrf_fuse(semantic_results, bm25_results, top_k)

    # ── Pure semantic search (cosine similarity) ───────────────

    def _search_memory(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query_vec = np.array(query_embedding)
        results: List[Dict[str, Any]] = []

        for chunk_id, data in self._store.items():
            if document_id and data["document_id"] != document_id:
                continue

            vec = np.array(data["embedding"])
            score = float(np.dot(query_vec, vec) / (norm(query_vec) * norm(vec) + 1e-10))
            results.append({
                "chunk_id": chunk_id,
                "text": data["text"],
                "score": score,
                "document_id": data["document_id"],
                "search_type": "semantic",
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ── BM25 keyword search ────────────────────────────────────

    def _search_bm25(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search using BM25 Okapi keyword matching."""
        if self._bm25_index is None:
            return []

        tokenized_query = _tokenize(query)
        scores = self._bm25_index.get_scores(tokenized_query)

        # Pair scores with chunk_ids and sort
        scored: List[tuple[float, str]] = list(zip(scores, self._bm25_chunk_ids))
        scored.sort(key=lambda x: x[0], reverse=True)

        results: List[Dict[str, Any]] = []
        seen = 0
        for score, chunk_id in scored:
            if score <= 0:
                continue
            data = self._store[chunk_id]
            if document_id and data["document_id"] != document_id:
                continue
            results.append({
                "chunk_id": chunk_id,
                "text": data["text"],
                "score": float(score),
                "document_id": data["document_id"],
                "search_type": "bm25",
            })
            seen += 1
            if seen >= top_k:
                break

        return results

    # ── MMR diversity selection ───────────────────────────────

    def _mmr_select(
        self,
        candidates: List[Dict[str, Any]],
        query_embedding: List[float],
        top_k: int = 5,
        lambda_param: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Select diverse results using Maximum Marginal Relevance.

        MMR balances relevance (query similarity) with diversity
        (penalising candidates that are too similar to already-selected ones).

        Formula:
          MMR = argmax [ λ * sim(q,d) - (1-λ) * max_{s∈S} sim(d,s) ]

        Args:
            candidates: Ranked candidate list from hybrid/reranker search.
            query_embedding: Query embedding vector.
            top_k: Number of results to return.
            lambda_param: MMR lambda. 0 = pure diversity, 1 = pure relevance.

        Returns:
            Diverse subset of candidates (re-ranked by MMR score).
        """
        import numpy as np
        from numpy.linalg import norm

        n = len(candidates)
        if n <= top_k:
            for r in candidates:
                r["diverse"] = False
            return candidates

        query_vec = np.array(query_embedding)

        # Build embedding matrix and query similarities
        embeddings = []
        query_sim = []
        for r in candidates:
            data = self._store.get(r["chunk_id"])
            if data and "embedding" in data:
                emb = np.array(data["embedding"])
            else:
                emb = np.zeros_like(query_vec)
            embeddings.append(emb)

            # Use reranker score if available, else cosine
            if r.get("reranked"):
                # Sigmoid-normalise logit to (0, 1) range
                qsim = 1.0 / (1.0 + np.exp(-r["score"]))
            else:
                cos = float(np.dot(query_vec, emb) / (norm(query_vec) * norm(emb) + 1e-10))
                qsim = max(0.0, cos)  # clip negative
            query_sim.append(qsim)

        # Pre-compute pairwise cosine similarity matrix
        emb_matrix = np.array(embeddings)  # (n, dim)
        norms = norm(emb_matrix, axis=1, keepdims=True) + 1e-10
        pair_sim = (emb_matrix @ emb_matrix.T) / (norms @ norms.T)
        np.clip(pair_sim, 0.0, 1.0, out=pair_sim)

        # Greedy MMR selection
        selected_indices: List[int] = []
        remaining = set(range(n))

        # First pick: highest relevance
        first = int(np.argmax(query_sim))
        selected_indices.append(first)
        remaining.remove(first)

        while len(selected_indices) < top_k and remaining:
            best_mmr = -float("inf")
            best_idx = -1

            for i in remaining:
                # Relevance term
                rel = query_sim[i]
                # Diversity term: max similarity to any selected
                max_to_selected = max(pair_sim[i][j] for j in selected_indices)
                # MMR score
                mmr = lambda_param * rel - (1.0 - lambda_param) * max_to_selected

                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i

            if best_idx >= 0:
                selected_indices.append(best_idx)
                remaining.remove(best_idx)

        # Build results preserving order from candidates
        selected_set = set(selected_indices)
        results = [
            {**candidates[i], "diverse": True}
            for i in selected_indices
        ]

        logger.debug(
            "MMR selected %d/%d candidates (λ=%.1f)",
            len(results), n, lambda_param,
        )
        return results

    # ── Provider-specific stubs (fall back to memory) ──────────

    async def _search_pinecone(self, query_embedding: List[float], top_k: int = 5,
                                document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.info("Pinecone search not yet implemented (dev mode)")
        return self._search_memory(query_embedding, top_k, document_id)

    async def _search_pgvector(self, query_embedding: List[float], top_k: int = 5,
                                document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.info("pgvector search not yet implemented (dev mode)")
        return self._search_memory(query_embedding, top_k, document_id)


# Singleton
vector_store = VectorStore()
