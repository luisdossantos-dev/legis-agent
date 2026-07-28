"""
OCR module for scanned PDFs.
Converts PDF pages to images and extracts text via OCR.

Optional dependencies:
  - pdf2image (poppler-utils required on system)
  - pytesseract (tesseract-ocr required on system)
  - Pillow (already installed)

Gracefully degrades when dependencies are missing.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def ocr_pdf(file_path: str, lang: str = "fra+eng") -> Optional[str]:
    """
    Extract text from a scanned PDF using OCR.

    Args:
        file_path: Path to the PDF file
        lang: Tesseract language codes (default: fra+eng for French + English)

    Returns:
        Extracted text, or None if OCR is not available
    """
    # Check if dependencies are available
    try:
        from pdf2image import convert_from_path
    except ImportError:
        logger.warning("pdf2image not installed. Install with: pip install pdf2image")
        logger.warning("System dependency: sudo apt-get install poppler-utils")
        return None

    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract not installed. Install with: pip install pytesseract")
        logger.warning("System dependency: sudo apt-get install tesseract-ocr tesseract-ocr-fra")
        return None

    try:
        logger.info("🖼️  OCR processing: %s (lang=%s)", Path(file_path).name, lang)

        # Convert PDF to images
        images = convert_from_path(
            file_path,
            dpi=300,  # Higher DPI = better OCR
            fmt="jpeg",
            thread_count=2,
        )

        logger.info("   -> Converted %d pages to images", len(images))

        # OCR each page
        text_parts = []
        for i, img in enumerate(images, 1):
            try:
                page_text = pytesseract.image_to_string(
                    img,
                    lang=lang,
                    config="--oem 3 --psm 6",  # LSTM engine, uniform block of text
                )
                if page_text.strip():
                    text_parts.append(f"[Page {i}]\n{page_text.strip()}")
            except Exception as e:
                logger.warning("   -> OCR failed on page %d: %s", i, str(e))
                text_parts.append(f"[Page {i}]\n[OCR failed on this page]")

        full_text = "\n\n".join(text_parts)
        logger.info(
            "✅ OCR complete: %d pages, %d chars",
            len(images),
            len(full_text),
        )

        return full_text

    except Exception as e:
        logger.error("❌ OCR processing error: %s", str(e))
        return None


def is_scanned_pdf(file_path: str, text_threshold: int = 50) -> bool:
    """
    Detect if a PDF is scanned (image-based) or digital (text-based).

    Uses PyPDF2 to extract text. If fewer than `text_threshold`
    characters are extracted, the PDF is likely scanned.

    Args:
        file_path: Path to the PDF file
        text_threshold: Minimum chars to consider it digital

    Returns:
        True if the PDF appears to be scanned
    """
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)
        total_text = ""
        for page in reader.pages:
            total_text += page.extract_text() or ""

        is_scanned = len(total_text.strip()) < text_threshold
        logger.debug(
            "PDF check: %s -> %d chars extracted -> %s",
            Path(file_path).name,
            len(total_text.strip()),
            "SCANNED" if is_scanned else "DIGITAL",
        )
        return is_scanned

    except Exception as e:
        logger.warning("PDF detection error: %s", str(e))
        # If we can't read it at all, assume scanned
        return True
