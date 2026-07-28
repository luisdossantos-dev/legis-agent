"""
Semantic search engine for case files (expedientes).

Performs hybrid search combining:
  - Vector similarity (embeddings)
  - Metadata filtering (case_id, doc_type, category, date range)

Results are aggregated at the document level with relevant excerpts.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.rag.case_clustering import case_store
from app.rag.embeddings import embeddings_provider
from app.rag.retriever import vector_store

logger = logging.getLogger(__name__)


async def search_cases(
    query: str,
    top_k: int = 5,
    top_k_per_doc: int = 2,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Search across all case files for semantically relevant content.

    Args:
        query: Search query (natural language)
        top_k: Maximum number of document-level results
        top_k_per_doc: Maximum chunks per document to aggregate
        filters: Optional metadata filters
            - case_id: Filter to specific case
            - doc_type: Document type (vente, pouvoir, etc.)
            - doc_category: Category (principal, annexe, etc.)
            - date_from: ISO date string (filter by indexed date)

    Returns:
        Dict with results grouped by case/document
    """
    if not query.strip():
        return {"query": query, "results": [], "total": 0}

    # Step 1: Get query embedding
    query_embedding = await embeddings_provider.embed_text(query)

    # Inject original query text into filters for keyword fallback
    filter_dict = dict(filters or {})
    filter_dict["_query_text"] = query

    # Step 2: Determine which case(s) to search
    case_ids = _resolve_case_ids(filter_dict)

    # Step 3: Search the vector store for each case
    all_chunks = []
    for case_id in case_ids:
        chunks = _search_case_chunks(
            case_id=case_id,
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more per case for aggregation
            filters=filter_dict,
        )
        all_chunks.extend(chunks)

    # Step 4: Sort by score and limit
    all_chunks.sort(key=lambda c: c.get("score", 0), reverse=True)
    all_chunks = all_chunks[:top_k * top_k_per_doc]

    # Step 5: Aggregate into document-level results
    doc_results = _aggregate_by_document(all_chunks, top_k_per_doc)

    # Step 6: Add case context to each result
    for result in doc_results:
        doc_id = result.get("document_id", "")
        case_id = case_store.get_document_case(doc_id)
        if case_id:
            case = case_store.get_case(case_id)
            result["case_id"] = case_id
            result["case_name"] = case.get("name", "") if case else ""
            result["case_doc_count"] = case.get("document_count", 0) if case else 0

    # Sort final results by max chunk score
    doc_results.sort(key=lambda r: max(c.get("score", 0) for c in r.get("excerpts", [])), reverse=True)

    logger.info(
        "🔍 Case search: query='%s' → %d case-level results from %d chunks",
        query[:50], len(doc_results), len(all_chunks),
    )

    return {
        "query": query,
        "results": doc_results[:top_k],
        "total": len(doc_results[:top_k]),
    }


async def search_in_case(
    case_id: str,
    query: str,
    top_k: int = 5,
    top_k_per_doc: int = 3,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Search within a specific case file.

    Args:
        case_id: Case file ID to search within
        query: Search query (natural language)
        top_k: Maximum number of document-level results
        top_k_per_doc: Maximum chunks per document
        filters: Additional metadata filters (doc_type, doc_category)

    Returns:
        Dict with results organized by document
    """
    case = case_store.get_case(case_id)
    if not case:
        return {"query": query, "results": [], "total": 0, "error": f"Case '{case_id}' not found"}

    # Add case_id to filters
    combined_filters = dict(filters or {})
    combined_filters["case_id"] = case_id

    # Run search with case filter
    result = await search_cases(
        query=query,
        top_k=top_k,
        top_k_per_doc=top_k_per_doc,
        filters=combined_filters,
    )

    # Attach case metadata
    result["case_id"] = case_id
    result["case_name"] = case.get("name", "")
    result["case_document_count"] = case.get("document_count", 0)

    return result


# ── Internal helpers ───────────────────────────────────────────


def _resolve_case_ids(filters: Optional[Dict[str, Any]]) -> List[str]:
    """Determine which case IDs to search."""
    if not filters:
        # Search all cases
        return [c["id"] for c in case_store.list_cases()]

    case_id = filters.pop("case_id", None)
    if case_id:
        return [case_id]

    # If no case_id filter, search all
    return [c["id"] for c in case_store.list_cases()]


def _search_case_chunks(
    case_id: str,
    query_embedding: List[float],
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Search chunks belonging to a specific case.
    Searches BOTH the vector store (from doc uploads) AND the
    case store documents (from cases/process endpoint).
    """
    from numpy.linalg import norm
    import numpy as np

    query_vec = np.array(query_embedding)
    results = []

    case = case_store.get_case(case_id)
    if not case:
        return results

    # Get the map of document_id → filename/category for this case
    doc_map = {}
    for doc in case.get("documents", []):
        doc_map[doc.get("id")] = {
            "filename": doc.get("filename", ""),
            "category": doc.get("category", ""),
            "doc_type": doc.get("doc_type", ""),
            "summary": doc.get("summary", ""),
        }

    # 1. Search through vector store chunks (indexed via /api/documents/upload)
    for chunk_id, data in vector_store._store.items():
        doc_id = data.get("document_id", "")
        if doc_id not in doc_map:
            continue

        doc_info = doc_map[doc_id]

        # Apply filters
        if filters and filters.get("doc_type") and doc_info.get("doc_type") != filters["doc_type"]:
            continue
        if filters and filters.get("doc_category") and doc_info.get("category") != filters["doc_category"]:
            continue

        vec = np.array(data["embedding"])
        score = float(np.dot(query_vec, vec) / (norm(query_vec) * norm(vec) + 1e-10))

        min_score = filters.get("min_score", 0.0) if filters else 0.0
        if score < min_score:
            continue

        results.append({
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "filename": doc_info.get("filename", ""),
            "doc_category": doc_info.get("category", ""),
            "doc_type": doc_info.get("doc_type", ""),
            "text": data.get("text", ""),
            "score": round(score, 4),
        })

    # 2. Also search through case store documents directly
    #    (documents created via /api/cases/process which stores them in case_store)
    query_text = (filters or {}).get("_query_text", "").strip()
    if query_text:
        query_words = set(query_text.lower().split())
        for doc_id, doc_info in doc_map.items():
            # Skip docs already found via vector store
            if any(r["document_id"] == doc_id for r in results):
                continue

            summary = doc_info.get("summary", "") or doc_info.get("filename", "")
            if not summary:
                continue

            # Keyword overlap score
            doc_text = (doc_info.get("filename", "") + " " + summary).lower()
            doc_words = set(doc_text.split())
            overlap = len(query_words & doc_words)
            keyword_score = overlap / max(len(query_words), 1)

            # Bonus for exact phrase matches
            phrase_bonus = 0.2 if any(phrase in doc_text for phrase in [query_text.lower()]) else 0.0
            score = min(keyword_score + phrase_bonus, 0.99)

            if score > 0.1:  # Low threshold for keyword fallback
                results.append({
                    "chunk_id": f"case_doc_{doc_id}",
                    "document_id": doc_id,
                    "filename": doc_info.get("filename", ""),
                    "doc_category": doc_info.get("category", ""),
                    "doc_type": doc_info.get("doc_type", ""),
                    "text": summary[:500],
                    "score": round(score, 4),
                })

    # Sort by score and return top_k
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def _aggregate_by_document(
    chunks: List[Dict[str, Any]],
    top_k_per_doc: int = 2,
) -> List[Dict[str, Any]]:
    """
    Aggregate chunk-level results into document-level results.

    Groups chunks by document_id, keeps top excerpts per doc.
    """
    doc_groups: Dict[str, Dict[str, Any]] = {}

    for chunk in chunks:
        doc_id = chunk.get("document_id", "")

        if doc_id not in doc_groups:
            doc_groups[doc_id] = {
                "document_id": doc_id,
                "filename": chunk.get("filename", ""),
                "doc_category": chunk.get("doc_category", ""),
                "doc_type": chunk.get("doc_type", ""),
                "max_score": chunk.get("score", 0),
                "avg_score": chunk.get("score", 0),
                "excerpts": [],
                "excerpt_count": 0,
            }
        else:
            group = doc_groups[doc_id]
            group["max_score"] = max(group["max_score"], chunk.get("score", 0))
            # Running average
            count = group["excerpt_count"] + 1
            group["avg_score"] = (group["avg_score"] * group["excerpt_count"] + chunk.get("score", 0)) / count
            group["excerpt_count"] = count

        # Add excerpt (limited)
        if len(doc_groups[doc_id]["excerpts"]) < top_k_per_doc:
            _add_excerpt_with_context(doc_groups[doc_id], chunk)

    # Convert to list
    results = list(doc_groups.values())
    results.sort(key=lambda r: r["max_score"], reverse=True)

    # Clean up intermediate fields
    for r in results:
        r.pop("excerpt_count", None)

    return results


def _add_excerpt_with_context(group: Dict[str, Any], chunk: Dict[str, Any]) -> None:
    """Add a chunk as an excerpt with surrounding context."""
    text = chunk.get("text", "")
    score = chunk.get("score", 0)

    # Truncate very long excerpts
    max_excerpt_len = 500
    if len(text) > max_excerpt_len:
        text = text[:max_excerpt_len] + "..."

    group["excerpts"].append({
        "text": text,
        "score": score,
        "chunk_id": chunk.get("chunk_id", ""),
    })
