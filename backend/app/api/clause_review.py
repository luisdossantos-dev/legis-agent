"""
Clause review API endpoints.
POST /api/clauses/review — Review a notarial clause.
GET  /api/clauses/checklist — Get risk checklist for a clause type.
GET  /api/clauses/types — List available clause types.
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.agents.clause_reviewer import review_clause
from app.rag.clause_checklist import get_all_checklist_types, get_checklist_for, CLAUSE_TYPE_LABELS
from app.core.rate_limit import limiter
from app.core.auth import AuthContext
from app.core.gdpr import AuditAction, log_interaction
from app.models.auth import Role as UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


class ClauseReviewRequest(BaseModel):
    clause_text: str
    clause_type: str = "autre"
    context: str = ""


@router.post("/review")
@limiter.limit("15/minute")
async def review_notarial_clause(request: Request, req: ClauseReviewRequest):
    """
    Review a notarial clause using the LangGraph pipeline.

    The pipeline:
    1. Analyze clause against checklist, risk patterns, and legal references
    2. Assess overall risk level (green/yellow/red)
    3. Generate structured report with issues, missing elements, recommendations

    Clause types: prix, delai, condition_suspensive, renonciation, garantie, penalite, autre
    """
    if not req.clause_text.strip():
        raise HTTPException(status_code=400, detail="Clause text is required.")

    if req.clause_type not in CLAUSE_TYPE_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown clause type '{req.clause_type}'. "
                   f"Available: {', '.join(CLAUSE_TYPE_LABELS.keys())}",
        )

    logger.info("Reviewing clause: type=%s, len=%d chars", req.clause_type, len(req.clause_text))
    result = await review_clause(
        clause_text=req.clause_text,
        clause_type=req.clause_type,
        context=req.context,
    )

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.ANALYSIS,
        resource_type="clause",
        resource_id="",
        details=f"Clause review: type={req.clause_type}, len={len(req.clause_text)} chars",
        metadata={"clause_type": req.clause_type, "risk_level": result.get("risk_level")},
    )

    return result


@router.get("/checklist/{clause_type}")
async def get_risk_checklist(clause_type: str):
    """Get the risk checklist for a specific clause type."""
    if clause_type not in CLAUSE_TYPE_LABELS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown clause type '{clause_type}'. "
                   f"Available: {', '.join(CLAUSE_TYPE_LABELS.keys())}",
        )

    checklist = get_checklist_for(clause_type)
    return {
        "clause_type": clause_type,
        "label": CLAUSE_TYPE_LABELS.get(clause_type, clause_type),
        "checklist": checklist,
    }


@router.get("/types")
async def list_clause_types():
    """List all available clause types with their metadata."""
    types = get_all_checklist_types()
    return {
        "types": types,
        "labels": CLAUSE_TYPE_LABELS,
    }
