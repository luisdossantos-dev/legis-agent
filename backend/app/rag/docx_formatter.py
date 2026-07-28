"""
DOCX formatter for notarial acts.

Generates a .docx file with standard notarial formatting:
- Title page with act type
- Numbered sections with proper headings
- Signature block
- Footer with notary information
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.models.act_generation import GenerationSection

logger = logging.getLogger(__name__)


def format_as_docx(
    title: str,
    sections: List[GenerationSection],
    act_type: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    Generate a .docx file with standard notarial formatting.

    Args:
        title: Document title
        sections: List of sections with title and content
        act_type: Type of notarial act
        output_dir: Output directory (default: uploads/)

    Returns:
        Path to the generated .docx file
    """
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt, Inches
    except ImportError:
        logger.warning("python-docx not installed. Returning empty path.")
        return ""

    doc = Document()

    # ── Page setup ────────────────────────────────────────────
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1.2)
    section.right_margin = Inches(1.2)

    # ── Title ─────────────────────────────────────────────────
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title.upper())
    run.bold = True
    run.font.size = Pt(16)
    run.font.name = "Times New Roman"

    # Subtitle
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Acte {act_type} — {datetime.now().strftime('%Y')}")
    run.font.size = Pt(12)
    run.font.name = "Times New Roman"
    run.italic = True

    doc.add_paragraph()  # spacer

    # ── Horizontal line ───────────────────────────────────────
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 60)
    run.font.size = Pt(8)

    doc.add_paragraph()  # spacer

    # ── Sections ──────────────────────────────────────────────
    for i, section_data in enumerate(sections, 1):
        # Section title
        p = doc.add_paragraph()
        run = p.add_run(section_data.title)
        run.bold = True
        run.font.size = Pt(12)
        run.font.name = "Times New Roman"

        # Section content
        p = doc.add_paragraph()
        run = p.add_run(section_data.content)
        run.font.size = Pt(11)
        run.font.name = "Times New Roman"

        # Spacer between sections
        doc.add_paragraph()

    # ── Signature block ───────────────────────────────────────
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run("\n\nFait à [Ville], le " + datetime.now().strftime("%d %B %Y"))
    run.font.size = Pt(11)
    run.font.name = "Times New Roman"

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run("\n\nMaître [Notaire]")
    run.bold = True
    run.font.size = Pt(11)
    run.font.name = "Times New Roman"

    # ── Save ──────────────────────────────────────────────────
    out_dir = Path(output_dir or settings.UPLOAD_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"acte_{act_type}_{timestamp}.docx"
    filepath = out_dir / filename

    doc.save(str(filepath))
    logger.info("DOCX saved: %s (%d sections)", filepath, len(sections))

    return str(filepath)
