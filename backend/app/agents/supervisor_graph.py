"""
Multi-agent orchestrator with LangGraph super-graph.

Architecture:
                    SUPERVISOR (router)
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ ANALYZE │ │  DRAFT  │ │  REVIEW │
    │ Agent   │ │  Agent  │ │  Agent  │
    └──────────┘ └──────────┘ └──────────┘
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                   ┌──────────┐
                   │ FORMAT  │
                   │ Agent   │
                   └──────────┘
                         ↓
                   [FINAL output]

Each sub-agent has:
  - Pydantic-validated tool params
  - Cost guard (estimated cost < threshold)
  - Retry with exponential backoff (1s → 3s → 9s)
"""

import json
import logging
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.agent_tools import (
    TOOL_REGISTRY,
    check_cost_guard,
    estimate_cost,
    get_tool_names,
    retry_with_backoff,
    validate_tool_params,
)
from app.core.langfuse import observe
from app.core.llm import llm_complete
from app.models.schemas import AnalysisResult

logger = logging.getLogger(__name__)

# ── Agent routing prompts ─────────────────────────────────────


def _build_supervisor_prompt(request: str, context: str, history: list) -> str:
    """Build the supervisor prompt including agent history to prevent loops."""
    history_str = ""
    if history:
        done_agents = [h.get("agent", "?") for h in history]
        history_str = f"\nAlready called: {', '.join(done_agents)}"

    return f'{{"next_agent":"analyze"}}\n\nChoose a DIFFERENT agent than before. Options: analyze, draft, review, format, final.\n"{request}"{history_str}'


# ── State ──────────────────────────────────────────────────────


class OrcState(TypedDict):
    """State for the orchestrator super-graph."""
    request: str
    context: str
    agent_history: List[Dict[str, Any]]
    current_agent: Optional[str]
    current_params: Optional[Dict[str, Any]]
    results: Dict[str, Any]
    errors: List[str]
    final_output: Optional[Dict[str, Any]]


# ── Supervisor node ────────────────────────────────────────────


async def supervisor_node(state: OrcState) -> Dict[str, Any]:
    """
    Supervisor: decides which agent to call next based on the request.
    Returns the next agent name and params for that agent.
    """
    # If analyze already ran, go to final to avoid loops
    history = state.get("agent_history", [])
    if len(history) >= 1:
        done_agents = [h.get("agent") for h in history if h.get("agent")]
        logger.info("🧠 Supervisor: agents already executed: %s -> routing to final", done_agents)
        return {"current_agent": "final", "current_params": {}}

    prompt = _build_supervisor_prompt(
        request=state["request"],
        context=state.get("context", "")[:2000],
        history=history,
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Route this request: {state['request'][:500]}"},
    ]

    response = await llm_complete(messages, max_tokens=500, temperature=0.0)
    logger.info("Supervisor LLM response (len=%d): %s", len(response), repr(response[:300]))
    decision = _extract_json(response)

    # Determine the agent: from LLM or keyword fallback
    agent = None
    params = {}

    if decision and decision.get("next_agent"):
        candidate = decision["next_agent"].strip().lower()
        # Filter out template literals (DeepSeek likes to output "<agent_name>")
        if candidate in ("analyze", "draft", "review", "format", "final") and "<" not in candidate:
            agent = candidate
            params = decision.get("params", {})

    # Keyword fallback if LLM didn't produce a valid agent
    if not agent:
        req_lower = state.get("request", "").lower()
        if any(kw in req_lower for kw in ["analyz", "extract", "examin"]):
            agent = "analyze"
        elif any(kw in req_lower for kw in ["draft", "write", "compos", "redact"]):
            agent = "draft"
        elif any(kw in req_lower for kw in ["clause", "risk", "review", "check"]):
            agent = "review"
        elif any(kw in req_lower for kw in ["format", "assembl", "generat"]):
            agent = "format"
        else:
            agent = "final"

    # Ensure params have required fields for the chosen agent
    params = _ensure_params(agent, params, state.get("request", ""), state.get("context", ""))

    logger.info("🧠 Supervisor: routing to '%s'", agent)
    return {"current_agent": agent, "current_params": params}


# ── Sub-agent execution nodes ──────────────────────────────────


def _route_after_supervisor(state: OrcState) -> Literal["analyze", "draft", "review", "format", "final"]:
    """Route to the sub-agent chosen by the supervisor."""
    agent = state.get("current_agent", "final")
    valid_agents = {"analyze", "draft", "review", "format"}
    return agent if agent in valid_agents else "final"


async def analyze_agent_node(state: OrcState) -> Dict[str, Any]:
    """Sub-agent: Analyze a legal document."""
    logger.info("📊 Running ANALYZE agent")
    params = state.get("current_params", {})

    # Cost guard
    cost_error = check_cost_guard("analyze_document", params)
    if cost_error:
        return _agent_error("analyze", cost_error)

    # Param validation
    param_error = validate_tool_params("analyze_document", params)
    if param_error:
        return _agent_error("analyze", param_error)

    try:
        from app.agents.analyzer import analyze_document

        result = await retry_with_backoff(
            analyze_document,
            kwargs={
                "document_text": params.get("document_text", state.get("context", "")),
                "query": params.get("query", state.get("request", "")),
                "document_id": params.get("document_id", ""),
            },
        )

        # Convert Pydantic to dict
        result_dict = result.model_dump() if hasattr(result, "model_dump") else result

        logger.info("✅ ANALYZE complete: %d clauses, %d parties",
                     len(result_dict.get("clauses", [])),
                     len(result_dict.get("parties", [])))

        return {
            "results": {**state.get("results", {}), "analysis": result_dict},
            "agent_history": state.get("agent_history", []) + [
                {"agent": "analyze", "status": "completed", "time": time.time()}
            ],
        }

    except Exception as e:
        logger.error("❌ ANALYZE agent error: %s", str(e)[:200])
        return _agent_error("analyze", str(e)[:300])


async def draft_agent_node(state: OrcState) -> Dict[str, Any]:
    """Sub-agent: Draft a legal response."""
    logger.info("✍️  Running DRAFT agent")
    params = state.get("current_params", {})

    cost_error = check_cost_guard("draft_response", params)
    if cost_error:
        return _agent_error("draft", cost_error)

    param_error = validate_tool_params("draft_response", params)
    if param_error:
        return _agent_error("draft", param_error)

    try:
        from app.agents.drafter import draft_response

        result = await retry_with_backoff(
            draft_response,
            kwargs={
                "query": params.get("query", state.get("request", "")),
                "context_chunks": params.get("context_chunks", []),
                "conversation_history": params.get("conversation_history", []),
            },
        )

        logger.info("✅ DRAFT complete: %d chars", len(result))

        return {
            "results": {**state.get("results", {}), "draft": result},
            "agent_history": state.get("agent_history", []) + [
                {"agent": "draft", "status": "completed", "time": time.time()}
            ],
        }

    except Exception as e:
        logger.error("❌ DRAFT agent error: %s", str(e)[:200])
        return _agent_error("draft", str(e)[:300])


async def review_agent_node(state: OrcState) -> Dict[str, Any]:
    """Sub-agent: Review a clause for risks."""
    logger.info("🔍 Running REVIEW agent")
    params = state.get("current_params", {})

    cost_error = check_cost_guard("review_clause", params)
    if cost_error:
        return _agent_error("review", cost_error)

    param_error = validate_tool_params("review_clause", params)
    if param_error:
        return _agent_error("review", param_error)

    try:
        from app.agents.clause_reviewer import review_clause

        result = await retry_with_backoff(
            review_clause,
            kwargs={
                "clause_text": params.get("clause_text", state.get("context", "")),
                "clause_type": params.get("clause_type", "autre"),
                "context": params.get("context", ""),
            },
        )

        logger.info("✅ REVIEW complete: risk=%s, %d issues",
                     result.get("risk_level", "?"),
                     len(result.get("issues", [])))

        return {
            "results": {**state.get("results", {}), "review": result},
            "agent_history": state.get("agent_history", []) + [
                {"agent": "review", "status": "completed", "time": time.time()}
            ],
        }

    except Exception as e:
        logger.error("❌ REVIEW agent error: %s", str(e)[:200])
        return _agent_error("review", str(e)[:300])


async def format_agent_node(state: OrcState) -> Dict[str, Any]:
    """Sub-agent: Format / assemble final output."""
    logger.info("📄 Running FORMAT agent")
    params = state.get("current_params", {})

    cost_error = check_cost_guard("format_document", params)
    if cost_error:
        return _agent_error("format", cost_error)

    param_error = validate_tool_params("format_document", params)
    if param_error:
        return _agent_error("format", param_error)

    # Build assembled output from all sub-agent results
    all_results = state.get("results", {})

    assembled = {
        "status": "completed",
        "agents_executed": [h.get("agent") for h in state.get("agent_history", [])],
        "analysis": all_results.get("analysis"),
        "draft": all_results.get("draft"),
        "review": all_results.get("review"),
    }

    logger.info(
        "✅ FORMAT complete: assembled %d agent results",
        len(assembled.get("agents_executed", [])),
    )

    return {
        "final_output": assembled,
        "agent_history": state.get("agent_history", []) + [
            {"agent": "format", "status": "completed", "time": time.time()}
        ],
    }


async def final_node(state: OrcState) -> Dict[str, Any]:
    """Final node: build and return the aggregated result."""
    all_results = state.get("results", {})

    final = {
        "status": "completed",
        "agents_executed": [h.get("agent") for h in state.get("agent_history", [])],
        "results": all_results,
        "errors": state.get("errors", []),
    }

    # If there's a final_output already (from format agent), use it
    if state.get("final_output"):
        final = state["final_output"]

    logger.info(
        "🏁 Orchestrator final: %d agents executed, %d errors",
        len(final.get("agents_executed", [])),
        len(final.get("errors", [])),
    )

    return {"final_output": final}


# ── Helpers ────────────────────────────────────────────────────


def _agent_error(agent: str, error: str) -> Dict[str, Any]:
    """Return an error state for a failed sub-agent."""
    return {
        "errors": [error],
        "agent_history": [{"agent": agent, "status": "error", "error": error[:200]}],
    }


def _ensure_params(agent: str, params: Dict[str, Any], request: str, context: str) -> Dict[str, Any]:
    """Ensure params have required fields for the chosen agent."""
    if agent == "analyze":
        if "document_text" not in params or not params.get("document_text"):
            params["document_text"] = context[:50000]
        if "query" not in params or not params.get("query"):
            params["query"] = request
        if "document_id" not in params:
            params["document_id"] = ""
    elif agent == "draft":
        if "query" not in params or not params.get("query"):
            params["query"] = request
        if "context_chunks" not in params:
            params["context_chunks"] = [context[:5000]] if context else []
        if "conversation_history" not in params:
            params["conversation_history"] = []
    elif agent == "review":
        if "clause_text" not in params or not params.get("clause_text"):
            params["clause_text"] = context[:10000]
        if "clause_type" not in params:
            params["clause_type"] = "autre"
    elif agent == "format":
        if "content" not in params or not params.get("content"):
            params["content"] = context[:50000]
        if "format_type" not in params:
            params["format_type"] = "docx"
    return params


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
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


# ── Graph builder ──────────────────────────────────────────────


def create_orchestrator_graph():
    """Create and compile the multi-agent orchestrator graph."""
    workflow = StateGraph(OrcState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("analyze", analyze_agent_node)
    workflow.add_node("draft", draft_agent_node)
    workflow.add_node("review", review_agent_node)
    workflow.add_node("format", format_agent_node)
    workflow.add_node("final", final_node)

    # Entry point
    workflow.set_entry_point("supervisor")

    # Supervisor routes to sub-agents based on decision
    workflow.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "analyze": "analyze",
            "draft": "draft",
            "review": "review",
            "format": "format",
            "final": "final",
        },
    )

    # After any sub-agent, return to supervisor for next decision
    workflow.add_edge("analyze", "supervisor")
    workflow.add_edge("draft", "supervisor")
    workflow.add_edge("review", "supervisor")
    workflow.add_edge("format", "final")

    # Final is terminal
    workflow.add_edge("final", END)

    return workflow.compile()


# Compiled graph
orchestrator_graph = create_orchestrator_graph()


# ── Public API ─────────────────────────────────────────────────


@observe(capture_input=True, capture_output=True)
async def run_orchestrator(
    request: str,
    context: str = "",
) -> Dict[str, Any]:
    """
    Run the multi-agent orchestrator.

    The supervisor routes the request through sub-agents (analyze,
    draft, review, format) until completion. Each sub-agent has
    cost guards, param validation, and retry with backoff.

    Args:
        request: User request (e.g., "Analyze this contract")
        context: Document text or context for the agents

    Returns:
        Dict with final output from all agents
    """
    start_time = time.time()

    initial_state: OrcState = {
        "request": request,
        "context": context,
        "agent_history": [],
        "current_agent": None,
        "current_params": {},
        "results": {},
        "errors": [],
        "final_output": None,
    }

    try:
        result_state = await orchestrator_graph.ainvoke(initial_state)
        elapsed = (time.time() - start_time) * 1000

        final = result_state.get("final_output", {})
        final["processing_time_ms"] = round(elapsed, 1)

        logger.info(
            "✅ Orchestrator completed in %.1fms: %d agents, %d errors",
            elapsed,
            len(final.get("agents_executed", [])),
            len(final.get("errors", [])),
        )

        return final

    except Exception as e:
        logger.error("❌ Orchestrator error: %s", str(e)[:200])
        return {
            "status": "error",
            "error": str(e)[:300],
            "processing_time_ms": round((time.time() - start_time) * 1000, 1),
        }
