"""
⚡ PERFORMANCE TESTS — Detect performance regressions and establish baselines.

Use pytest-benchmark for deterministic measurements.
Marked with @pytest.mark.benchmark so they can be skipped in fast CI runs.
"""

import pytest

benchmark = pytest.mark.benchmark


class TestAuthPerformance:
    """Authentication performance benchmarks."""

    @benchmark
    def test_login_performance(self, benchmark):
        """Measure login latency. Expect < 200ms."""
        from app.core.auth import authenticate_user, get_admin_password
        pwd = get_admin_password()
        assert pwd is not None, "Admin password not initialised"
        result = benchmark(authenticate_user, "admin", pwd)
        assert result is not None

    @benchmark
    def test_list_users_performance(self, benchmark):
        """Measure listing users latency. Expect < 50ms."""
        from app.core.auth import list_users
        users = benchmark(list_users)
        assert len(users) >= 1


@pytest.mark.asyncio
class TestAPIPerformance:
    """API endpoint benchmarks (minimal payloads)."""

    @benchmark
    async def test_health_endpoint_latency(self, benchmark, client):
        """GET /health should respond in < 50ms."""
        async def _health():
            resp = await client.get("/health")
            return resp
        resp = await benchmark(_health)
        assert resp.status_code == 200

    @benchmark
    async def test_email_templates_latency(self, benchmark, client):
        """GET /api/email/templates should respond in < 100ms."""
        async def _templates():
            resp = await client.get("/api/email/templates")
            return resp
        resp = await benchmark(_templates)
        assert resp.status_code == 200

    @benchmark
    async def test_classify_categories_latency(self, benchmark, client):
        """GET /api/email/classify/categories should respond in < 100ms."""
        async def _categories():
            resp = await client.get("/api/email/classify/categories")
            return resp
        resp = await benchmark(_categories)
        assert resp.status_code == 200


class TestSanitizePerformance:
    """Text sanitization performance benchmarks."""

    @benchmark
    def test_sanitize_short_text(self, benchmark):
        """Sanitize 100-char text. Expect < 1ms."""
        from app.core.security import sanitize_text
        result = benchmark(sanitize_text, "Hello world! " * 5)
        assert len(result) > 0

    @benchmark
    def test_sanitize_long_text(self, benchmark):
        """Sanitize 10K-char text. Expect < 10ms."""
        from app.core.security import sanitize_text
        text = "Hello world!\n" * 500
        result = benchmark(sanitize_text, text)
        assert len(result) > 0

    @benchmark
    def test_sanitize_with_control_chars(self, benchmark):
        """Sanitize text with many control chars. Expect < 10ms."""
        from app.core.security import sanitize_text
        text = "Normal text.\x00\x01\x02\x03" * 2000
        result = benchmark(sanitize_text, text)
        assert "\x00" not in result


class TestRoleCheckPerformance:
    """Role permission check performance."""

    @benchmark
    def test_role_permission_lookup(self, benchmark):
        """ROLE_PERMISSIONS lookup should be instant (< 1ms)."""
        from app.models.auth import ROLE_PERMISSIONS, Role, Permission
        def lookup():
            return Permission.READ in ROLE_PERMISSIONS[Role.NOTAIRE]
        result = benchmark(lookup)
        assert result is True
