"""
🟢 SMOKE TESTS — Verify the system loads and basic operations work.
"""

import pytest


class TestImports:
    """Critical modules import without error."""

    def test_import_models(self):
        from app.models import schemas, auth, act_schemas, case_schemas, act_generation
        assert schemas is not None

    def test_import_core(self):
        from app.core import config, llm, logging, security, routing, auth as core_auth
        assert config is not None

    def test_import_agents(self):
        from app.agents import graph, analyzer, drafter
        assert graph is not None

    def test_import_rag(self):
        from app.rag import chunker, embeddings, retriever, email_templates
        assert chunker is not None

    def test_import_api(self):
        from app.api import documents, agents, system, email, email_classifier
        assert documents is not None


@pytest.mark.asyncio
class TestHealth:
    """Basic health check endpoints."""

    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    async def test_documents_list_empty(self, client):
        resp = await client.get("/api/documents/")
        assert resp.status_code == 200
        data = resp.json()
        assert "documents" in data
        assert data["documents"] == []

    async def test_system_config(self, client):
        resp = await client.get("/api/system/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert "status" in data

    async def test_email_templates(self, client):
        resp = await client.get("/api/email/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data

    async def test_classify_categories(self, client):
        resp = await client.get("/api/email/classify/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data

    async def test_action_tools(self, client):
        resp = await client.get("/api/email/action/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data

    async def test_clause_types(self, client):
        resp = await client.get("/api/clauses/types")
        assert resp.status_code == 200
        data = resp.json()
        assert "types" in data

    async def test_system_logs(self, client):
        resp = await client.get("/api/system/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data

    async def test_security_status(self, client):
        resp = await client.get("/api/security/status")
        assert resp.status_code == 200

    async def test_routing_status(self, client):
        resp = await client.get("/api/routing/status")
        assert resp.status_code == 200

    async def test_observability_health(self, client):
        resp = await client.get("/api/observability/health")
        assert resp.status_code == 200

    async def test_observability_stats(self, client):
        resp = await client.get("/api/observability/stats")
        assert resp.status_code == 200

    async def test_pdf_schemas(self, client):
        resp = await client.get("/api/pdf/schemas")
        assert resp.status_code == 200
