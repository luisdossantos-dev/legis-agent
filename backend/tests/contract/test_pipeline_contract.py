"""
🟡 CONTRACT TESTS — Pipeline & Analysis API contract.

Fast tests that verify HTTP contract WITHOUT document uploads or LLM calls.
"""

import pytest


@pytest.mark.asyncio
async def test_pipeline_no_document_returns_404(client):
    """Pipeline with non-existent doc returns 404."""
    response = await client.post(
        "/api/v1/agents/pipeline",
        json={"document_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_nonexistent_document_returns_404(client):
    """Analyze endpoint returns 404 for non-existent document."""
    response = await client.post(
        "/api/v1/agents/analyze",
        json={"document_id": "00000000-0000-0000-0000-000000000000", "query": "test"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_nonexistent_document_returns_404(client):
    """Chat endpoint returns 404 for non-existent document."""
    response = await client.post(
        "/api/v1/agents/chat",
        json={
            "document_id": "00000000-0000-0000-0000-000000000000",
            "messages": [],
            "query": "test",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_pipeline_rejects_missing_document_id(client):
    """Pipeline without document_id returns 422."""
    response = await client.post(
        "/api/v1/agents/pipeline",
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_rejects_missing_document_id(client):
    """Analyze without document_id returns 422."""
    response = await client.post(
        "/api/v1/agents/analyze",
        json={},
    )
    assert response.status_code == 422
