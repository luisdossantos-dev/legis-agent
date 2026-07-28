"""
PDF data extraction API endpoints.
POST /api/pdf/extract — Upload a PDF and extract structured data.
GET  /api/pdf/schemas — List available extraction schemas.
GET  /api/pdf/status  — Check PDF extraction system status.
"""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.rag.pdf_extractor import extract_pdf_data
from app.rag.pdf_schemas import get_all_schema_info, SCHEMA_LABELS

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf"}


@router.post("/extract")
async def extract_pdf(
    file: UploadFile = File(...),
    doc_type: str = "auto",
    lang: str = "fra+eng",
):
    """
    Upload a PDF and extract structured data from it.

    The pipeline:
    1. Auto-detect scanned vs digital PDF
    2. Extract text (OCR for scanned, PyPDF2 for digital)
    3. Semantic chunking by legal sections
    4. LLM-based extraction with Pydantic validation
    5. Sensitive data routing to local vLLM if available

    Args:
        file: The PDF file to process
        doc_type: Document type hint (vente, pouvoir, etc.) or "auto"
        lang: OCR language code (default: fra+eng)
    """
    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Only PDF files are supported.",
        )

    # Validate doc_type
    if doc_type != "auto" and doc_type not in SCHEMA_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown document type '{doc_type}'. "
                   f"Available: auto, {', '.join(SCHEMA_LABELS.keys())}",
        )

    # Validat lang
    if not lang.strip():
        lang = "fra+eng"

    # Save uploaded file to temp location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(
            "PDF extraction request: file=%s, type=%s, size=%d bytes",
            file.filename, doc_type, len(content),
        )

        # Run extraction
        result = await extract_pdf_data(
            file_path=tmp_path,
            doc_type=doc_type,
            lang=lang,
        )

        # Add filename
        result["filename"] = file.filename

        return result

    except (OSError, ConnectionError, ValueError) as e:
        logger.error("PDF extraction endpoint error: %s", e)
        raise HTTPException(status_code=500, detail="PDF extraction failed. The file may be corrupted.")

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.get("/schemas")
async def list_extraction_schemas():
    """List all available extraction schemas with their fields."""
    schemas = get_all_schema_info()
    return {
        "schemas": schemas,
        "labels": SCHEMA_LABELS,
    }


@router.get("/status")
async def pdf_extraction_status():
    """Check the status of PDF extraction capabilities."""
    status = {
        "pypdf2_available": True,  # Always True (bundled dep)
        "ocr_available": False,
        "vllm_available": False,
        "vllm_base": "",
    }

    # Check OCR availability
    try:
        import pdf2image
        status["ocr_available"] = True
    except ImportError:
        pass

    try:
        import pytesseract
        # Double-check: pytesseract also needs the system binary
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            status["ocr_available"] = False
    except ImportError:
        status["ocr_available"] = False

    # Check vLLM
    vllm_base = os.environ.get("VLLM_API_BASE", "")
    if vllm_base:
        status["vllm_available"] = True
        status["vllm_base"] = vllm_base

    return status
