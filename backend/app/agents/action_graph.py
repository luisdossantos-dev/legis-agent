"""
LangGraph action detection pipeline.

Flow:
  [Email + category]
       ↓
  [action_detector node]
       ├── 1. LLM analyzes email + category
       ├── 2. Decides action (tool call with params)
       ├── 3. Pydantic validation BEFORE execution
       ├── 4. Cost guard: estimated cost < threshold
       ├── 5. Execute with retry (max 3, exp. backoff)
       └── 6. Return result

The graph is a simple two-node pipeline:
  detect → execute → end
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.action_tools import (
    TOOL_DEFINITIONS,
    execute_action,
    get_tool_prompt,
)
from app.models.schemas import ACTION_PARAM_MODELS
from app.core.langfuse import observe
from app.core.llm import llm_complete
from app.models.schemas import (
    ActionDetectionResponse,
    ActionExecutionResult,
    DetectedAction,
)

logger = logging.getLogger(__name__)

# ── System prompt for action detection ────────────────────────

_SIMPLIFIED_PROMPT = """Classify this email for a notary office. Reply ONLY with JSON: {"action": "<name>", "params": {...}, "reasoning": "<why>"}

Actions: draft_reply (needs template_id, variables, priority), create_task (needs assignee, deadline, description), forward_to_notary (needs notary_email, reason, include_attachments), mark_as_read (no params), archive (needs folder: inbox/done/pending/legal/personal)."""


def _build_prompt(category: str, subject: str, body: str, from_address: str) -> List[Dict[str, str]]:
    """Build the message list for the LLM."""
    email_info = f"Category: {category}\n"
    if from_address:
        email_info += f"From: {from_address}\n"
    email_info += f"Subject: {subject}\n\n{body[:2000]}"

    return [
        {"role": "system", "content": _SIMPLIFIED_PROMPT},
        {"role": "user", "content": email_info},
    ]


def _extract_first_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first complete JSON object from text.
    Handles arbitrary nesting by counting brace depth."""
    stack = []
    for i, ch in enumerate(text):
        if ch == '{':
            stack.append(i)
        elif ch == '}':
            if stack:
                start = stack.pop()
                if not stack:  # outermost closing brace
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        return None
    return None


def _parse_llm_response(response: str) -> Optional[DetectedAction]:
    """
    Parse the LLM response to extract the detected action.

    Expected format: {"action": "...", "params": {...}, "reasoning": "..."}
    Also handles free-form text that contains action keywords.
    """
    if not response or not response.strip():
        logger.warning("Empty LLM response")
        return None

    # Log the full response
    logger.info("Raw LLM response (len=%d, chars=%s): %s", len(response), repr(response[:100]), response[:1500])

    # Try to extract and parse JSON with arbitrary nesting depth
    data = _extract_first_json(response)
    if data is None:
        logger.debug("JSON extraction failed, trying full parse")
        try:
            data = json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.debug("Full JSON parse failed: %s", e)
            data = None

    if data:
        action_name = data.get("action", "").strip()
        params = data.get("params", {})
        reasoning = data.get("reasoning", "") or data.get("reason", "")

        if action_name and action_name in ACTION_PARAM_MODELS:
            return DetectedAction(
                action_name=action_name,
                params=params if isinstance(params, dict) else {},
                confidence=0.85,
                reasoning=reasoning[:300] if reasoning else "LLM detected action",
            )

        # Check for alternative key names
        for alt_key in ["tool", "name", "function", "action_name"]:
            if alt_key in data and data[alt_key] in ACTION_PARAM_MODELS:
                return DetectedAction(
                    action_name=data[alt_key],
                    params=params,
                    confidence=0.8,
                    reasoning=reasoning or f"LLM via key '{alt_key}'",
                )

        logger.warning("Unknown action '%s' in LLM response. Keys: %s", action_name, list(data.keys()))
    else:
        logger.debug("No JSON found in response")

    # Fallback: keyword matching
    response_lower = response.lower()
    for tool_name in ["draft_reply", "create_task", "forward_to_notary", "mark_as_read", "archive"]:
        if tool_name in response_lower:
            logger.info("Fallback: matched '%s' in response text", tool_name)
            return DetectedAction(
                action_name=tool_name, params={}, confidence=0.6,
                reasoning=f"Keyword-matched '{tool_name}'",
            )

    logger.warning("Failed to parse any action from LLM response")
    return None


# ── LangGraph state ───────────────────────────────────────────


class ActionGraphState(TypedDict):
    """State for the action detection graph."""
    email_id: str
    category: str
    from_address: str
    subject: str
    body: str
    detected_action: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]


# ── Graph nodes ────────────────────────────────────────────────


async def detect_action_node(state: ActionGraphState) -> Dict[str, Any]:
    """
    Node 1: LLM analyzes the email and detects an action.
    """
    logger.info("🔍 Detecting action for email %s (category: %s)", state["email_id"], state["category"])

    messages = _build_prompt(
        category=state["category"],
        subject=state["subject"],
        body=state["body"],
        from_address=state["from_address"],
    )

    response = await llm_complete(messages, max_tokens=2048, temperature=0.1)

    # If response is empty, try a simpler prompt
    if not response.strip():
        logger.warning("Empty LLM response, retrying with simplified prompt")
        simplified = [
            {"role": "system", "content": _SIMPLIFIED_PROMPT},
            {"role": "user", "content": f"Category: {state['category']}\nSubject: {state['subject'][:200]}\nBody: {state['body'][:500]}"},
        ]
        response = await llm_complete(simplified, max_tokens=2048, temperature=0.1)

    detected = _parse_llm_response(response)

    if detected is None:
        logger.warning("No action detected, defaulting to archive")
        detected = DetectedAction(
            action_name="archive",
            params={"folder": "done"},
            confidence=0.5,
            reasoning="No clear action detected from LLM, defaulting to archive",
        )

    logger.info(
        "   ➡️ Action detected: %s (confidence=%.2f)",
        detected.action_name, detected.confidence,
    )

    return {"detected_action": detected.model_dump()}


async def execute_action_node(state: ActionGraphState) -> Dict[str, Any]:
    """
    Node 2: Execute the detected action with validation and cost guards.
    """
    detected_data = state.get("detected_action", {})
    if not detected_data:
        return {"execution_result": {"action_name": "none", "status": "skipped", "error": "No action detected"}}

    action_name = detected_data.get("action_name", "")
    params = detected_data.get("params", {})

    logger.info("⚡ Executing action: %s", action_name)

    result = await execute_action(action_name, params)

    logger.info(
        "   ✅ Action result: %s (status=%s)",
        action_name, result.status,
    )

    return {"execution_result": result.model_dump()}


# ── Graph builder ─────────────────────────────────────────────


def create_action_graph():
    """Create and compile the action detection graph."""
    workflow = StateGraph(ActionGraphState)

    workflow.add_node("detect", detect_action_node)
    workflow.add_node("execute", execute_action_node)

    workflow.set_entry_point("detect")
    workflow.add_edge("detect", "execute")
    workflow.add_edge("execute", END)

    return workflow.compile()


# Compiled graph instance
action_graph = create_action_graph()


# ── Public API ─────────────────────────────────────────────────


@observe(capture_input=True, capture_output=True)
async def run_action_pipeline(
    email_id: str,
    category: str,
    subject: str,
    body: str,
    from_address: str = "",
) -> ActionDetectionResponse:
    """
    Run the full action detection pipeline: detect → validate → execute.

    Args:
        email_id: Email identifier
        category: Pre-classified category
        subject: Email subject
        body: Email body
        from_address: Sender email

    Returns:
        ActionDetectionResponse with detected actions and execution results
    """
    start_time = time.time()

    initial_state: ActionGraphState = {
        "email_id": email_id,
        "category": category,
        "from_address": from_address,
        "subject": subject,
        "body": body,
        "detected_action": None,
        "execution_result": None,
    }

    try:
        result = await action_graph.ainvoke(initial_state)
        elapsed = (time.time() - start_time) * 1000

        detected_data = result.get("detected_action", {})
        exec_data = result.get("execution_result", {})

        detected_action = DetectedAction(**detected_data) if detected_data else DetectedAction(action_name="none", params={})

        exec_result = ActionExecutionResult(**exec_data) if exec_data else ActionExecutionResult(
            action_name="none", status="skipped",
        )

        logger.info(
            "✅ Action pipeline completed in %.0fms: %s → %s",
            elapsed, detected_action.action_name, exec_result.status,
        )

        return ActionDetectionResponse(
            email_id=email_id,
            detected_actions=[detected_action],
            execution_results=[exec_result],
            total_estimated_cost=exec_result.cost_estimated_usd,
        )

    except Exception as e:
        logger.error("❌ Action pipeline error: %s", str(e))
        return ActionDetectionResponse(
            email_id=email_id,
            detected_actions=[],
            execution_results=[
                ActionExecutionResult(
                    action_name="error",
                    status="execution_error",
                    error=str(e),
                )
            ],
            total_estimated_cost=0.0,
        )
