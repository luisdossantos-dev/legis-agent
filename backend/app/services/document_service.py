"""
Document service layer — business logic for document upload, storage, and retrieval.

Separates the "what" (business rules) from the "how" (HTTP transport).
The API layer calls these functions and translates results into HTTP responses.
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.auth import AuthContext
from app.core.config import settings
from app.core.profiler import timed
from app.ingestion.parser import parser
from app.models.schemas import DocumentListResponse, DocumentSummary, DocumentUploadResponse
from app.rag.chunker import chunk_by_sections
from app.rag.retriever import vector_store

logger = logging.getLogger(__name__)

# ── In-memory document store (use a database in production) ─────
# Exported at module level so other modules (agents, gdpr) can query it.
_documents_store: dict = {}

# ── Validation constants ────────────────────────────────────────

_VALID_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_MAX_FILENAME_LENGTH = 255
_CHARS_PER_PAGE_ESTIMATE = 2500


# ── Domain exception ────────────────────────────────────────────


class DocumentServiceError(ValueError):
    """Raised when a document operation fails. Carries an HTTP-compatible status code."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ── Background indexing ─────────────────────────────────────────


@timed("app.services.document")
async def index_document_background(
    doc_id: str,
    filename: str,
    chunk_texts: list[str],
    ext: str,
    temp_path: Path,
) -> None:
    """Index document chunks in the vector store as a background task.

    Updates the document status to "indexed" on success, or "error" on failure.
    Cleans up the temp file on failure.
    """
    try:
        num_chunks = await vector_store.index_document(
            document_id=doc_id,
            chunks=chunk_texts,
            metadata={
                "filename": filename,
                "extension": ext,
                "uploaded_at": datetime.utcnow().isoformat(),
            },
        )
        if doc_id in _documents_store:
            _documents_store[doc_id]["status"] = "indexed"
            _documents_store[doc_id]["chunks"] = num_chunks
        logger.info(
            "Background indexing complete: %s (id=%s, %d chunks)",
            filename, doc_id, num_chunks,
        )
    except Exception as e:
        logger.error("Background indexing failed for %s: %s", doc_id, e)
        if doc_id in _documents_store:
            _documents_store[doc_id]["status"] = "error"
        try:
            await asyncio.to_thread(temp_path.unlink, missing_ok=True)
        except Exception:
            logger.debug("Failed to clean up temp file on indexing error: %s", temp_path)


# ── File helpers ────────────────────────────────────────────────


def _write_file(path: Path, content: bytes) -> None:
    """Write bytes to a file (runs in a thread pool via asyncio.to_thread)."""
    with open(path, "wb") as f:
        f.write(content)


# ── Upload pipeline ─────────────────────────────────────────────


async def process_upload(
    *,
    filename: str,
    content: bytes,
    content_length: Optional[int],
    user: AuthContext,
) -> tuple[DocumentUploadResponse, Path, list[str], str]:
    """Validate, save, parse, and chunk an uploaded document.

    Args:
        filename: Original filename from the upload.
        content: Raw file bytes.
        content_length: Value of the Content-Length header, if present.
        user: Authenticated user context.

    Returns:
        Tuple of (response, temp_path, chunk_texts, extension).

    Raises:
        DocumentServiceError: If any validation or processing step fails.
    """
    # ── Step 1: Validate filename length ──────────────────────────
    if not filename or len(filename) > _MAX_FILENAME_LENGTH:
        raise DocumentServiceError("Filename is missing or exceeds maximum length.")

    # ── Step 2: Validate extension ────────────────────────────────
    ext = Path(filename).suffix.lower()
    if ext not in parser.SUPPORTED_EXTENSIONS:
        raise DocumentServiceError(
            f"Unsupported format '{ext}'. Supported formats: PDF, DOCX, TXT.",
        )

    # ── Step 3: Preliminary size check via Content-Length header ──
    if content_length is not None and content_length > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise DocumentServiceError(
            f"File too large ({content_length // (1024 * 1024)} MB). "
            f"Maximum allowed size is {max_mb} MB.",
        )

    # ── Step 4: Size enforcement ─────────────────────────────────
    if len(content) > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        size_mb = len(content) // (1024 * 1024)
        raise DocumentServiceError(
            f"File too large ({size_mb} MB). Maximum allowed size is {max_mb} MB.",
        )

    if len(content) == 0:
        raise DocumentServiceError("Uploaded file is empty.")

    # ── Step 5: Validate MIME type via content signature ──────────
    if not parser.validate_file_signature(content, ext):
        raise DocumentServiceError(
            f"File content does not match extension '{ext}'. "
            f"The file appears to be a different format than its extension suggests.",
        )

    # ── Step 6: Save to disk ────────────────────────────────────
    doc_id = str(uuid.uuid4())
    upload_dir = Path(settings.UPLOAD_DIR)
    await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)

    temp_path = upload_dir / f"{doc_id}{ext}"
    try:
        await asyncio.to_thread(_write_file, temp_path, content)
    except OSError as e:
        logger.error("Failed to save uploaded file to disk: %s", e)
        raise DocumentServiceError("Error saving uploaded file.", status_code=500)

    # ── Step 7: Parse document ────────────────────────────────────
    try:
        text = await parser.parse(str(temp_path))
    except Exception as e:
        await asyncio.to_thread(temp_path.unlink, missing_ok=True)
        logger.warning("Document parsing failed: %s", str(e))
        raise DocumentServiceError(
            "Could not parse document content. "
            "The file may be corrupted or in an unsupported format.",
            status_code=422,
        )

    # ── Step 8: Chunk ─────────────────────────────────────────────
    chunks = chunk_by_sections(text)
    chunk_texts = [c[0] for c in chunks]
    logger.info("Document chunked: %d chunks", len(chunk_texts))

    # ── Step 9: Store metadata ───────────────────────────────────
    pages_estimate = len(text) // _CHARS_PER_PAGE_ESTIMATE
    _documents_store[doc_id] = {
        "id": doc_id,
        "filename": filename,
        "pages": max(1, pages_estimate),
        "chunks": len(chunk_texts),
        "status": "processing",
        "created_at": datetime.utcnow(),
        "text": text,
        "user_id": user.user_id if user and user.user_id != "open" else None,
        "uploaded_by": user.username if user and user.user_id != "open" else None,
    }

    logger.info("Document saved: %s (id=%s)", filename, doc_id)

    return (
        DocumentUploadResponse(
            id=doc_id,
            filename=filename,
            pages=max(1, pages_estimate),
            chunks=len(chunk_texts),
            status="processing",
            created_at=datetime.utcnow(),
        ),
        temp_path,
        chunk_texts,
        ext,
    )


# ── Query operations ────────────────────────────────────────────


def list_documents(limit: int = 100, offset: int = 0) -> DocumentListResponse:
    """Return a paginated list of uploaded documents."""
    all_docs = sorted(
        _documents_store.values(),
        key=lambda d: d.get("created_at", datetime.min),
        reverse=True,
    )
    total = len(all_docs)
    paginated = all_docs[offset : offset + limit]

    docs = [
        DocumentSummary(
            id=doc["id"],
            filename=doc["filename"],
            pages=doc["pages"],
            chunks=doc["chunks"],
            status=doc["status"],
            created_at=doc["created_at"],
        )
        for doc in paginated
    ]
    return DocumentListResponse(documents=docs, total=total)


def get_document(document_id: str) -> dict[str, Any]:
    """Return document metadata by ID, or raise DocumentServiceError."""
    if not _VALID_UUID_RE.match(document_id):
        raise DocumentServiceError("Invalid document ID format. Must be a valid UUID.", status_code=400)

    doc = _documents_store.get(document_id)
    if not doc:
        raise DocumentServiceError("Document not found", status_code=404)
    return doc
