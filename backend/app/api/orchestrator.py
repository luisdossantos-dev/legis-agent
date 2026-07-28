"""
Multi-agent orchestrator API endpoint.
POST /api/orchestrator/run — Run the multi-agent pipeline.
GET  /api/orchestrator/tools — List available agent tools with cost info.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.supervisor_graph import run_orchestrator
from app.agents.agent_tools import COST_THRESHOLDS, ESTIMATED_TOKENS, TOOL_REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter()


class OrchestratorRequest(BaseModel):
    request: str
    context: str = ""


@router.post("/run")
async def run_multi_agent(req: OrchestratorRequest):
    """
    Run the multi-agent orchestrator.

    The supervisor routes the request through sub-agents:
      analyze → draft → review → format

    Each sub-agent has:
      - Pydantic parameter validation
      - Cost guards (blocks if estimated cost exceeds threshold)
      - Retry with exponential backoff (1s → 3s → 9s, max 3)

    Example request:
      "Analyze this contract and identify risky clauses"
      + document text as context
    """
    if not req.request.strip():
        raise HTTPException(status_code=400, detail="Request is required.")

    logger.info("🧠 Orchestrator request: %s", req.request[:200])
    result = await run_orchestrator(request=req.request, context=req.context)
    return result


@router.get("/tools")
async def list_agent_tools():
    """List available agent tools with cost thresholds and schema info."""
    tools = []
    for name, info in TOOL_REGISTRY.items():
        schema = info["params_schema"]
        tools.append({
            "name": name,
            "description": info["description"],
            "cost_threshold_usd": info["cost_threshold"],
            "estimated_tokens": info["estimated_tokens"],
            "required_params": [
                fname for fname, f in schema.model_fields.items() if f.is_required()
            ],
        })
    return {
        "tools": tools,
        "cost_info": "Estimated costs based on gpt-4o pricing ($2.50/1M input, $10.00/1M output)",
    }
