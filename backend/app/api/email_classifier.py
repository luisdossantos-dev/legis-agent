"""
Email classification API endpoints.
POST /api/email/classify — Classify an incoming email.
GET  /api/email/classify/categories — List available categories.
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import EMAIL_CATEGORIES, EmailClassificationRequest, EmailClassificationResponse
from app.rag.email_classifier import classify_email
from app.core.rate_limit import limiter
from app.core.auth import AuthContext
from app.core.gdpr import AuditAction, log_interaction
from app.models.auth import Role as UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/classify", response_model=EmailClassificationResponse)
@limiter.limit("15/minute")
async def classify_incoming_email(request: Request, req: EmailClassificationRequest):
    """
    Classify an incoming email using hybrid embedding + LLM approach.

    The email is first classified by cosine similarity against 6 category
    centroids. If confidence >= 0.7, the result is returned immediately.
    Otherwise, the active LLM is called for assisted classification.
    """
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="Email body is required.")

    start = time.time()
    result = await classify_email(
        subject=req.subject,
        body=req.body,
        from_address=req.from_address,
        to_address=req.to_address,
    )
    elapsed = (time.time() - start) * 1000

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.READ,
        resource_type="email",
        resource_id="",
        details=f"Email classified: {result.category} (method={result.method}, confidence={result.confidence:.2f})",
        metadata={"category": result.category, "method": result.method, "confidence": result.confidence, "processing_time_ms": elapsed},
    )

    logger.info(
        "Email classified: category=%s, method=%s, confidence=%.4f, time=%.0fms",
        result.category, result.method, result.confidence, elapsed,
    )

    return result


@router.get("/classify/categories")
async def list_categories():
    """Return the list of available email categories."""
    return {
        "categories": EMAIL_CATEGORIES,
        "descriptions": {
            "cliente_nuevo": "New client inquiry, first contact, request for info",
            "seguimiento_escritura": "Deed of sale follow-up, property transfer status",
            "consulta_hipoteca": "Mortgage consultation, loan inquiry, financing",
            "notificacion_banco": "Bank notification, payment confirmation",
            "spam": "Unsolicited email, phishing, junk mail",
            "interno": "Internal office communication, staff memo",
        },
    }
