"""
🟡 CONTRACT TESTS — Email templates & health endpoint contract.

Fast tests that verify HTTP contract WITHOUT document uploads or LLM calls.
"""

import pytest


@pytest.mark.asyncio
async def test_email_templates_endpoint(client):
    """GET /api/v1/email/templates returns template list with required fields."""
    response = await client.get("/api/v1/email/templates")
    assert response.status_code == 200
    data = response.json()
    assert "templates" in data
    assert len(data["templates"]) > 0
    for t in data["templates"]:
        assert "act_type" in t
        assert "name" in t
        assert "required_fields" in t


@pytest.mark.asyncio
async def test_email_templates_structure(client):
    """Each email template has valid structure."""
    response = await client.get("/api/v1/email/templates")
    templates = response.json()["templates"]
    for tmpl in templates:
        assert isinstance(tmpl["act_type"], str) and len(tmpl["act_type"]) > 0
        assert isinstance(tmpl["name"], str)
        assert isinstance(tmpl["required_fields"], list)
        for field in tmpl["required_fields"]:
            assert isinstance(field, str)


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint returns ok status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
