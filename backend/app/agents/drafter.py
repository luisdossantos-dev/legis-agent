"""
Legal drafting agent.
Generates summaries, clause drafts and contextual responses.
"""

import logging
from typing import List

from app.core.llm import llm_complete
from app.core.langfuse import observe

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a legal expert assistant specializing in notarial and legal document drafting.
Your tasks include:

1. **Summarizing** legal documents while maintaining legal precision
2. **Drafting** clauses, contracts and deeds
3. **Answering questions** about documents based on provided context
4. **Flagging** ambiguous or risky clauses

Rules:
- Always cite fragments from the original document when relevant
- Use clear but precise language
- Indicate when something requires lawyer review
- Never invent legal information"""


@observe(capture_input=True, capture_output=True)
async def draft_response(
    query: str,
    context_chunks: List[str],
    conversation_history: List[dict],
) -> str:
    """
    Generate a legal drafting response based on retrieved context.

    Args:
        query: User query
        context_chunks: Relevant document fragments
        conversation_history: Conversation history

    Returns:
        Drafted response
    """
    context = "\n\n---\n\n".join(
        f"[Fragment {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *conversation_history[-10:],  # last 10 messages for context
        {
            "role": "user",
            "content": (
                f"Document context:\n\n{context}\n\n"
                f"Query: {query}\n\n"
                "Respond based on the provided context."
            ),
        },
    ]

    response = await llm_complete(messages, profile="reasoning")
    return response
