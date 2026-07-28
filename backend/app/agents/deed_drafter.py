"""
Deed drafting orchestrator.

Combines:
  1. LlamaIndex → retrieve previous similar clauses as reference
  2. DSPy → draft clause using (optionally) optimized prompt
  3. LiteLLM → fallback when DSPy is unavailable

Flow:
  [type_clause + contexte]
    ↓
  LlamaIndex retrieves similar previous clauses
    ↓
  DSPy (optimized or base) drafts the clause
    ↓
  LiteLLM fallback if DSPy fails or is unavailable
    ↓
  [drafted clause]
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.agents.action_tools import COST_THRESHOLDS, estimate_cost
from app.core.langfuse import observe
from app.core.llm import llm_complete
from app.rag.deed_dspy import draft_clause as dspy_draft_clause
from app.rag.deed_llamaindex import deed_retriever

logger = logging.getLogger(__name__)

_CLAUSE_LLM_PROMPT = """You are a notarial lawyer drafting a formal clause in French.

Clause type: {type_clause}
Context: {contexte}

{references}

Draft a formal notarial clause in French. Use proper legal terminology.
Include placeholders in [BRACKETS] for variable fields.
Output ONLY the clause text, no additional commentary."""


@observe(capture_input=True, capture_output=True)
async def draft_deed_clause(
    type_clause: str,
    contexte: str,
    use_optimized: bool = True,
    use_retriever: bool = True,
) -> Dict[str, Any]:
    """
    Draft a notarial clause using the full pipeline.

    Args:
        type_clause: Type of clause (prix, delai, condition_suspensive, etc.)
        contexte: Context of the notarial act
        use_optimized: Whether to use DSPy-optimized prompt
        use_retriever: Whether to retrieve similar clauses as reference

    Returns:
        Dict with drafted clause and metadata
    """
    references_text = ""
    retrieved_count = 0

    # Step 1: Retrieve similar clauses
    if use_retriever:
        query = f"clause de {type_clause} {contexte[:200]}"
        retrieved = await deed_retriever.retrieve_similar(query=query, top_k=3)

        if retrieved:
            retrieved_count = len(retrieved)
            refs = []
            for r in retrieved[:2]:  # Use top 2
                text = r["text"][:1000]
                refs.append(f"--- Référence (score: {r['score']:.2f}) ---\n{text}")
            references_text = "\n\n".join(refs)
            logger.info("Retrieved %d similar clauses for reference", retrieved_count)

    # Step 2: Try DSPy
    dspy_success = False
    clause = ""

    if use_optimized:
        try:
            dspy_result = await dspy_draft_clause(
                type_clause=type_clause,
                contexte=contexte,
                references=references_text,
                use_optimized=True,
            )
            clause = dspy_result.get("clause", "")
            if clause and len(clause) > 20:
                dspy_success = True
                logger.info("DSPy drafted clause (%d chars)", len(clause))
        except Exception as e:
            logger.warning("DSPy drafting failed: %s", e)

    # Step 3: LiteLLM fallback
    if not dspy_success:
        ref_section = ""
        if references_text:
            ref_section = f"Previous similar clauses for reference:\n{references_text}"

        prompt = _CLAUSE_LLM_PROMPT.format(
            type_clause=type_clause,
            contexte=contexte[:2000],
            references=ref_section,
        )

        logger.info("Using LiteLLM fallback for clause drafting")
        response = await llm_complete(
            [{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        clause = response

    # Estimate cost
    cost_est = estimate_cost("draft_reply", {"type_clause": type_clause, "contexte": contexte})

    return {
        "clause": clause,
        "type_clause": type_clause,
        "method": "dspy" if dspy_success else "litellm",
        "references_used": retrieved_count,
        "estimated_cost_usd": round(cost_est, 6),
        "chars": len(clause),
    }


async def index_deed_text(deed_text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Index a deed text for future retrieval.

    Args:
        deed_text: Text of the deed or clause
        metadata: Optional metadata

    Returns:
        Dict with indexing status
    """
    count = await deed_retriever.index_deed(deed_text, metadata)
    return {
        "indexed": count > 0,
        "chunks": count,
        "total_docs": deed_retriever.doc_count,
    }
