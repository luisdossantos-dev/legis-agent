"""
Document clustering engine for automatic case file assembly.

Uses embedding similarity to group related documents into case files.
Works with the existing EmbeddingsProvider and VectorStore.

Thresholds:
  - >0.75 cosine similarity → cluster (group together)
  - >0.80 cosine similarity → auto-assign to existing case
  - <0.50 → definitely new case
"""

import logging
import statistics
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.core.langfuse import observe
from app.rag.embeddings import embeddings_provider

logger = logging.getLogger(__name__)

# ── Thresholds ─────────────────────────────────────────────────

CLUSTER_THRESHOLD = 0.75    # minimum similarity to be in same cluster
ASSIGN_THRESHOLD = 0.80     # minimum similarity to auto-assign
NEW_CASE_THRESHOLD = 0.50   # below this → definitely new case
RE_CLUSTER_INTERVAL = 10    # re-cluster after this many new documents


# ── Case store (in-memory) ─────────────────────────────────────

class CaseStore:
    """In-memory store for case files.

    In production, this would be a database. Uses the same pattern
    as the document store in api/documents.py.
    """

    def __init__(self):
        self._cases: Dict[str, Any] = {}
        self._doc_to_case: Dict[str, str] = {}  # document_id → case_id
        self._auto_assign_count = 0
        self._manual_count = 0
        self._total_processed = 0

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self._cases.get(case_id)

    def list_cases(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cases = list(self._cases.values())
        if status:
            cases = [c for c in cases if c.get("status") == status]
        return sorted(cases, key=lambda c: c.get("updated_at", ""), reverse=True)

    def create_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        case_id = str(uuid.uuid4())
        case_data["id"] = case_id
        case_data["created_at"] = datetime.now(timezone.utc).isoformat()
        case_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        case_data["document_count"] = 0
        case_data["documents"] = []
        case_data["status"] = "open"
        self._cases[case_id] = case_data
        return case_data

    def add_document_to_case(self, case_id: str, doc_data: Dict[str, Any], category: str = "annexe") -> Optional[Dict[str, Any]]:
        case = self._cases.get(case_id)
        if not case:
            return None

        doc_data["category"] = category
        doc_data["added_at"] = datetime.now(timezone.utc).isoformat()
        case["documents"].append(doc_data)
        case["document_count"] = len(case["documents"])
        case["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Update centroid
        self._recompute_centroid(case_id)

        # Track assignment
        self._doc_to_case[doc_data["id"]] = case_id
        self._total_processed += 1

        return case

    def remove_document(self, case_id: str, document_id: str) -> bool:
        case = self._cases.get(case_id)
        if not case:
            return False
        case["documents"] = [d for d in case["documents"] if d.get("id") != document_id]
        case["document_count"] = len(case["documents"])
        case["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._recompute_centroid(case_id)
        self._doc_to_case.pop(document_id, None)
        return True

    def merge_cases(self, target_id: str, source_id: str) -> Optional[Dict[str, Any]]:
        """Merge source case into target case."""
        target = self._cases.get(target_id)
        source = self._cases.get(source_id)
        if not target or not source:
            return None

        # Move all documents from source to target
        for doc in source.get("documents", []):
            doc["category"] = "annexe"
            target["documents"].append(doc)
            self._doc_to_case[doc["id"]] = target_id

        target["document_count"] = len(target["documents"])
        target["updated_at"] = datetime.now(timezone.utc).isoformat()
        target["parties"] = list(set(target.get("parties", []) + source.get("parties", [])))

        # Recompute centroid
        self._recompute_centroid(target_id)

        # Remove source
        self._cases.pop(source_id, None)
        self._manual_count += 1

        return target

    def rename_case(self, case_id: str, name: str) -> bool:
        case = self._cases.get(case_id)
        if not case:
            return False
        case["name"] = name
        case["updated_at"] = datetime.now(timezone.utc).isoformat()
        return True

    def get_document_case(self, document_id: str) -> Optional[str]:
        return self._doc_to_case.get(document_id)

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._cases)
        open_cases = sum(1 for c in self._cases.values() if c.get("status") == "open")
        closed_cases = sum(1 for c in self._cases.values() if c.get("status") == "closed")
        total_docs = sum(c.get("document_count", 0) for c in self._cases.values())

        return {
            "total_cases": total,
            "total_documents": total_docs,
            "open_cases": open_cases,
            "closed_cases": closed_cases,
            "avg_docs_per_case": round(total_docs / total, 2) if total else 0.0,
            "auto_assigned_count": self._auto_assign_count,
            "manually_created_count": self._manual_count,
        }

    def _recompute_centroid(self, case_id: str) -> None:
        """Recompute the centroid (average embedding) of a case."""
        case = self._cases.get(case_id)
        if not case:
            return

        embeddings_list = [
            np.array(d["embedding"]) for d in case["documents"]
            if d.get("embedding") is not None
        ]
        if embeddings_list:
            centroid = np.mean(embeddings_list, axis=0).tolist()
            case["centroid"] = centroid
        else:
            case["centroid"] = None


# Singleton store
case_store = CaseStore()


# ── Clustering functions ────────────────────────────────────


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_best_case(embedding: List[float]) -> Tuple[Optional[str], float]:
    """
    Find the best matching case for a document embedding.

    Returns:
        Tuple of (case_id, similarity_score)
        If no match found, case_id is None.
    """
    best_case_id = None
    best_score = 0.0

    for case_id, case in case_store._cases.items():
        centroid = case.get("centroid")
        if centroid is None:
            continue

        score = cosine_similarity(embedding, centroid)

        if score > best_score and score >= CLUSTER_THRESHOLD:
            best_score = score
            best_case_id = case_id

    return best_case_id, best_score


def compute_cluster_scores(embedding: List[float]) -> Dict[str, float]:
    """
    Compute similarity scores against all existing case centroids.

    Returns:
        Dict of {case_id: similarity_score}
    """
    scores = {}
    for case_id, case in case_store._cases.items():
        centroid = case.get("centroid")
        if centroid is not None:
            scores[case_id] = cosine_similarity(embedding, centroid)
    return scores


# ── Main processing function ─────────────────────────────────


@observe(capture_input=True, capture_output=True)
async def process_document_for_cases(
    document_id: str,
    filename: str,
    text: str,
    chunks: List[str],
    embeddings: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    """
    Process a document into the case file system.

    Steps:
    1. Generate embedding for the document
    2. Compare against existing case centroids
    3. Auto-assign, cluster, or create new case
    4. Return assignment result

    Args:
        document_id: Unique document ID
        filename: Original filename
        text: Full document text
        chunks: Document chunks
        embeddings: Pre-computed embeddings (optional)

    Returns:
        Dict with assignment result
    """
    # Step 1: Get or compute document embedding
    doc_embedding = None
    if embeddings and len(embeddings) > 0:
        # Average chunk embeddings for document-level embedding
        doc_embedding = np.mean(embeddings, axis=0).tolist()
    else:
        # Generate embedding from full text
        # Truncate to ~2K tokens for embedding (most embedding models have
        # a ~512-8192 token limit, and longer texts don't produce better vectors).
        _EMBEDDING_TRUNCATE_CHARS = 8_000
        text_for_embedding = text[:_EMBEDDING_TRUNCATE_CHARS]
        emb_result = await embeddings_provider.embed_texts([text_for_embedding])
        if emb_result and len(emb_result) > 0:
            doc_embedding = emb_result[0]

    if doc_embedding is None:
        logger.warning("Could not generate embedding for doc %s", document_id)
        return {
            "document_id": document_id,
            "assigned_to": None,
            "action": "no_embedding",
            "case_name": "",
            "confidence": 0.0,
            "similarity_scores": {},
        }

    # Step 2: Find best matching case
    best_case_id, best_score = find_best_case(doc_embedding)
    similarity_scores = compute_cluster_scores(doc_embedding)

    # Step 3: Create document record
    doc_record = {
        "id": document_id,
        "filename": filename,
        "category": "annexe",  # will be re-categorized later
        "doc_type": "",
        "chunk_count": len(chunks),
        "text_length": len(text),
        "embedding": doc_embedding,
        "summary": text[:200],
    }

    # Step 4: Decide action
    if best_case_id and best_score >= ASSIGN_THRESHOLD:
        # Auto-assign to existing case with high confidence
        case = case_store.add_document_to_case(best_case_id, doc_record)
        case_store._auto_assign_count += 1
        logger.info(
            "📂 Auto-assigned doc %s to case %s (similarity=%.4f)",
            filename, case["name"], best_score,
        )
        return {
            "document_id": document_id,
            "assigned_to": best_case_id,
            "action": "assigned_existing",
            "case_name": case["name"],
            "confidence": best_score,
            "similarity_scores": similarity_scores,
        }

    elif best_case_id and best_score >= CLUSTER_THRESHOLD:
        # Similar enough to cluster, but not enough to auto-assign
        case = case_store.add_document_to_case(best_case_id, doc_record)
        logger.info(
            "📂 Clustered doc %s into case %s (similarity=%.4f)",
            filename, case["name"], best_score,
        )
        return {
            "document_id": document_id,
            "assigned_to": best_case_id,
            "action": "clustered",
            "case_name": case["name"],
            "confidence": best_score,
            "similarity_scores": similarity_scores,
        }

    else:
        # Create new case
        case_name = f"Case #{len(case_store._cases) + 1}"
        case_data = {
            "name": case_name,
            "parties": [],
            "property_ref": "",
            "notes": "",
            "confidence": best_score if best_case_id else 0.0,
        }
        new_case = case_store.create_case(case_data)
        case_store.add_document_to_case(new_case["id"], doc_record)
        case_store._manual_count += 1
        logger.info(
            "📂 Created new case %s for doc %s", new_case["name"], filename,
        )
        return {
            "document_id": document_id,
            "assigned_to": new_case["id"],
            "action": "new_case",
            "case_name": new_case["name"],
            "confidence": 0.0,
            "similarity_scores": similarity_scores,
        }
