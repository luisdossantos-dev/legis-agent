"""
Legal document parser.
Supports PDF, DOCX and TXT.
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentParser:
    """Polymorphic parser for legal document formats."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

    # PDF magic byte: '%PDF' (offset 0 in standard PDFs)
    _PDF_MAGIC = b"%PDF"
    # DOCX files are ZIP archives: PK\x03\x04 header at offset 0
    _DOCX_MAGIC = b"PK\x03\x04"
    # Maximum bytes to scan for PDF signature (handles tools that
    # prepend metadata or BOM before the PDF header)
    _PDF_SCAN_LIMIT = 128

    @staticmethod
    def validate_file_signature(content: bytes, ext: str) -> bool:
        """
        Validate that file content matches its extension via magic bytes.

        Checks the file header (magic bytes) against known signatures:
        - PDF: must contain b'%PDF' within the first 128 bytes
        - DOCX: starts with ZIP header b'PK\x03\x04'
        - TXT: must be valid UTF-8 or close enough (no null bytes in first 8KB)

        Args:
            content: Raw file bytes
            ext: Expected file extension (e.g. '.pdf')

        Returns:
            True if the content signature matches the extension
        """
        ext = ext.lower()

        if ext == ".pdf":
            # Scan first N bytes for %PDF. Real PDFs always start with %PDF at offset 0,
            # but some generators (e.g. LibreOffice, certain online tools) prepend
            # BOM, XML metadata, or whitespace before the PDF header.
            return DocumentParser._PDF_MAGIC in content[:DocumentParser._PDF_SCAN_LIMIT]

        if ext == ".docx":
            # DOCX files are ZIP archives — must start with PK\x03\x04
            return len(content) >= 4 and content[:4] == DocumentParser._DOCX_MAGIC

        if ext == ".txt":
            # TXT has no universal magic bytes, but reject binary content
            # by checking for null bytes in the first 8KB
            sample = content[:8192]
            return b"\x00" not in sample

        return False

    async def parse(self, file_path: str) -> str:
        """
        Parse a document and extract its text.

        All sync I/O and CPU-bound parsing (PdfReader, python-docx, file reads)
        is offloaded to a thread pool via asyncio.to_thread to avoid blocking
        the async event loop.

        Args:
            file_path: Path to the file

        Returns:
            Extracted document text

        Raises:
            ValueError: If the format is not supported
        """
        ext = Path(file_path).suffix.lower()

        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported format: {ext}. "
                f"Supported: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )

        if ext == ".pdf":
            return await asyncio.to_thread(self._parse_pdf, file_path)
        elif ext == ".docx":
            return await asyncio.to_thread(self._parse_docx, file_path)
        else:  # .txt
            return await asyncio.to_thread(self._parse_txt, file_path)

    def _parse_pdf(self, file_path: str) -> str:
        """Extract text from PDF using PyPDF2."""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(file_path)
            text_parts = []
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(f"[Page {page_num}]\n{page_text}")

            full_text = "\n\n".join(text_parts)
            logger.info(
                "PDF parsed: %s (%d pages, %d chars)",
                Path(file_path).name,
                len(reader.pages),
                len(full_text),
            )
            return full_text

        except ImportError:
            logger.warning("PyPDF2 not installed, falling back to raw text")
            return self._parse_txt(file_path)

        except Exception as e:
            logger.warning("Failed to parse PDF '%s': %s", file_path, e)
            raise ValueError(f"Could not parse PDF file: {e}") from e

    def _parse_docx(self, file_path: str) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            from docx import Document

            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = "\n\n".join(paragraphs)

            logger.info(
                "DOCX parsed: %s (%d paragraphs, %d chars)",
                Path(file_path).name,
                len(paragraphs),
                len(full_text),
            )
            return full_text

        except ImportError:
            logger.warning("python-docx not installed, falling back to raw text")
            return self._parse_txt(file_path)

        except Exception as e:
            logger.warning("Failed to parse DOCX '%s': %s", file_path, e)
            raise ValueError(f"Could not parse DOCX file: {e}") from e

    def _parse_txt(self, file_path: str) -> str:
        """Read plain TXT file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except FileNotFoundError:
            raise ValueError(f"File not found: {file_path}")
        except PermissionError:
            raise ValueError(f"Permission denied reading file: {file_path}")
        except OSError as e:
            raise ValueError(f"Could not read file '{file_path}': {e}") from e

        logger.info(
            "TXT parsed: %s (%d chars)",
            Path(file_path).name,
            len(text),
        )
        return text


parser = DocumentParser()
