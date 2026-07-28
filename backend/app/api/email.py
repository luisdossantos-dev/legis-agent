"""
Email API endpoints.
POST /api/email/draft — Generate a professional email draft (optionally from a document).
GET  /api/email/models — List available models for email drafting.
GET  /api/email/templates — List available email templates.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.agents.email_drafter import draft_email
from app.core.auth import AuthContext
from app.core.email_llm import get_available_models
from app.core.gdpr import AuditAction, log_interaction
from app.models.auth import Role as UserRole
from app.core.rate_limit import limiter
from app.models.schemas import EmailDraftRequest, EmailDraftResponse
from app.rag.email_templates import get_seed_templates
from app.services.document_service import get_document as _get_doc, DocumentServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/draft", response_model=EmailDraftResponse)
@limiter.limit("10/minute")
async def create_email_draft(request: Request, req: EmailDraftRequest):
    """
    Generate a professional email draft for a notarial communication.

    If ``document_id`` is provided, the document text is used as RAG context
    to extract real names, dates, amounts, and details for the email.
    """
    if not req.fields:
        raise HTTPException(status_code=400, detail="At least one field is required.")

    # Optional: load document context
    document_context = None
    if req.document_id:
        try:
            doc = _get_doc(req.document_id)
            text = doc.get("text", "")
            if text:
                # Take first 8000 chars to stay within token budget
                document_context = text[:8000]
                logger.info(
                    "Email draft with document context: %s (%d chars)",
                    doc.get("filename"), len(document_context),
                )
        except DocumentServiceError as e:
            logger.warning("Document not found for email draft: %s", e.detail)
            # Non-fatal: email will be generated without document context

    draft, debug = await draft_email(req, document_context=document_context)

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.DRAFT,
        resource_type="email",
        resource_id=req.document_id or "",
        details=f"Email draft: template={draft.template_used or 'none'}, model={draft.model_used}",
        metadata={"tokens_used": draft.tokens_used, "model_used": draft.model_used},
    )

    logger.info(
        "Email drafted: template=%s, model=%s, tokens=%d, doc_ctx=%s",
        draft.template_used, draft.model_used, draft.tokens_used,
        bool(document_context),
    )

    return draft


@router.get("/models")
async def list_email_models():
    """Return the list of LLM models available for email drafting."""
    return {"models": get_available_models()}


@router.get("/templates")
async def list_email_templates():
    """Return the list of available email templates."""
    templates = get_seed_templates()
    return {
        "templates": [
            {
                "act_type": t.act_type,
                "name": t.name,
                "description": t.description,
                "language": t.language,
                "required_fields": t.required_fields,
            }
            for t in templates
        ]
    }
