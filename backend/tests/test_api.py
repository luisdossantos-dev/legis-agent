"""
Tests de los endpoints de la API.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Cliente HTTP async para tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test del health check."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_upload_txt(client, tmp_path):
    """Test de subida de TXT."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Contrato de prueba.\n\nCláusula 1: Plazo de 90 días.")

    with open(test_file, "rb") as f:
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", f, "text/plain")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["status"] == "indexed"
    assert "id" in data


@pytest.mark.asyncio
async def test_upload_invalid_extension(client):
    """Test que rechaza formatos no soportados."""
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_documents(client):
    """Test que lista documentos vacíos."""
    response = await client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data


@pytest.mark.asyncio
async def test_analyze_nonexistent_document(client):
    """Test que analizar un doc inexistente da 404."""
    response = await client.post(
        "/api/v1/agents/analyze",
        json={"document_id": "no-existe", "query": "analizá esto"},
    )
    assert response.status_code == 404
