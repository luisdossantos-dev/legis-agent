"""
Document API endpoints.
POST /api/documents/upload — Upload and process documents.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile

from app.core.auth import AuthContext, get_optional_current_user
from app.core.gdpr import AuditAction, log_interaction
from app.models.auth import Role as UserRole
from app.core.rate_limit import limiter
from app.models.schemas import DocumentUploadResponse
from app.services.document_service import (
    DocumentServiceError,
    get_document as _get_doc,
    index_document_background,
    list_documents as _list_docs,
    process_upload as _process_upload,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Re-export for backward compatibility with agents.py and gdpr.py
from app.services.document_service import _documents_store  # noqa: E402, F401


@router.post("/upload", response_model=DocumentUploadResponse)
@limiter.limit("5/minute")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: Optional[AuthContext] = Depends(get_optional_current_user),
):
    """Upload a legal document (PDF, DOCX, TXT).

    Delegates validation and processing to the service layer.
    Vector indexing runs as a background task after the response is sent.
    """
    auth_user = user or AuthContext(
        user_id="anonymous", username="anonymous",
        role=UserRole.STAGIAIRE, office="", display_name="Anonymous",
    )

    # Read file bytes
    try:
        content = await file.read()
    except (OSError, ConnectionError) as e:
        logger.warning("File read failed: %s", e)
        raise HTTPException(status_code=500, detail="Error reading uploaded file.")

    # Delegate to service layer
    try:
        response, temp_path, chunk_texts, ext = await _process_upload(
            filename=file.filename or "",
            content=content,
            content_length=_parse_content_length(request),
            user=auth_user,
        )
    except DocumentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    # Audit log
    log_interaction(
        auth_user,
        AuditAction.CREATE,
        resource_type="document",
        resource_id=response.id,
        details=f"Uploaded '{response.filename}' ({response.pages} pages)",
        ip_address=request.client.host if request.client else "",
        metadata={"pages": response.pages, "chunks": response.chunks},
    )

    # Offload vector indexing to a background task
    background_tasks.add_task(
        index_document_background,
        doc_id=response.id,
        filename=response.filename,
        chunk_texts=chunk_texts,
        ext=ext,
        temp_path=temp_path,
    )

    return response


@router.get("/")
async def list_documents(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of documents to return"),
    offset: int = Query(default=0, ge=0, le=10000, description="Number of documents to skip"),
):
    """List uploaded documents with pagination."""
    return _list_docs(limit=limit, offset=offset)


@router.get("/{document_id}")
async def get_document(document_id: str):
    """Get document metadata by ID."""
    try:
        return _get_doc(document_id)
    except DocumentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


def _parse_content_length(request: Request) -> Optional[int]:
    """Extract Content-Length header as an int, or None if absent/malformed."""
    raw = request.headers.get("content-length")
    if raw:
        try:
            return int(raw)
        except (ValueError, TypeError):
            pass
    return None
