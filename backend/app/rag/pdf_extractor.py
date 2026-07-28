"""
PDF data extraction orchestrator.

Dual pipeline:
  [PDF]
   ├── Scanned (image) → OCR via pdf2image + pytesseract
   └── Digital (text)  → PyPDF2 direct extraction
        ↓
  [Semantic chunking by legal sections]
        ↓
  [LiteLLM extraction with Pydantic validation]

For sensitive documents, routes to local vLLM if available.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.llm import llm_complete
from app.core.langfuse import observe
from app.rag.pdf_chunker import chunk_by_sections
from app.rag.pdf_ocr import is_scanned_pdf, ocr_pdf
from app.rag.pdf_schemas import get_all_schema_info, get_schema, SCHEMA_LABELS

logger = logging.getLogger(__name__)

# ── vLLM self-hosted detection ─────────────────────────────────

_VLLM_BASE = os.environ.get("VLLM_API_BASE", "")


def _vllm_available() -> bool:
    """Check if a local vLLM instance is configured."""
    return bool(_VLLM_BASE)


def _is_sensitive(text: str) -> bool:
    """Heuristic: detect if text contains sensitive personal data."""
    sensitive_patterns = [
        r"\b\d{13}\b",           # French Social Security (13 digits)
        r"\b\d{15}\b",           # SIRET
        r"(?:né|née)\s+le\s+\d{2}/\d{2}/\d{4}",  # Birth date
        r"(?:pièce|passeport|CNI|carte\s+d'identité)\s+n[°o]?\s*\d+",
        r"\b(?:IBAN|RIB|BIC)\b",
        r"\b\d{16}\b",           # Credit card number
    ]
    import re
    for pattern in sensitive_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ── Extraction constants ───────────────────────────────────────
# Maximum characters to pass to LLM extraction prompt.
# Longer texts are truncated to stay within the model's context window.
_MAX_EXTRACTION_TEXT_LENGTH = 30000
# Token budget for the LLM extraction call (output can be large).
_MAX_EXTRACTION_TOKENS = 8192

# ── Extraction prompts ────────────────────────────────────────

_EXTRACTION_PROMPT = """Extract structured data from this French notarial document.
Output ONLY valid JSON matching this schema:
{schema_json}

Document type: {doc_type}
Document text:

{document_text}

Output ONLY the JSON. No explanation, no reasoning."""


# ── Main extraction function ──────────────────────────────────


@observe(capture_input=True, capture_output=True)
async def extract_pdf_data(
    file_path: str,
    doc_type: str = "auto",
    lang: str = "fra+eng",
) -> Dict[str, Any]:
    """
    Extract structured data from a PDF.
    Auto-detects scanned vs digital, routes appropriately.

    Args:
        file_path: Path to the PDF file
        doc_type: Document type hint (vente, pouvoir, etc.) or "auto"
        lang: OCR language code

    Returns:
        Dict with extracted data, metadata, and processing info
    """
    start_time = time.time()
    result: Dict[str, Any] = {
        "filename": Path(file_path).name,
        "status": "processing",
        "doc_type": doc_type,
        "is_scanned": False,
        "text_length": 0,
        "chunks": 0,
        "extraction_method": "",
        "sensitive": False,
        "vllm_used": False,
        "data": {},
        "processing_time_ms": 0,
        "errors": [],
    }

    try:
        # Step 1: Detect scanned vs digital
        result["is_scanned"] = is_scanned_pdf(file_path)

        # Step 2: Extract text
        text = ""
        if result["is_scanned"]:
            logger.info("📄 Scanned PDF detected, routing to OCR")
            result["extraction_method"] = "ocr"
            ocr_text = ocr_pdf(file_path, lang=lang)
            if ocr_text:
                text = ocr_text
            else:
                # OCR not available, try PyPDF2 as fallback
                logger.warning("OCR unavailable, falling back to PyPDF2")
                text = _extract_pypdf(file_path)
                result["extraction_method"] = "pypdf2_fallback"
        else:
            logger.info("📄 Digital PDF detected, using PyPDF2")
            result["extraction_method"] = "pypdf2"
            text = _extract_pypdf(file_path)

        if not text.strip():
            raise ValueError("No text could be extracted from the PDF")

        result["text_length"] = len(text)

        # Step 3: Check sensitivity
        result["sensitive"] = _is_sensitive(text)

        # Step 4: Semantic chunking
        chunks = chunk_by_sections(text)
        result["chunks"] = len(chunks)

        # Step 5: Auto-detect document type if needed
        if doc_type == "auto":
            doc_type = await _detect_doc_type(text)
            result["doc_type"] = doc_type

        # Step 6: LLM extraction
        schema_cls = get_schema(doc_type)

        # Route: sensitive + vLLM available → local
        use_vllm = result["sensitive"] and _vllm_available()
        result["vllm_used"] = use_vllm

        extracted = await _llm_extract(text, doc_type, schema_cls, use_vllm)
        result["data"] = extracted

        # Step 7: Validate with Pydantic
        try:
            validated = schema_cls(**extracted)
            result["data"] = validated.model_dump()
            result["validation"] = "passed"
        except Exception as ve:
            logger.warning("Pydantic validation error: %s", str(ve))
            result["validation"] = f"partial: {str(ve)[:200]}"
            # Return the raw extraction even if validation fails

        result["status"] = "completed"

    except Exception as e:
        logger.error("❌ PDF extraction error: %s", str(e))
        result["status"] = "error"
        result["errors"].append(str(e))

    elapsed = (time.time() - start_time) * 1000
    result["processing_time_ms"] = round(elapsed, 1)

    logger.info(
        "✅ PDF extraction: %s -> %s (%d chars, %d chunks, %.1fms)",
        result["filename"],
        result["status"],
        result["text_length"],
        result["chunks"],
        elapsed,
    )
    return result


# ── Helper functions ──────────────────────────────────────────


def _extract_pypdf(file_path: str) -> str:
    """Extract text from PDF using PyPDF2."""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    text_parts = []
    for page_num, page in enumerate(reader.pages, 1):
        page_text = page.extract_text()
        if page_text.strip():
            text_parts.append(f"[Page {page_num}]\n{page_text}")

    return "\n\n".join(text_parts)


async def _detect_doc_type(text: str) -> str:
    """Use LLM to detect the document type from the text."""
    prompt = """Detect the type of this French notarial document. Reply with ONLY one word: vente, pouvoir, testament, contrat, acte_societe, or autre.

Document text:
{text}"""

    messages = [
        {"role": "system", "content": "You are a legal document classifier. Output only the type name."},
        {"role": "user", "content": prompt.format(text=text[:_MAX_EXTRACTION_TEXT_LENGTH])},
    ]

    response = await llm_complete(messages, max_tokens=_MAX_EXTRACTION_TOKENS, temperature=0.0)
    response = response.strip().lower()

    valid_types = {"vente", "pouvoir", "testament", "contrat", "acte_societe", "autre"}
    for t in valid_types:
        if t in response:
            return t
    return "autre"


async def _llm_extract(
    text: str,
    doc_type: str,
    schema_cls: Any,
    use_vllm: bool,
) -> Dict[str, Any]:
    """Use LLM to extract structured data from document text."""
    # Get a simplified schema representation
    schema_json = json.dumps(schema_cls.model_json_schema(), indent=2, ensure_ascii=False)

    # Truncate text to fit context window
    document_text = text[:_MAX_EXTRACTION_TEXT_LENGTH]

    messages = [
        {"role": "system", "content": _EXTRACTION_PROMPT.format(
            schema_json=schema_json,
            doc_type=SCHEMA_LABELS.get(doc_type, doc_type),
            document_text=document_text,
        )},
        {"role": "user", "content": f"Extract data from this {doc_type} document."},
    ]

    # Use larger max_tokens for extraction (output can be large)
    response = await llm_complete(messages, max_tokens=_MAX_EXTRACTION_TOKENS, temperature=0.0)

    # Parse JSON from response
    extracted = _extract_json(response)
    if extracted is None:
        logger.warning("Failed to parse LLM extraction JSON, trying fallback")
        # Try to find any JSON object
        stack = []
        for i, ch in enumerate(response):
            if ch == '{':
                stack.append(i)
            elif ch == '}':
                if stack:
                    start = stack.pop()
                    if not stack:
                        try:
                            extracted = json.loads(response[start:i+1])
                            break
                        except json.JSONDecodeError:
                            continue

    if extracted is None:
        logger.error("Could not extract any JSON from LLM response")
        return {"_error": "LLM response could not be parsed", "_raw": response[:500]}

    return extracted


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first complete JSON object."""
    stack = []
    for i, ch in enumerate(text):
        if ch == '{':
            stack.append(i)
        elif ch == '}':
            if stack:
                start = stack.pop()
                if not stack:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        return None
    return None
