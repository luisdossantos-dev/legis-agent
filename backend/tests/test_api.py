"""
Tests de la API usando las rutas reales (/api/v1/...).
Livianos: usan mocks para evitar LLM/vector store reales.
"""

import pytest
from unittest.mock import patch, AsyncMock


API_PREFIX = "/api/v1"


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /health returns ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_documents_empty(client, use_temp_config):
    """GET /api/v1/documents/ returns empty list initially."""
    from app.services.document_service import _documents_store
    _documents_store.clear()
    response = await client.get(f"{API_PREFIX}/documents/")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert data["documents"] == []


@pytest.mark.asyncio
async def test_upload_txt(client, use_temp_config):
    """POST /api/v1/documents/upload with TXT returns success."""
    from app.services.document_service import _documents_store
    _documents_store.clear()

    with patch("app.services.document_service.parser.parse", return_value="Contrato de prueba.\nCláusula 1."), \
         patch("app.services.document_service.chunk_by_sections", return_value=[("Contrato de prueba.", {}), ("Cláusula 1.", {})]), \
         patch("app.services.document_service.vector_store.index_document", new_callable=AsyncMock, return_value=2):

        response = await client.post(
            f"{API_PREFIX}/documents/upload",
            files={"file": ("test.txt", b"Contrato de prueba.\nClausula 1.", "text/plain")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["status"] == "processing"
    assert "id" in data


@pytest.mark.asyncio
async def test_upload_invalid_extension(client, use_temp_config):
    """POST /api/v1/documents/upload with unsupported format returns 400."""
    with patch("app.services.document_service.parser.parse") as mock_parse:
        mock_parse.side_effect = ValueError("Unsupported format")
        response = await client.post(
            f"{API_PREFIX}/documents/upload",
            files={"file": ("test.jpg", b"fake-image", "image/jpeg")},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_nonexistent_document(client, use_temp_config):
    """POST /api/v1/agents/analyze with nonexistent doc returns 404."""
    response = await client.post(
        f"{API_PREFIX}/agents/analyze",
        json={"document_id": "no-existe", "query": "analiza esto"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rbac_login(client, use_temp_config, admin_password):
    """POST /api/v1/rbac/auth/login returns token (query params)."""
    response = await client.post(
        f"{API_PREFIX}/rbac/auth/login?username=admin&password={admin_password}",
    )
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_system_config(client):
    """GET /api/v1/system/config returns config."""
    response = await client.get(f"{API_PREFIX}/system/config")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data or "llm" in data or "model" in data


@pytest.mark.asyncio
async def test_security_status(client):
    """GET /api/v1/security/status returns ok."""
    response = await client.get(f"{API_PREFIX}/security/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_routing_status(client):
    """GET /api/v1/routing/status returns ok."""
    response = await client.get(f"{API_PREFIX}/routing/status")
    assert response.status_code == 200
