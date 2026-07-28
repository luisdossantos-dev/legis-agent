"""
Multi-turn conversation API with persisted memory.
POST /api/conversations — Create a new conversation.
POST /api/conversations/{id}/turn — Add a turn.
GET  /api/conversations/{id} — Get conversation state.
GET  /api/conversations — List active conversations (from memory).
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.conversation_graph import add_turn, create_conversation, get_conversation

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateConversationRequest(BaseModel):
    document_id: str = ""
    document_text: str = ""
    analysis: Optional[Dict[str, Any]] = None


class AddTurnRequest(BaseModel):
    query: str


@router.post("")
async def create_new_conversation(req: CreateConversationRequest):
    """
    Create a new multi-turn conversation with persisted memory.

    Initializes the conversation with document context so future
    turns can reference it without re-uploading the document.

    Args:
        document_id: Associated document ID (optional)
        document_text: Document text for LLM context
        analysis: Pre-computed analysis results (optional)
    """
    logger.info("📝 Creating new conversation (doc=%s)", req.document_id or "none")

    result = await create_conversation(
        document_id=req.document_id,
        document_text=req.document_text,
        analysis=req.analysis,
    )

    if "error" in result:
        logger.error("Conversation creation failed: %s", result["error"])
        raise HTTPException(status_code=500, detail="Failed to create conversation.")

    return result


@router.post("/{conversation_id}/turn")
async def add_conversation_turn(conversation_id: str, req: AddTurnRequest):
    """
    Add a turn to an existing conversation.

    The persisted graph state is retrieved, the new query is processed
    with full conversation context, and the updated state is persisted.

    Each turn enriches the state — no context is lost between turns.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")

    logger.info("💬 Turn on conversation %s: '%s'", conversation_id[:8], req.query[:100])

    result = await add_turn(
        conversation_id=conversation_id,
        query=req.query,
    )

    if "error" in result:
        logger.warning("Conversation turn failed: %s", result["error"])
        raise HTTPException(status_code=404, detail="Could not process query for this conversation.")

    return result


@router.get("/{conversation_id}")
async def get_conversation_state(conversation_id: str):
    """
    Get the full state of a conversation, including all messages
    and the current context.
    """
    result = await get_conversation(conversation_id)

    if "error" in result:
        logger.warning("Conversation state lookup failed: %s", result["error"])
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return result
