"""
Deadline / timeline extraction API.
POST /api/timeline/extract — Extract deadlines from text.
POST /api/timeline/extract-email — Extract deadlines from a classified email.
GET  /api/timeline/formats — Show supported date formats.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag.deadline_parser import extract_deadlines

logger = logging.getLogger(__name__)

router = APIRouter()


class ExtractRequest(BaseModel):
    text: str
    use_llm: bool = True


class ExtractEmailRequest(BaseModel):
    subject: str = ""
    body: str
    category: str = ""


@router.post("/extract")
async def extract_timeline(req: ExtractRequest):
    """
    Extract all deadlines and dates from a text.

    Supports:
    - Explicit dates: "le 31 décembre 2025", "15/01/2026"
    - Relative dates: "sous 30 jours", "dans un délai de 15 jours"
    - Business days: "15 jours ouvrés"
    - LLM fallback for complex cases
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")

    result = await extract_deadlines(req.text, use_llm=req.use_llm)
    return result


@router.post("/extract-email")
async def extract_email_timeline(req: ExtractEmailRequest):
    """
    Extract deadlines from an email (subject + body).
    """
    combined = f"Sujet: {req.subject}\n\n{req.body}" if req.subject else req.body
    result = await extract_deadlines(combined, use_llm=True)
    return result


@router.get("/formats")
async def list_formats():
    """Show supported date formats with examples."""
    return {
        "explicit_formats": [
            {"pattern": "le 15/01/2026", "description": "Numeric date (DD/MM/YYYY)"},
            {"pattern": "au 31 décembre 2025", "description": "French text date"},
            {"pattern": "le 1er mars 2025", "description": "French ordinal date"},
            {"pattern": "avant le 15 mars", "description": "Deadline with 'avant le'"},
            {"pattern": "2026-01-15", "description": "ISO format (YYYY-MM-DD)"},
        ],
        "relative_formats": [
            {"pattern": "sous 30 jours", "description": "N days from now"},
            {"pattern": "dans un délai de 15 jours", "description": "Within N days"},
            {"pattern": "sous 15 jours ouvrés", "description": "N business days"},
            {"pattern": "pour le 15 du mois prochain", "description": "Next month"},
            {"pattern": "sous quinzaine", "description": "15 days (fortnight)"},
            {"pattern": "dans la semaine", "description": "Within a week"},
        ],
    }
