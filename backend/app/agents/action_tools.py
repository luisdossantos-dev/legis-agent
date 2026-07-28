"""
Action tools for email-based task detection and execution.

Each tool has:
  - name: Unique identifier
  - description: What the tool does (for LLM prompt)
  - params_schema: Pydantic model for parameter validation
  - cost_threshold: Max allowed cost in USD
  - execute(): The actual side-effect logic

Cost guards prevent excessive LLM usage by estimating cost
before execution and rejecting calls that exceed thresholds.
"""

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

from app.core.langfuse import observe
from app.models.schemas import (
    ACTION_PARAM_MODELS,
    ActionExecutionResult,
    ArchiveParams,
    CreateTaskParams,
    DraftReplyParams,
    ForwardToNotaryParams,
    MarkAsReadParams,
)

logger = logging.getLogger(__name__)

# ── Cost thresholds ──────────────────────────────────────────
# Estimated cost per tool based on typical token usage.
# These are conservative estimates; real costs depend on the model.

COST_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "mark_as_read": {"max_tokens": 50, "max_cost_usd": 0.001},
    "draft_reply": {"max_tokens": 1500, "max_cost_usd": 0.03},
    "create_task": {"max_tokens": 500, "max_cost_usd": 0.01},
    "forward_to_notary": {"max_tokens": 300, "max_cost_usd": 0.005},
    "archive": {"max_tokens": 100, "max_cost_usd": 0.002},
}

# Cost per token estimate (conservative for GPT-4o class models)
_COST_PER_INPUT_TOKEN = 0.0000025  # $2.50/1M tokens
_COST_PER_OUTPUT_TOKEN = 0.00001   # $10/1M tokens


def estimate_cost(
    action_name: str,
    params: Dict[str, Any],
    input_tokens: int = 0,
) -> float:
    """
    Estimate the cost of executing an action.

    Combines the tool's base cost (from threshold) with
    the actual input context cost for more accuracy.

    Args:
        action_name: Tool name
        params: Tool parameters
        input_tokens: Number of input context tokens (0 = use default)

    Returns:
        Estimated cost in USD
    """
    threshold = COST_THRESHOLDS.get(action_name, {})
    max_tokens = threshold.get("max_tokens", 500)
    max_cost = threshold.get("max_cost_usd", 0.01)

    # Estimate input tokens from params
    param_chars = sum(len(str(v)) for v in params.values())
    estimated_input = input_tokens or (param_chars // 4) + 100

    total_tokens = estimated_input + max_tokens
    estimated = (estimated_input * _COST_PER_INPUT_TOKEN) + (max_tokens * _COST_PER_OUTPUT_TOKEN)

    # Cap at the threshold max
    return min(estimated, max_cost)


# ── Tool definitions ─────────────────────────────────────────

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "mark_as_read",
        "description": "Mark the email as read. No parameters needed. Use when the email is informational and requires no further action.",
        "params_schema": MarkAsReadParams,
        "prompt_example": '{"action": "mark_as_read", "params": {}}',
    },
    {
        "name": "draft_reply",
        "description": "Draft a reply to the email using a predefined template. Use when a response is needed based on a template.",
        "params_schema": DraftReplyParams,
        "prompt_example": '{"action": "draft_reply", "params": {"template_id": "tmpl_escritura01", "variables": {"cliente": "Juan Perez"}, "priority": "normal"}}',
    },
    {
        "name": "create_task",
        "description": "Create a follow-up task assigned to a team member with a deadline. Use when action is required from someone.",
        "params_schema": CreateTaskParams,
        "prompt_example": '{"action": "create_task", "params": {"assignee": "notary_maria", "deadline": "2024-03-01", "description": "Prepare deed for client visit"}}',
    },
    {
        "name": "forward_to_notary",
        "description": "Forward the email to a specific notary for handling. Use when the email requires notarial expertise.",
        "params_schema": ForwardToNotaryParams,
        "prompt_example": '{"action": "forward_to_notary", "params": {"notary_email": "notary@notaria.es", "reason": "Requires notarial review of deed terms", "include_attachments": true}}',
    },
    {
        "name": "archive",
        "description": "Archive the email to a folder. Use when the email has been processed and needs to be filed.",
        "params_schema": ArchiveParams,
        "prompt_example": '{"action": "archive", "params": {"folder": "done"}}',
    },
]


def get_tool_names() -> List[str]:
    """Return list of available tool names."""
    return [t["name"] for t in TOOL_DEFINITIONS]


def get_tool_prompt() -> str:
    """Generate the tools section for the LLM system prompt."""
    lines = ["Available actions (choose ONE):"]
    for t in TOOL_DEFINITIONS:
        schema_hint = ""
        if t["params_schema"] != MarkAsReadParams:
            fields = t["params_schema"].model_fields
            required = [name for name, field in fields.items() if field.is_required()]
            schema_hint = f" Required params: {required}"
        lines.append(f"  - {t['name']}: {t['description']}{schema_hint}")
        lines.append(f"    Example: {t['prompt_example']}")
    lines.append("")
    lines.append('Respond with ONLY a JSON object: {"action": "<name>", "params": {...}, "reasoning": "<why>"}')
    return "\n".join(lines)


# ── Validation ────────────────────────────────────────────────


def validate_action_params(action_name: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate action parameters against the tool's Pydantic schema.

    Returns:
        (is_valid, error_message, validated_params)
    """
    schema_cls = ACTION_PARAM_MODELS.get(action_name)
    if schema_cls is None:
        return False, f"Unknown action: {action_name}", params

    try:
        validated = schema_cls(**params)
        return True, None, validated.model_dump()
    except ValidationError as e:
        errors = e.errors()
        error_msgs = [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        return False, "; ".join(error_msgs), params


# ── Cost guard ────────────────────────────────────────────────


def check_cost_guard(action_name: str, params: Dict[str, Any]) -> Tuple[bool, float, Optional[str]]:
    """
    Check if the action's estimated cost is within the threshold.

    Returns:
        (is_allowed, estimated_cost, error_message)
    """
    estimated = estimate_cost(action_name, params)
    threshold = COST_THRESHOLDS.get(action_name, {}).get("max_cost_usd", 0.01)

    if estimated > threshold:
        return False, estimated, f"Cost guard: ${estimated:.6f} exceeds threshold ${threshold:.6f}"

    return True, estimated, None


# ── Execution ──────────────────────────────────────────────────


@observe(capture_input=True)
async def execute_action(
    action_name: str,
    params: Dict[str, Any],
) -> ActionExecutionResult:
    """
    Execute an action with retry logic (max 3 attempts, exponential backoff).

    Steps:
    1. Validate params against Pydantic schema
    2. Check cost guard
    3. Execute with retry
    4. Return result
    """
    cost_estimated = estimate_cost(action_name, params)

    # Step 1: Validate
    is_valid, error_msg, validated_params = validate_action_params(action_name, params)
    if not is_valid:
        logger.warning("Action '%s' validation failed: %s", action_name, error_msg)
        return ActionExecutionResult(
            action_name=action_name,
            status="validation_error",
            params=params,
            cost_estimated_usd=cost_estimated,
            error=error_msg,
        )

    # Step 2: Cost guard
    is_allowed, cost_estimated, cost_error = check_cost_guard(action_name, validated_params)
    if not is_allowed:
        logger.warning("Action '%s' cost guard triggered: %s", action_name, cost_error)
        return ActionExecutionResult(
            action_name=action_name,
            status="cost_guard",
            params=validated_params,
            cost_estimated_usd=cost_estimated,
            error=cost_error,
        )

    # Step 3: Execute with retry
    max_retries = 3
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            result = await _execute_tool_impl(action_name, validated_params)
            logger.info(
                "Action '%s' executed successfully (attempt %d/%d)",
                action_name, attempt, max_retries,
            )
            return ActionExecutionResult(
                action_name=action_name,
                status="success",
                params=validated_params,
                result=result,
                cost_estimated_usd=cost_estimated,
            )
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "Action '%s' attempt %d/%d failed: %s",
                action_name, attempt, max_retries, last_error,
            )
            if attempt < max_retries:
                backoff = 2 ** attempt + random.uniform(0, 1)
                await asyncio.sleep(backoff)

    return ActionExecutionResult(
        action_name=action_name,
        status="execution_error",
        params=validated_params,
        cost_estimated_usd=cost_estimated,
        error=f"All {max_retries} attempts failed: {last_error}",
    )


async def _execute_tool_impl(action_name: str, params: Dict[str, Any]) -> str:
    """
    Internal tool execution. In production, this would call real APIs.
    For now, simulates execution and returns a descriptive result.
    """
    # Simulate processing time
    await asyncio.sleep(0.2)

    if action_name == "mark_as_read":
        return f"Email marked as read."

    elif action_name == "draft_reply":
        template_id = params.get("template_id", "unknown")
        var_count = len(params.get("variables", {}))
        return f"Draft reply using template '{template_id}' with {var_count} variables (priority: {params.get('priority', 'normal')})."

    elif action_name == "create_task":
        assignee = params.get("assignee", "unknown")
        deadline = params.get("deadline", "unknown")
        desc = params.get("description", "")[:80]
        return f"Task created: assignee={assignee}, deadline={deadline}, description='{desc}'."

    elif action_name == "forward_to_notary":
        notary = params.get("notary_email", "unknown")
        reason = params.get("reason", "")[:80]
        incl = params.get("include_attachments", True)
        return f"Email forwarded to {notary}. Reason: {reason}. Attachments: {'yes' if incl else 'no'}."

    elif action_name == "archive":
        folder = params.get("folder", "done")
        return f"Email archived to '{folder}' folder."

    else:
        raise ValueError(f"Unknown action: {action_name}")
