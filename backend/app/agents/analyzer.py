"""
Document analysis agent.
Extracts document type, parties, dates, clauses, amounts and risks.
"""

import logging
from typing import Dict, List, Optional

from app.core.llm import llm_complete
from app.core.langfuse import observe
from app.models.schemas import AnalysisResult, ClauseInfo

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a legal expert assistant specializing in notarial and legal document analysis.
Your task is to extract structured information from legal documents.

You must identify:
1. **Document type**: Contract, Deed, Power of Attorney, Will, Lawsuit, etc.
2. **Parties involved**: Individuals or legal entities mentioned
3. **Key Dates**: Document dates, deadlines, terms
4. **Main Clauses**: Each clause with its title and content
5. **Amounts**: Numerical values, currency, concept
6. **Risks**: Clauses or terms that could be problematic
7. **Summary**: Document synthesis in 2-3 paragraphs

Respond ONLY with the structured analysis in the requested format.
Do not include unsolicited legal opinions."""


@observe(capture_input=True, capture_output=True)
async def analyze_document(
    document_text: str,
    query: str = "Analyze this legal document and extract its main components.",
    document_id: str = "",
) -> AnalysisResult:
    """
    Execute document legal analysis.

    Args:
        document_text: Full document text
        query: User's specific query
        document_id: Document identifier to include in result

    Returns:
        AnalysisResult with extracted structured information
    """
    # Truncate to ~3K tokens to avoid excessive context for the LLM.
    # 12 000 characters ≈ 3 000 tokens at ~4 chars/token,
    # which keeps the prompt well within common context windows.
    _MAX_DOCUMENT_CHARS = 12_000
    if len(document_text) > _MAX_DOCUMENT_CHARS:
        logger.warning(
            "Document truncated from %d to %d chars",
            len(document_text),
            _MAX_DOCUMENT_CHARS,
        )
        document_text = document_text[:_MAX_DOCUMENT_CHARS] + "\n\n[...document truncated...]"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Document:\n\n{document_text}\n\n{query}",
        },
    ]

    response = await llm_complete(messages, profile="fast")

    # Parse the structured response
    analysis = _parse_analysis(response, document_text, document_id)
    return analysis


def _parse_analysis(response: str, document_text: str, document_id: str = "") -> AnalysisResult:
    """
    Parse LLM response into a structured AnalysisResult.

    In production this would use a more robust parser
    (e.g., JSON mode from the LLM or a specialized parser).
    """
    return AnalysisResult(
        document_id=document_id,
        document_type=_extract_section(response, "Document type"),
        parties=_extract_list(response, "Parties involved"),
        dates=_extract_list(response, "Key Dates"),
        amounts=_extract_amounts(response),
        clauses=_extract_clauses(response),
        risks=_extract_list(response, "Risks"),
        summary=_extract_section(response, "Summary") or response[:500],
    )


def _extract_section(text: str, section: str) -> Optional[str]:
    """Extract a section from the response text."""
    import re
    pattern = rf"(?:{section}):?\s*\n?(.*?)(?:\n\n|\Z|(?:\n(?:Document|Part|Date|Clause|Amount|Risk|Summary)))"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_list(text: str, section: str) -> List[str]:
    """Extract a list of items from a section."""
    section_text = _extract_section(text, section)
    if not section_text:
        return []
    import re
    items = re.findall(r"(?:^|\n)\s*[-•*]\s*(.+)", section_text)
    return [item.strip() for item in items if item.strip()]


def _extract_amounts(text: str) -> List[Dict]:
    """Extract mentioned amounts."""
    amounts = []
    section = _extract_section(text, "Amounts")
    if section:
        import re
        lines = section.strip().split("\n")
        for line in lines:
            if line.strip():
                amounts.append({"description": line.strip()})
    return amounts


def _extract_clauses(text: str) -> List[ClauseInfo]:
    """Extract clauses from the response."""
    clauses = []
    section = _extract_section(text, "Main Clauses")
    if section:
        import re
        clause_blocks = re.split(r"\n\s*(?:\d+\.|[-•*])\s*", section)
        for block in clause_blocks:
            block = block.strip()
            if block and len(block) > 10:
                title = block.split("\n")[0][:80]
                clauses.append(
                    ClauseInfo(title=title, content=block[:500])
                )
    return clauses
