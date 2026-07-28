"""
LangGraph agent for automatic case file assembly.

Organizes documents within a case file into structured categories:
  principal → annexes → correspondance → identite

Also generates meaningful case names based on document content.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.core.langfuse import observe
from app.core.llm import llm_complete
from app.rag.case_clustering import case_store, process_document_for_cases
from app.models.case_schemas import CATEGORY_LABELS, CATEGORY_ORDER

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────

_CATEGORIZE_PROMPT = """Classify this notarial document into exactly one category.
Output ONLY JSON: {{"category": "<category>", "reasoning": "<why>"}}

Categories:
- principal: Main legal document (deed, contract, will, power of attorney)
- annexe: Supporting document (appraisal, certificate, report, plan)
- correspondance: Letters, emails, communication
- identite: ID card, passport, identity verification

Document: {filename}
Summary: {summary}"""

_NAME_CASE_PROMPT = """Generate a concise, professional name for this notarial case file.
Output ONLY JSON: {{"name": "<name>", "parties": ["...", "..."], "property_ref": "<address or reference>"}}

The name should include: type of act, parties, and property if applicable.
Max 80 characters.

Documents in this case:
{documents}"""

_ORGANIZE_PROMPT = """Organize these documents into a structured case file.
Output ONLY JSON with:
{{"categories": {{"principal": ["doc_id", ...], "annexe": ["doc_id", ...], "correspondance": ["doc_id", ...], "identite": ["doc_id", ...]}}}}

Documents: {documents_json}"""


# ── State ────────────────────────────────────────────────────


class CaseAssemblyState(TypedDict):
    """State for the case assembly graph."""
    case_id: str
    documents: List[Dict[str, Any]]  # list of CaseDocument dicts
    categorized: bool
    named: bool
    organized: bool
    result: Optional[Dict[str, Any]]


# ── Graph nodes ──────────────────────────────────────────────


async def categorize_documents_node(state: CaseAssemblyState) -> Dict[str, Any]:
    """Node 1: Categorize each document in the case."""
    docs = state.get("documents", [])
    if not docs:
        return {"categorized": True, "result": {"error": "No documents"}}

    logger.info("🏷️  Categorizing %d documents in case %s", len(docs), state["case_id"])

    for doc in docs:
        filename = doc.get("filename", "unknown")
        summary = doc.get("summary", "")[:500]

        prompt = _CATEGORIZE_PROMPT.format(filename=filename, summary=summary)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Categorize: {filename}"},
        ]

        response = await llm_complete(messages, max_tokens=200, temperature=0.0)
        result = _extract_json(response)

        if result and result.get("category") in CATEGORY_ORDER:
            doc["category"] = result["category"]
            logger.info("   -> %s: %s", filename, result["category"])
        else:
            # Fallback: use keyword matching
            doc["category"] = _keyword_categorize(filename, summary)
            logger.info("   -> %s: %s (keyword fallback)", filename, doc["category"])

    return {"categorized": True}


async def name_case_node(state: CaseAssemblyState) -> Dict[str, Any]:
    """Node 2: Generate a meaningful name for the case."""
    docs = state.get("documents", [])
    case_id = state["case_id"]

    logger.info("🏷️  Naming case %s", case_id)

    docs_summary = "\n".join(
        f"- {d.get('filename', '?')} ({d.get('category', '?')}): {d.get('summary', '')[:100]}"
        for d in docs
    )

    prompt = _NAME_CASE_PROMPT.format(documents=docs_summary)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Name this case with {len(docs)} documents."},
    ]

    response = await llm_complete(messages, max_tokens=300, temperature=0.0)
    result = _extract_json(response)

    case = case_store.get_case(case_id)
    if case:
        # LLM result - detect if it's just copying the template
        if result and result.get("name"):
            name = result["name"][:80]
            # Detect template literal placeholders
            if "<" in name or name in ("...", ""):
                name = _generate_fallback_name(case, docs)
            case["name"] = name
            logger.info("   -> Case named: %s", case["name"])
        else:
            case["name"] = _generate_fallback_name(case, docs)
            logger.info("   -> Case named (fallback): %s", case["name"])

        if result and result.get("parties"):
            parties = result["parties"]
            # Filter out template literals
            parties = [p for p in parties if p not in ("...", "<...>", "") and "<" not in p]
            if parties:
                case["parties"] = parties

        if result and result.get("property_ref"):
            ref = result["property_ref"]
            if ref not in ("...", "<...>", "<address or reference>", ""):
                case["property_ref"] = ref

    return {"named": True}


async def organize_case_node(state: CaseAssemblyState) -> Dict[str, Any]:
    """Node 3: Organize documents into the standard structure."""
    docs = state.get("documents", [])
    case_id = state["case_id"]

    logger.info("📂 Organizing %d documents in case %s", len(docs), case_id)

    # Sort documents by category order
    categorized = sorted(
        docs,
        key=lambda d: (
            CATEGORY_ORDER.index(d.get("category", "annexe"))
            if d.get("category") in CATEGORY_ORDER
            else 99
        ),
    )

    # Update the case with organized documents
    case = case_store.get_case(case_id)
    if case:
        case["documents"] = categorized
        case["document_count"] = len(categorized)
        case["updated_at"] = datetime.now(timezone.utc).isoformat()

    return {"organized": True, "result": {"organized_count": len(categorized)}}


async def finalize_node(state: CaseAssemblyState) -> Dict[str, Any]:
    """Node 4: Build and return the final result."""
    case_id = state["case_id"]
    case = case_store.get_case(case_id)

    if not case:
        return {"result": {"error": f"Case {case_id} not found"}}

    # Build structured view
    organized_docs: Dict[str, List] = {}
    for cat in CATEGORY_ORDER:
        organized_docs[cat] = [
            {
                "id": d["id"],
                "filename": d["filename"],
                "category": d.get("category", "annexe"),
                "doc_type": d.get("doc_type", ""),
                "summary": d.get("summary", "")[:200],
            }
            for d in case.get("documents", [])
            if d.get("category") == cat
        ]

    result = {
        "case_id": case_id,
        "name": case.get("name", ""),
        "status": case.get("status", "open"),
        "parties": case.get("parties", []),
        "property_ref": case.get("property_ref", ""),
        "document_count": case.get("document_count", 0),
        "categories": organized_docs,
        "category_labels": CATEGORY_LABELS,
    }

    logger.info(
        "✅ Case assembled: %s (%d docs, %d parties)",
        result["name"],
        result["document_count"],
        len(result["parties"]),
    )

    return {"result": result}


# ── Helpers ────────────────────────────────────────────────────


def _generate_fallback_name(case: Dict[str, Any], docs: List[Dict[str, Any]]) -> str:
    """Generate a fallback case name from document filenames and content."""
    # Try to extract type from first doc
    filenames = [d.get("filename", "") for d in docs if d.get("filename")]

    doc_types = {
        "vente": "Sale", "compromis": "Compromise", "acte": "Deed",
        "testament": "Will", "pouvoir": "POA", "contrat": "Contract",
    }

    doc_type_label = "Case"
    for fn in filenames:
        fn_lower = fn.lower()
        for kw, label in doc_types.items():
            if kw in fn_lower:
                doc_type_label = label
                break

    # Try to extract party names from summaries
    parties_found = []
    for d in docs:
        summary = d.get("summary", "")
        for word in summary.split():
            if word.startswith("M.") or word.startswith("Mme"):
                # Try to get the name after title
                idx = summary.find(word)
                if idx >= 0:
                    name_part = summary[idx:idx+50].split(",")[0].split(".")[0]
                    if name_part not in parties_found:
                        parties_found.append(name_part)

    case_num = str(case.get("id", ""))[:8]
    if parties_found:
        return f"{doc_type_label} - {' & '.join(parties_found[:2])}"
    return f"{doc_type_label} #{case_num}"


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


def _keyword_categorize(filename: str, summary: str) -> str:
    """Fallback keyword-based categorization."""
    text = (filename + " " + summary).lower()

    if any(kw in text for kw in ["id", "passport", "identity", "cni", "passeport", "carte"]):
        return "identite"
    if any(kw in text for kw in ["email", "letter", "courrier", "correspondance"]):
        return "correspondance"
    if any(kw in text for kw in ["acte", "contrat", "vente", "deed", "will", "testament", "compromis"]):
        return "principal"
    return "annexe"  # default


# ── Graph builder ──────────────────────────────────────────────


def create_case_assembly_graph():
    """Create and compile the case assembly graph."""
    workflow = StateGraph(CaseAssemblyState)

    workflow.add_node("categorize", categorize_documents_node)
    workflow.add_node("name", name_case_node)
    workflow.add_node("organize", organize_case_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("categorize")
    workflow.add_edge("categorize", "name")
    workflow.add_edge("name", "organize")
    workflow.add_edge("organize", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# Compiled graph
case_assembly_graph = create_case_assembly_graph()


# ── Public API ─────────────────────────────────────────────────


@observe(capture_input=True, capture_output=True)
async def assemble_case(case_id: str) -> Dict[str, Any]:
    """
    Run the full case assembly pipeline for a case file.

    1. Categorize each document (principal/annexe/correspondance/identite)
    2. Generate a meaningful case name
    3. Organize documents in standard order
    4. Return the structured result

    Args:
        case_id: Case file ID to assemble

    Returns:
        Dict with organized case structure
    """
    case = case_store.get_case(case_id)
    if not case:
        return {"error": f"Case {case_id} not found"}

    initial_state: CaseAssemblyState = {
        "case_id": case_id,
        "documents": case.get("documents", []),
        "categorized": False,
        "named": False,
        "organized": False,
        "result": None,
    }

    try:
        result_state = await case_assembly_graph.ainvoke(initial_state)
        return result_state.get("result", {})

    except Exception as e:
        logger.error("❌ Case assembly error: %s", str(e))
        return {
            "case_id": case_id,
            "name": case.get("name", ""),
            "error": str(e)[:200],
        }


async def process_and_assemble(
    document_id: str,
    filename: str,
    text: str,
    chunks: List[str],
    embeddings: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    """
    Process a document and assemble its case in one step.

    1. Cluster/assign document to a case
    2. Run the full assembly pipeline on that case
    """
    # Step 1: Process document into case system
    assign_result = await process_document_for_cases(
        document_id=document_id,
        filename=filename,
        text=text,
        chunks=chunks,
        embeddings=embeddings,
    )

    case_id = assign_result.get("assigned_to")
    if not case_id:
        return {**assign_result, "assembly": None}

    # Step 2: Run assembly pipeline
    assembly = await assemble_case(case_id)

    return {
        **assign_result,
        "assembly": assembly,
    }
