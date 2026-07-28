"""
LangGraph graph for orchestrating agents.
Flow: retrieve → supervisor → (extract → analyze → review → draft → send) → END.
"""

import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.analyzer import analyze_document
from app.agents.drafter import draft_response
from app.core.langfuse import observe
from app.core.llm import llm_complete, llm_complete_stream
from app.core.cache import async_ttl_cache
from app.core.profiler import timed
from app.models.schemas import AgentState
from app.rag.retriever import vector_store
from app.rag.context_optimizer import compute_dynamic_top_k, prepare_context_for_llm

logger = logging.getLogger(__name__)

# ── Available pipeline steps ──────────────────────────────────
ALL_STEPS = ["extract", "analyze", "review", "draft", "send"]

# Document type keywords for supervisor routing
_DOC_TYPE_KEYWORDS = {
    "contrato": ["contrato", "contract", "convenio", "acuerdo"],
    "escritura": ["escritura", "deed", "venta", "compraventa", "sale"],
    "poder": ["poder", "power of attorney", "mandato", "proxy"],
    "testamento": ["testamento", "will", "testament", "last will"],
    "demanda": ["demanda", "lawsuit", "complaint", "litigio", "pleito"],
    "dictamen": ["dictamen", "opinion", "legal opinion", "memorandum"],
}

# Pipeline routing rules per document type
_DOC_TYPE_PIPELINES: Dict[str, List[str]] = {
    "contrato":  ["extract", "analyze", "review", "draft"],
    "escritura": ["extract", "draft"],      # Simple: just draft
    "poder":     ["extract", "analyze", "draft"],
    "testamento": ["extract", "analyze", "review", "draft"],
    "demanda":   ["extract", "analyze", "draft"],
    "dictamen":  ["extract", "draft"],
    "default":   ["extract", "analyze", "draft"],
}


class GraphState(TypedDict):
    """LangGraph state type.

    Steps are executed in order based on the selected steps list.
    The supervisor inspects the document and sets recommended steps.
    The router dispatches to ``steps[step_index]``, each step
    increments the index via the ``router`` node.
    """
    document_id: str
    query: str
    retrieved_chunks: List[str]
    analysis: Dict[str, Any]
    review: Optional[str]
    draft: str
    messages: List[Dict[str, str]]
    error: str
    steps: List[str]         # ordered steps to execute
    step_index: int          # current position in steps
    document_type: str       # detected document type


# ── Named constants ─────────────────────────────────────────
_DEFAULT_TOP_K = 5
_MAX_RETRIEVAL_CHUNKS = 20
_DEFAULT_CHUNK_DISPLAY = 3


# ── Node implementations ──────────────────────────────────────


async def retrieve_node(state: GraphState) -> Dict[str, Any]:
    """Retrieval node: fetches relevant chunks from the vector store."""
    query = state["query"]
    logger.info("🔍 Retrieving chunks for: %s", query[:100])

    top_k = compute_dynamic_top_k(query)
    results = await vector_store.search(
        query=query,
        document_id=state["document_id"],
        top_k=top_k,
    )
    chunks = [r["text"] for r in results]
    logger.info("   -> %d chunks retrieved (top_k=%d)", len(chunks), top_k)
    return {"retrieved_chunks": chunks}


async def supervisor_node(state: GraphState) -> Dict[str, Any]:
    """
    Supervisor node: inspects document type and sets pipeline steps.

    If ``steps`` is already provided by the caller, it is respected.
    Otherwise, the supervisor auto-detects the document type from
    the filename and selects the optimal pipeline.
    """
    # If steps were explicitly provided, skip auto-detection
    if state.get("steps"):
        return {"step_index": 0}

    # Fetch document metadata to detect type
    from app.services.document_service import _documents_store
    doc = _documents_store.get(state["document_id"], {})
    filename: str = doc.get("filename", "").lower()

    detected_type = "default"
    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        if any(kw in filename for kw in keywords):
            detected_type = doc_type
            break

    steps = _DOC_TYPE_PIPELINES.get(detected_type, _DOC_TYPE_PIPELINES["default"])

    logger.info(
        "🤖 Supervisor: detected_type=%s, steps=%s, filename=%s",
        detected_type, steps, filename,
    )

    return {
        "document_type": detected_type,
        "steps": steps,
        "step_index": 0,
    }


async def extract_node(state: GraphState) -> Dict[str, Any]:
    """
    Extract node: quick metadata extraction (parties, dates, amounts).
    Uses a lightweight LLM call (profile='fast').
    """
    logger.info("📋 Extracting metadata from document: %s", state["document_id"])

    chunks = state["retrieved_chunks"]
    context = "\n\n---\n\n".join(chunks[:3])[:3000]  # first 3 chunks only

    prompt = (
        "Extract key metadata from this legal document fragment.\n"
        "Return ONLY a JSON object with these fields:\n"
        '{"document_type": "...", "parties": ["..."], "dates": ["..."], '
        '"amounts": [{"description": "..."}], "summary": "..."}\n\n'
        f"Document:\n{context}"
    )

    try:
        response = await llm_complete(
            [{"role": "user", "content": prompt}],
            profile="fast",
        )
        import json
        # Try to parse JSON from response
        match = __import__("re").search(r"\{.*\}", response, __import__("re").DOTALL)
        if match:
            parsed = json.loads(match.group())
            # Merge with existing analysis if any
            existing = state.get("analysis", {})
            existing.update({
                "document_type": parsed.get("document_type", existing.get("document_type")),
                "parties": parsed.get("parties", existing.get("parties", [])),
                "dates": parsed.get("dates", existing.get("dates", [])),
                "amounts": parsed.get("amounts", existing.get("amounts", [])),
            })
            return {"analysis": existing}
    except Exception as e:
        logger.debug("Extract node non-critical error: %s", str(e)[:100])

    return {}


async def analyze_node(state: GraphState) -> Dict[str, Any]:
    """Analysis node: runs the analyzer agent on the document."""
    logger.info("📊 Analyzing document: %s", state["document_id"])

    chunk_dicts = [{"text": c, "score": 1.0} for c in state["retrieved_chunks"]]
    context = prepare_context_for_llm(chunk_dicts, token_budget=3000)

    from app.models.schemas import AnalysisResult
    analysis = await analyze_document(
        document_text=context,
        query=state["query"],
        document_id=state["document_id"],
    )

    return {"analysis": analysis.model_dump()}


async def review_node(state: GraphState) -> Dict[str, Any]:
    """
    Review node: checks the draft for legal issues, missing clauses, risks.
    """
    draft = state.get("draft", "")
    if not draft:
        logger.warning("Review node: no draft to review")
        return {"review": "No draft available for review."}

    logger.info("🔍 Reviewing draft (%d chars)", len(draft))

    prompt = (
        "Review this legal document draft for:\n"
        "1. Missing mandatory clauses\n"
        "2. Ambiguous or risky language\n"
        "3. Inconsistencies between sections\n"
        "4. Compliance with the requested document type\n\n"
        f"Draft:\n{draft[:4000]}\n\n"
        "Output a concise review with SEVERITY tags: [HIGH], [MEDIUM], [LOW]."
    )

    try:
        review = await llm_complete(
            [{"role": "user", "content": prompt}],
            profile="fast",
        )
        logger.info("   -> Review generated (%d chars)", len(review))
        return {"review": review.strip()}
    except Exception as e:
        logger.warning("Review node failed: %s", str(e)[:100])
        return {"review": "[Review unavailable due to processing error]"}


async def draft_node(state: GraphState) -> Dict[str, Any]:
    """Draft node: generates a response based on analysis/context."""
    logger.info("✍️ Drafting response for: %s", state["query"][:100])

    draft = await draft_response(
        query=state["query"],
        context_chunks=state["retrieved_chunks"],
        conversation_history=state.get("messages", []),
    )

    return {"draft": draft}


async def send_node(state: GraphState) -> Dict[str, Any]:
    """
    Send node: formats the final output with all results.
    Assembles analysis + review + draft into the final response.
    """
    logger.info("📨 Assembling final response")

    analysis = state.get("analysis", {})
    review = state.get("review", "")
    draft = state.get("draft", "")

    # If there's a review, append it to the draft
    if review and draft:
        draft = draft + "\n\n---\n\n📋 **Legal Review**\n" + review

    return {"draft": draft}


# ── Central step router ───────────────────────────────────────


def route_next(state: GraphState) -> str:
    """
    Central router: determines the next step based on ``step_index``.
    The supervisor sets ``steps`` and ``step_index=0``.
    Each step node increments ``step_index``.
    """
    steps = state.get("steps", ["draft"])
    idx = state.get("step_index", 0)

    if idx >= len(steps):
        return "__end__"

    return steps[idx]


# ── Graph construction ────────────────────────────────────────


def create_agent_graph() -> StateGraph:
    """
    Creates and compiles the multi-step LangGraph agent graph.

    Flow:
        retrieve → supervisor → router → [step] → router → ... → END

    The router dispatches to the next step based on ``steps[step_index]``.
    Each step increments ``step_index`` so the next dispatch picks up
    the subsequent step.
    """
    workflow = StateGraph(GraphState)

    # Nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("router", lambda s: {"step_index": s.get("step_index", 0) + 1})
    workflow.add_node("extract", extract_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("review", review_node)
    workflow.add_node("draft", draft_node)
    workflow.add_node("send", send_node)

    # Entry point
    workflow.set_entry_point("retrieve")

    # Retrieve → Supervisor
    workflow.add_edge("retrieve", "supervisor")

    # Supervisor → Router (first dispatch)
    workflow.add_conditional_edges(
        "supervisor",
        route_next,
        {
            "extract": "extract",
            "analyze": "analyze",
            "review": "review",
            "draft": "draft",
            "send": "send",
            "__end__": END,
        },
    )

    # Each step → Router → next step or END
    for step_name in ALL_STEPS:
        workflow.add_edge(step_name, "router")

    # Router → next step (increment step_index, then route to next)
    workflow.add_conditional_edges(
        "router",
        route_next,
        {
            "extract": "extract",
            "analyze": "analyze",
            "review": "review",
            "draft": "draft",
            "send": "send",
            "__end__": END,
        },
    )

    return workflow.compile()


# Instancia del grafo compilado
agent_graph = create_agent_graph()


@timed("app.agents.graph")
@observe(capture_input=True, capture_output=True)
@async_ttl_cache(ttl_seconds=300)
async def run_agent_pipeline(
    document_id: str,
    query: str,
    messages: List[Dict[str, str]] | None = None,
    steps: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Runs the multi-step agent pipeline.

    Args:
        document_id: Document ID
        query: User query
        messages: Conversation history (optional)
        steps: Custom step sequence (optional).
               If omitted, the supervisor auto-selects steps
               based on document type.
               Available: extract, analyze, review, draft, send

    Returns:
        Pipeline result with analysis, review, and draft
    """
    start_time = time.time()

    initial_state: GraphState = {
        "document_id": document_id,
        "query": query,
        "retrieved_chunks": [],
        "analysis": {},
        "review": "",
        "draft": "",
        "messages": messages or [],
        "error": "",
        "steps": steps or [],
        "step_index": 0,
        "document_type": "",
    }

    try:
        result = await agent_graph.ainvoke(initial_state)
        elapsed = (time.time() - start_time) * 1000

        logger.info(
            "✅ Pipeline completed in %.0fms (steps=%s)",
            elapsed, result.get("steps", []),
        )

        return {
            "analysis": result.get("analysis") or {},
            "review": result.get("review") or "",
            "draft": result.get("draft") or "",
            "document_type": result.get("document_type") or "",
            "steps_executed": result.get("steps") or [],
            "processing_time_ms": elapsed,
        }

    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error("❌ Pipeline error after %.0fms: %s", elapsed, str(e))
        return {
            "error": str(e),
            "analysis": {},
            "review": "",
            "draft": "",
            "document_type": "",
            "steps_executed": [],
            "processing_time_ms": elapsed,
        }


# ── Chat pipelines (unchanged) ────────────────────────────────


async def run_chat_pipeline_stream(
    document_id: str,
    query: str,
    messages: list[Dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a chat response token by token."""
    import json

    logger.info("Retrieving chunks for stream chat: %s", query[:100])

    top_k = compute_dynamic_top_k(query)
    results = await vector_store.search(
        query=query,
        document_id=document_id,
        top_k=top_k,
    )
    chunks = [r["text"] for r in results]
    logger.info("   -> %d chunks retrieved, starting stream", len(chunks))

    context = prepare_context_for_llm(results, token_budget=2500)

    history = messages or []
    system_prompt = (
        "You are a legal expert assistant specializing in notarial and legal documents.\n"
        "Answer questions based on the provided document context. "
        "Cite fragments when relevant."
    )

    llm_messages = [
        {"role": "system", "content": system_prompt},
        *history[-10:],
        {
            "role": "user",
            "content": f"Document context:\n\n{context}\n\nQuery: {query}",
        },
    ]

    try:
        async for event in llm_complete_stream(
            messages=llm_messages,
            profile="fast",
        ):
            yield event
    except Exception as e:
        logger.error("Stream pipeline error: %s", str(e))
        yield f"data: {json.dumps({'token': '', 'done': True, 'error': str(e)[:200]})}\n\n"


async def run_chat_pipeline(
    document_id: str,
    query: str,
    messages: list[Dict[str, str]] | None = None,
) -> str:
    """Run a chat pipeline: retrieve + draft (no analysis)."""
    logger.info("Chat pipeline: retrieving chunks for: %s", query[:100])

    top_k = compute_dynamic_top_k(query)
    results = await vector_store.search(
        query=query,
        document_id=document_id,
        top_k=top_k,
    )
    chunks = [r["text"] for r in results]

    context = prepare_context_for_llm(results, token_budget=2500)

    history = messages or []
    system_prompt = (
        "You are a legal expert assistant specializing in notarial and legal documents.\n"
        "Answer questions based on the provided document context. "
        "Cite fragments when relevant."
    )

    llm_messages = [
        {"role": "system", "content": system_prompt},
        *history[-10:],
        {
            "role": "user",
            "content": f"Document context:\n\n{context}\n\nQuery: {query}",
        },
    ]

    try:
        from app.core.llm import llm_complete
        response = await llm_complete(messages=llm_messages, profile="fast")
        return response
    except Exception as e:
        logger.error("Chat pipeline error: %s", str(e))
        return ""
