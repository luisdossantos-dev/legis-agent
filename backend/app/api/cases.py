"""
Case file API endpoints.
POST /api/cases/process — Process a document into case files.
POST /api/cases/process-and-assemble — Process + assemble in one step.
GET  /api/cases — List all case files.
GET  /api/cases/{case_id} — Get case file detail.
POST /api/cases/rename — Rename a case file.
POST /api/cases/merge — Merge two case files.
POST /api/cases/{case_id}/categorize — Recategorize a document.
GET  /api/cases/stats — Case system statistics.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.case_assembler import assemble_case, process_and_assemble
from app.rag.case_clustering import case_store, process_document_for_cases
from app.rag.case_search import search_cases, search_in_case
from app.models.case_schemas import CATEGORY_ORDER, CaseFileSummary, CaseListResponse, CaseStats

logger = logging.getLogger(__name__)

router = APIRouter()


class ProcessRequest(BaseModel):
    document_id: str
    filename: str = ""
    text: str
    chunks: list[str] = []
    embeddings: Optional[list[list[float]]] = None


class RenameRequest(BaseModel):
    case_id: str
    name: str


class MergeRequest(BaseModel):
    target_case_id: str
    source_case_id: str


class CategorizeDocumentRequest(BaseModel):
    document_id: str
    category: str = "annexe"


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    top_k_per_doc: int = 2
    filters: Optional[dict[str, Any]] = None


# ── Endpoints ─────────────────────────────────────────────────


@router.post("/process")
async def process_document(req: ProcessRequest):
    """
    Process a document into the case file system.

    The document is embedded, compared against existing case centroids,
    and either:
    - Auto-assigned to an existing case (similarity > 0.80)
    - Clustered into an existing case (similarity > 0.75)
    - Placed in a new case file (similarity < 0.75)

    Returns the assignment result with which case it was assigned to.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Document text is required.")

    logger.info(
        "Processing doc for cases: id=%s, filename=%s, text=%d chars, chunks=%d",
        req.document_id, req.filename, len(req.text), len(req.chunks),
    )

    result = await process_document_for_cases(
        document_id=req.document_id,
        filename=req.filename or req.document_id,
        text=req.text,
        chunks=req.chunks,
        embeddings=req.embeddings,
    )

    return result


@router.post("/process-and-assemble")
async def process_and_assemble_endpoint(req: ProcessRequest):
    """
    Process a document AND run the full case assembly pipeline
    (categorize, name, organize) in one step.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Document text is required.")

    result = await process_and_assemble(
        document_id=req.document_id,
        filename=req.filename or req.document_id,
        text=req.text,
        chunks=req.chunks,
        embeddings=req.embeddings,
    )

    return result


@router.get("", response_model=CaseListResponse)
async def list_cases(status: Optional[str] = None):
    """List all case files, optionally filtered by status."""
    cases = case_store.list_cases(status=status)

    summaries = [
        CaseFileSummary(
            id=c["id"],
            name=c.get("name", "Unnamed Case"),
            status=c.get("status", "open"),
            document_count=c.get("document_count", 0),
            created_at=c.get("created_at", ""),
            updated_at=c.get("updated_at", ""),
            parties=c.get("parties", []),
            property_ref=c.get("property_ref", ""),
        )
        for c in cases
    ]

    return CaseListResponse(cases=summaries, total=len(summaries))


@router.get("/stats")
async def case_stats():
    """Get statistics about the case file system."""
    stats = case_store.get_stats()
    return stats


@router.post("/search")
async def search_all_cases(req: SearchRequest):
    """
    Search across all case files using semantic search.

    Natural language query finds relevant content even without
    exact keyword matches. Results grouped by document with excerpts.

    Optional filters: doc_type, doc_category, min_score
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")

    logger.info("🔍 Search all cases: query='%s'", req.query[:100])
    result = await search_cases(
        query=req.query,
        top_k=req.top_k,
        top_k_per_doc=req.top_k_per_doc,
        filters=req.filters,
    )
    return result


@router.post("/{case_id}/search")
async def search_case_documents(case_id: str, req: SearchRequest):
    """
    Search within a specific case file.
    Returns documents with relevant excerpts and similarity scores.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")

    logger.info("🔍 Search in case %s: query='%s'", case_id, req.query[:100])
    result = await search_in_case(
        case_id=case_id,
        query=req.query,
        top_k=req.top_k,
        top_k_per_doc=req.top_k_per_doc,
        filters=req.filters,
    )
    return result


@router.get("/{case_id}")
async def get_case(case_id: str):
    """Get the full detail of a case file, including organized documents."""
    case = case_store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    # Run assembly to get organized view
    assembly = await assemble_case(case_id)
    return assembly


@router.post("/rename")
async def rename_case(req: RenameRequest):
    """Rename a case file."""
    success = case_store.rename_case(req.case_id, req.name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Case '{req.case_id}' not found")

    return {"status": "ok", "case_id": req.case_id, "name": req.name}


@router.post("/merge")
async def merge_cases(req: MergeRequest):
    """Merge two case files into one."""
    result = case_store.merge_cases(req.target_case_id, req.source_case_id)
    if not result:
        raise HTTPException(
            status_code=400,
            detail=f"Could not merge: one or both cases not found",
        )

    return {
        "status": "ok",
        "target_case_id": req.target_case_id,
        "name": result.get("name"),
        "document_count": result.get("document_count", 0),
    }


@router.post("/{case_id}/categorize")
async def categorize_document(case_id: str, req: CategorizeDocumentRequest):
    """Recategorize a document within a case file."""
    case = case_store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    if req.category not in CATEGORY_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{req.category}'. Valid: {', '.join(CATEGORY_ORDER)}",
        )

    for doc in case.get("documents", []):
        if doc.get("id") == req.document_id:
            doc["category"] = req.category
            case["updated_at"] = __import__("datetime").datetime.utcnow().isoformat()
            return {"status": "ok", "document_id": req.document_id, "category": req.category}

    raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found in case")


@router.get("/stats")
async def case_stats():
    """Get statistics about the case file system."""
    stats = case_store.get_stats()
    return stats
