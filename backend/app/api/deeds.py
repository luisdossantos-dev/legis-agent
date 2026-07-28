"""
Deed drafting API.
POST /api/deeds/draft-clause — Draft a notarial clause (DSPy + LlamaIndex + LiteLLM).
POST /api/deeds/optimize   — Run DSPy prompt optimization.
POST /api/deeds/index      — Index a deed for future retrieval.
GET  /api/deeds/status     — Show deed retriever and DSPy status.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.deed_drafter import draft_deed_clause, index_deed_text
from app.rag.deed_dspy import optimize_prompt
from app.rag.deed_llamaindex import deed_retriever
from app.core.auth import AuthContext
from app.core.gdpr import AuditAction, log_interaction
from app.models.auth import Role as UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


class DraftClauseRequest(BaseModel):
    type_clause: str
    contexte: str
    use_optimized: bool = True
    use_retriever: bool = True


class OptimizeRequest(BaseModel):
    examples: list[dict] | None = None
    num_fewshot: int = 5


class IndexDeedRequest(BaseModel):
    text: str
    metadata: dict | None = None


@router.post("/draft-clause")
async def draft_clause_endpoint(req: DraftClauseRequest):
    """
    Draft a notarial clause using DSPy (optimized prompt) + LlamaIndex
    (previous similar clauses) + LiteLLM (fallback).

    Clause types: prix, delai, condition_suspensive, renonciation, garantie, autre
    """
    if not req.contexte.strip():
        raise HTTPException(status_code=400, detail="Context is required.")

    result = await draft_deed_clause(
        type_clause=req.type_clause,
        contexte=req.contexte,
        use_optimized=req.use_optimized,
        use_retriever=req.use_retriever,
    )

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.DRAFT,
        resource_type="deed",
        resource_id="",
        details=f"Clause drafted: type={req.type_clause}, len={len(req.contexte)} chars",
        metadata={"type_clause": req.type_clause},
    )

    return result


@router.post("/optimize")
async def optimize_endpoint(req: OptimizeRequest):
    """
    Run DSPy prompt optimization with BootstrapFewShot.

    Provide optional training examples to customize the optimization.
    Without examples, uses 5 default legal clause templates.
    """
    result = await optimize_prompt(
        train_examples=req.examples,
        num_fewshot=req.num_fewshot,
    )

    if result.get("status") == "error":
        logger.error("Prompt optimization failed: %s", result.get("message", "unknown"))
        raise HTTPException(status_code=500, detail="Prompt optimization failed. Please try again.")

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.UPDATE,
        resource_type="prompt",
        resource_id="",
        details=f"DSPy optimization run: num_fewshot={req.num_fewshot}",
        metadata={"num_fewshot": req.num_fewshot},
    )

    return result


@router.post("/index")
async def index_deed(req: IndexDeedRequest):
    """
    Index a deed or clause in LlamaIndex for future retrieval.

    Once indexed, the retriever will find this deed when drafting
    similar clauses in the future.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")

    result = await index_deed_text(req.text, req.metadata)

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.CREATE,
        resource_type="deed_index",
        resource_id="",
        details=f"Deed indexed: {len(req.text)} chars",
        metadata={"char_count": len(req.text)},
    )

    return result


@router.get("/status")
async def deed_status():
    """Show the status of the deed drafting system."""
    return {
        "llamaindex_available": deed_retriever.is_available,
        "indexed_deeds": deed_retriever.doc_count,
        "dspy_available": True,  # Will be checked at import time
    }
