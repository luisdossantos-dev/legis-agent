"""
Persisted conversation graph with LangGraph checkpointer.

Maintains conversation state across turns using:
  - PostgresSaver when DATABASE_URL is configured
  - MemorySaver for development (fallback)

Each conversation has a thread_id. State persists across turns.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.core.llm import llm_complete

logger = logging.getLogger(__name__)


# ── State ──────────────────────────────────────────────────────


class ConvoState(TypedDict):
    """Persisted state for a multi-turn conversation."""
    conversation_id: str
    document_id: str
    document_text: str
    context: str  # analysis results, retrieved chunks, etc.
    messages: List[Dict[str, str]]  # full conversation history
    turn_count: int
    analysis: Dict[str, Any]
    last_response: str


# ── Graph nodes ────────────────────────────────────────────────


async def ingest_node(state: ConvoState) -> Dict[str, Any]:
    """
    Node 1: Store initial context from the document/analysis.
    Called on first turn or when context is updated.
    """
    logger.info("📥 Ingesting context for conversation %s", state["conversation_id"][:8])

    # If context is already set, this is a subsequent turn -> skip
    if state.get("context") and state.get("turn_count", 0) > 0:
        return {}

    context_parts = []

    if state.get("document_text"):
        context_parts.append(f"Document:\n{state['document_text'][:5000]}")

    if state.get("analysis"):
        context_parts.append(f"Analysis:\n{json.dumps(state['analysis'], indent=2, ensure_ascii=False)[:2000]}")

    if not context_parts:
        context_parts.append("No document context provided.")

    return {
        "context": "\n\n---\n\n".join(context_parts),
        "turn_count": 0,
    }


async def query_node(state: ConvoState) -> Dict[str, Any]:
    """
    Node 2: Process the latest user query with full conversation context.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"last_response": "No query provided."}

    latest = messages[-1]["content"] if messages else ""
    turn = state.get("turn_count", 0)

    logger.info("💬 Processing turn %d for conversation %s", turn + 1, state["conversation_id"][:8])

    # Build system prompt with context and conversation history
    system_prompt = f"""You are a legal assistant with context about a notarial document.

Context:
{state.get('context', 'No context available.')}

Conversation history:
{_format_history(messages[:-1])}

Answer the latest question based on the context and history above.
Be precise and cite relevant parts of the document when possible."""

    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": latest},
    ]

    response = await llm_complete(llm_messages, max_tokens=2048, temperature=0.1)

    return {
        "last_response": response,
        "turn_count": turn + 1,
    }


async def update_node(state: ConvoState) -> Dict[str, Any]:
    """
    Node 3: Update the state after a turn completes.
    This node's output persists into the checkpointer.
    """
    logger.info("💾 Turn %d persisted for conversation %s", state["turn_count"], state["conversation_id"][:8])
    return {}


# ── Helpers ────────────────────────────────────────────────────


def _format_history(messages: List[Dict[str, str]]) -> str:
    """Format conversation history for the LLM prompt."""
    parts = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")[:500]
        parts.append(f"[{i + 1}] {role}: {content}")
    return "\n".join(parts) if parts else "No previous conversation."


# ── Graph builder ──────────────────────────────────────────────


def _create_checkpointer():
    """Create the appropriate checkpointer based on configuration."""
    # Try PostgresSaver if database URL is configured
    db_url = getattr(settings, "DATABASE_URL", "") or getattr(settings, "database_url", "")
    if db_url and "postgresql" in db_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            import asyncpg

            # Return a connection string-based saver
            logger.info("🗄️  Using PostgresSaver checkpointer: %s...", db_url[:30])
            return PostgresSaver(connection_string=db_url)
        except ImportError:
            logger.warning("PostgresSaver not available (install asyncpg or psycopg)")
        except Exception as e:
            logger.warning("PostgresSaver init failed: %s", e)

    # Fallback to MemorySaver
    logger.info("💾 Using MemorySaver checkpointer (dev mode)")
    return MemorySaver()


def create_conversation_graph():
    """Create and compile the conversation graph with persisted state."""
    workflow = StateGraph(ConvoState)

    workflow.add_node("ingest", ingest_node)
    workflow.add_node("query", query_node)
    workflow.add_node("update", update_node)

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "query")
    workflow.add_edge("query", "update")
    workflow.add_edge("update", END)

    checkpointer = _create_checkpointer()

    return workflow.compile(checkpointer=checkpointer)


# Compiled graph
conversation_graph = create_conversation_graph()


# ── Public API ─────────────────────────────────────────────────


async def create_conversation(
    document_id: str = "",
    document_text: str = "",
    analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new conversation with initial context.

    Args:
        document_id: Associated document ID
        document_text: Document text for context
        analysis: Pre-computed analysis results

    Returns:
        Dict with conversation_id and initial state
    """
    convo_id = str(uuid.uuid4())

    initial_state: ConvoState = {
        "conversation_id": convo_id,
        "document_id": document_id,
        "document_text": document_text,
        "context": "",
        "messages": [],
        "turn_count": 0,
        "analysis": analysis or {},
        "last_response": "",
    }

    config = {"configurable": {"thread_id": convo_id}}

    # Run the first turn (just ingest, no query yet)
    try:
        result = await conversation_graph.ainvoke(initial_state, config=config)
        logger.info("✅ Conversation %s created", convo_id[:8])
    except Exception as e:
        logger.error("❌ Failed to create conversation: %s", str(e)[:200])
        raise

    return {
        "conversation_id": convo_id,
        "status": "created",
        "turn_count": 0,
    }


async def add_turn(
    conversation_id: str,
    query: str,
) -> Dict[str, Any]:
    """
    Add a turn to an existing conversation.

    The graph retrieves the persisted state, processes the new query,
    and persists the updated state.

    Args:
        conversation_id: Conversation thread ID
        query: User's new query

    Returns:
        Dict with response and updated state info
    """
    config = {"configurable": {"thread_id": conversation_id}}

    # Get current state from checkpointer
    try:
        current_state = await conversation_graph.aget_state(config)
        if not current_state or not current_state.values:
            return {"error": f"Conversation '{conversation_id}' not found"}
    except Exception as e:
        logger.warning("Could not get state for %s: %s", conversation_id[:8], e)
        return {"error": f"Conversation '{conversation_id}' not found: {str(e)[:100]}"}

    state_values = dict(current_state.values)

    # Append the new message
    messages = state_values.get("messages", [])
    messages.append({"role": "user", "content": query})
    state_values["messages"] = messages

    # Run the graph with updated state
    try:
        result = await conversation_graph.ainvoke(state_values, config=config)
    except Exception as e:
        logger.error("❌ Turn failed for %s: %s", conversation_id[:8], str(e)[:200])
        return {"error": str(e)[:300]}

    turn_count = result.get("turn_count", 0)

    logger.info("💬 Turn %d completed for conversation %s", turn_count, conversation_id[:8])

    return {
        "conversation_id": conversation_id,
        "response": result.get("last_response", ""),
        "turn_count": turn_count,
    }


async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Get the full state of a conversation.

    Args:
        conversation_id: Conversation thread ID

    Returns:
        Dict with full conversation state
    """
    config = {"configurable": {"thread_id": conversation_id}}

    try:
        state = await conversation_graph.aget_state(config)
        if not state or not state.values:
            return {"error": f"Conversation '{conversation_id}' not found"}

        values = dict(state.values)
        return {
            "conversation_id": conversation_id,
            "document_id": values.get("document_id", ""),
            "turn_count": values.get("turn_count", 0),
            "messages": values.get("messages", []),
            "context_preview": values.get("context", "")[:500],
            "last_response": values.get("last_response", ""),
        }
    except (ValueError, TypeError, KeyError) as e:
        logger.warning("Failed to get conversation %s: %s", conversation_id[:8], e)
        return {"error": str(e)[:200]}
