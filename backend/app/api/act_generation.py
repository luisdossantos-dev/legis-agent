"""
Notarial act generation API.
POST /api/acts/generate — Generate a notarial act (5-node LangGraph pipeline).
GET  /api/acts/types — List supported act types.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.act_generator import generate_act
from app.models.act_generation import GenerateActRequest, GenerationResult
from app.models.act_schemas import ACT_SCHEMA_REGISTRY, ACT_TYPE_LABELS
from app.core.auth import AuthContext
from app.core.gdpr import AuditAction, log_interaction
from app.models.auth import Role as UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=GenerationResult)
async def generate_notarial_act(req: GenerateActRequest):
    """
    Generate a notarial act using a 5-node LangGraph pipeline:

    1. RETRIEVE  — Find similar acts from vector store
    2. STRUCTURE — LLM generates section structure
    3. DRAFT     — LLM drafts each section (formal legal tone)
    4. VALIDATE  — Pydantic AI validates required fields
         ↳ If errors → back to DRAFT with feedback (max 3 cycles)
         ↳ If OK → continue
    5. FORMAT    — Assemble .docx with notarial formatting
    """
    if req.act_type not in ACT_SCHEMA_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown act type '{req.act_type}'. Supported: {', '.join(ACT_SCHEMA_REGISTRY.keys())}",
        )

    logger.info("Generating act: type=%s, lang=%s", req.act_type, req.language)
    result = await generate_act(req)

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.DRAFT,
        resource_type="act",
        resource_id="",
        details=f"Act generated: type={req.act_type}, lang={req.language}",
        metadata={"act_type": req.act_type, "language": req.language},
    )

    return result


@router.get("/types")
async def list_act_types():
    """List supported notarial act types with their schemas."""
    return {
        "types": [
            {
                "id": act_type,
                "label": ACT_TYPE_LABELS.get(act_type, act_type),
                "required_fields": [
                    {"name": name, "type": str(field.annotation), "required": field.is_required()}
                    for name, field in schema_cls.model_fields.items()
                ],
            }
            for act_type, schema_cls in ACT_SCHEMA_REGISTRY.items()
        ]
    }
