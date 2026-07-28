"""
Email action detection API endpoint.
POST /api/email/action — Detect and execute an action from a classified email.
GET  /api/email/action/tools — List available action tools.
"""

import logging
import time

from fastapi import APIRouter, HTTPException

from app.agents.action_graph import run_action_pipeline
from app.agents.action_tools import get_tool_names, TOOL_DEFINITIONS, COST_THRESHOLDS
from app.models.schemas import (
    ActionDetectionRequest,
    ActionDetectionResponse,
)
from app.core.auth import AuthContext
from app.core.gdpr import AuditAction, log_interaction
from app.models.auth import Role as UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/action", response_model=ActionDetectionResponse)
async def detect_and_execute_action(req: ActionDetectionRequest):
    """
    Detect an action from a classified email and execute it.

    The pipeline:
    1. LLM analyzes the email content + category
    2. Decides which action tool to call
    3. Validates parameters against Pydantic schema
    4. Checks cost guard (estimated cost < threshold)
    5. Executes with retry (max 3, exponential backoff)
    6. Returns the result
    """
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="Email body is required.")

    start = time.time()
    result = await run_action_pipeline(
        email_id=req.email_id or "unknown",
        category=req.category,
        subject=req.subject,
        body=req.body,
        from_address=req.from_address,
    )
    elapsed = (time.time() - start) * 1000

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.UPDATE,
        resource_type="email_action",
        resource_id=req.email_id or "",
        details=f"Action pipeline: category={req.category}, results={len(result.execution_results)}",
        metadata={"category": req.category, "result_count": len(result.execution_results), "cost": result.total_estimated_cost},
    )

    logger.info(
        "Action pipeline: email=%s, actions=%d, time=%.0fms, cost=$%.6f",
        req.email_id,
        len(result.execution_results),
        elapsed,
        result.total_estimated_cost,
    )

    return result


@router.get("/action/tools")
async def list_action_tools():
    """Return the list of available action tools and their schemas."""
    return {
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "required_params": [
                    name for name, f in t["params_schema"].model_fields.items() if f.is_required()
                ],
                "cost_threshold_usd": COST_THRESHOLDS.get(t["name"], {}).get("max_cost_usd", 0.01),
            }
            for t in TOOL_DEFINITIONS
        ]
    }
