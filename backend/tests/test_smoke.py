"""
🟢 SMOKE TESTS — Sanity checks: imports and health endpoint.
Livianos y rápidos (< 1s).
"""

import pytest


class TestImports:
    """Critical modules import without error."""

    def test_import_models(self):
        from app.models import schemas, auth
        assert schemas is not None

    def test_import_core(self):
        from app.core import config, security, logging
        assert config is not None

    def test_import_api(self):
        from app.api import documents, agents, system, email
        assert documents is not None


class TestHealth:
    """Health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
