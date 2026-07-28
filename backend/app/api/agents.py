"""
Agent API endpoints.
POST /api/agents/analyze — Run analysis pipeline.
POST /api/agents/pipeline — Run multi-step configurable pipeline.
POST /api/agents/chat — Multi-turn chat with the agent.
POST /api/agents/chat/stream — Stream chat response token by token.
"""

import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.graph import run_agent_pipeline, run_chat_pipeline, run_chat_pipeline_stream
from app.core.auth import AuthContext
from app.models.auth import Role as UserRole
from app.core.gdpr import AuditAction, log_interaction
from app.services.document_service import _documents_store
from app.core.rate_limit import limiter
from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalysisResult,
    ChatRequest,
    ChatResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("10/minute")
async def analyze_document(request: Request, req: AnalyzeRequest):
    """
    Run the full pipeline: retrieve → analyze → draft.
    """
    # Check document exists
    if req.document_id not in _documents_store:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = _documents_store[req.document_id]
    logger.info("Analyzing document: %s", doc["filename"])

    start_time = time.time()

    result = await run_agent_pipeline(
        document_id=req.document_id,
        query=req.query,
    )

    elapsed = (time.time() - start_time) * 1000

    if "error" in result and result["error"]:
        logger.error("Analysis pipeline error: %s", result["error"])
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again.")

    # Defensive: ensure document_id is present
    analysis_data = result.get("analysis", {})
    if isinstance(analysis_data, dict) and "document_id" not in analysis_data:
        analysis_data["document_id"] = req.document_id

    try:
        parsed = AnalysisResult(**analysis_data)
    except Exception as e:
        logger.warning("Failed to parse analysis result: %s", e)
        parsed = AnalysisResult(
            document_id=req.document_id,
            summary=str(analysis_data.get("summary", "Analysis completed but result parsing failed.")),
        )

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.ANALYSIS,
        resource_type="document",
        resource_id=req.document_id,
        details=f"Analysis of '{doc.get('filename', '?')}' completed in {elapsed:.0f}ms",
        metadata={"processing_time_ms": elapsed},
    )

    return AnalyzeResponse(
        analysis=parsed,
        processing_time_ms=elapsed,
    )


class PipelineRequest(BaseModel):
    """Request to run a multi-step agent pipeline."""
    document_id: str = Field(..., description="Document ID to process")
    query: str = Field(default="Analyze this legal document and extract its main components.")
    steps: Optional[List[str]] = Field(
        default=None,
        description=(
            "Custom step sequence. Available: extract, analyze, review, draft, send. "
            "If omitted, the supervisor auto-selects based on document type."
        ),
    )


class PipelineResponse(BaseModel):
    """Response from a multi-step pipeline run."""
    analysis: AnalysisResult
    review: str = ""
    draft: str = ""
    document_type: str = ""
    steps_executed: List[str] = []
    processing_time_ms: float = 0.0


@router.post("/pipeline", response_model=PipelineResponse)
@limiter.limit("10/minute")
async def run_pipeline(request: Request, req: PipelineRequest):
    """
    Run the multi-step agent pipeline with optional step configuration.

    The pipeline runs: retrieve → supervisor → [selected steps] → output.

    - If ``steps`` is provided, only those steps execute (in order).
    - If ``steps`` is omitted, the supervisor auto-selects based on
      document type (filename heuristic).

    Available steps:
      - ``extract``: Quick metadata extraction (parties, dates, amounts)
      - ``analyze``: Full structured document analysis
      - ``review``: Legal review of the draft
      - ``draft``: Generate response/email draft
      - ``send``: Final formatting and assembly

    Examples:
      Full pipeline:
        POST /api/v1/agents/pipeline
        {"document_id": "...", "steps": ["extract", "analyze", "review", "draft", "send"]}

      Quick extract + draft (skip review):
        POST /api/v1/agents/pipeline
        {"document_id": "...", "steps": ["extract", "draft"]}

      Automatic (supervisor decides):
        POST /api/v1/agents/pipeline
        {"document_id": "..."}
    """
    if req.document_id not in _documents_store:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = _documents_store[req.document_id]
    logger.info("Running pipeline on: %s (steps=%s)", doc["filename"], req.steps)

    start_time = time.time()

    result = await run_agent_pipeline(
        document_id=req.document_id,
        query=req.query,
        steps=req.steps,
    )

    if "error" in result and result["error"]:
        logger.error("Pipeline error: %s", result["error"])
        raise HTTPException(status_code=500, detail="Pipeline failed. Please try again.")

    # Build analysis result
    analysis_data = result.get("analysis", {})
    if isinstance(analysis_data, dict) and "document_id" not in analysis_data:
        analysis_data["document_id"] = req.document_id

    try:
        parsed = AnalysisResult(**analysis_data)
    except Exception as e:
        logger.warning("Failed to parse analysis result: %s", e)
        parsed = AnalysisResult(
            document_id=req.document_id,
            summary=str(analysis_data.get("summary", "Pipeline completed.")),
        )

    return PipelineResponse(
        analysis=parsed,
        review=result.get("review") or "",
        draft=result.get("draft") or "",
        document_type=result.get("document_type") or "",
        steps_executed=result.get("steps_executed") or [],
        processing_time_ms=(time.time() - start_time) * 1000,
    )


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_with_agent(request: Request, req: ChatRequest):
    """
    Multi-turn chat with the agent about a document.
    Skips analysis step for faster responses (~5-8s saved).
    """
    if req.document_id not in _documents_store:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = _documents_store[req.document_id]
    logger.info("Chat about document: %s", doc["filename"])

    history = [{"role": m.role, "content": m.content} for m in req.messages]

    response = await run_chat_pipeline(
        document_id=req.document_id,
        query=req.query,
        messages=history,
    )

    # Extraer referencias de los chunks recuperados
    references = []

    # Audit log
    log_interaction(
        AuthContext(
            user_id="api", username="api", role=UserRole.ADMIN,
            office="main", display_name="API",
        ),
        AuditAction.CHAT,
        resource_type="document",
        resource_id=req.document_id,
        details=f"Chat about '{doc.get('filename', '?')}' — query: {req.query[:100]}",
    )

    return ChatResponse(
        response=response,
        references=references,
    )


@router.post("/chat/stream")
@limiter.limit("20/minute")
@limiter.exempt
async def chat_with_agent_stream(request: Request, req: ChatRequest):
    """
    Stream a chat response token by token via SSE.

    Same as POST /chat but returns a Server-Sent Events stream.
    The first token arrives in ~1-3s instead of waiting for the full response.

    SSE event format:
      data: {"token": "Hello", "done": false}\n\n
      data: {"token": "", "done": true}\n\n
    """
    if req.document_id not in _documents_store:
        raise HTTPException(status_code=404, detail="Document not found")

    history = [{"role": m.role, "content": m.content} for m in req.messages]

    async def event_stream():
        async for event in run_chat_pipeline_stream(
            document_id=req.document_id,
            query=req.query,
            messages=history,
        ):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
