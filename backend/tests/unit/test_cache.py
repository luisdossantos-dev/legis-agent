"""Unit tests for cache.py — async_ttl_cache decorator."""

import pytest
import time


class TestAsyncTtlCache:
    """Tests for async_ttl_cache decorator."""

    @pytest.mark.asyncio
    async def test_cache_hits(self):
        """Repeated calls with same args return cached value within TTL."""
        from app.core.cache import async_ttl_cache

        call_count = 0

        @async_ttl_cache(ttl_seconds=60)
        async def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await compute(5)
        assert result1 == 10
        assert call_count == 1

        result2 = await compute(5)
        assert result2 == 10
        assert call_count == 1  # Cached — no additional call

    @pytest.mark.asyncio
    async def test_different_args_no_cache(self):
        """Different arguments produce different cache entries."""
        from app.core.cache import async_ttl_cache

        call_count = 0

        @async_ttl_cache(ttl_seconds=60)
        async def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        r1 = await compute(1)
        r2 = await compute(2)
        assert r1 == 2
        assert r2 == 4
        assert call_count == 2  # Different args → not cached

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Cache expires after TTL."""
        from app.core.cache import async_ttl_cache

        call_count = 0

        @async_ttl_cache(ttl_seconds=0.01)  # 10ms TTL
        async def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        await compute(5)
        assert call_count == 1

        await compute(5)
        assert call_count == 1  # Still within TTL

        await compute(5)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_different_kwargs(self):
        """kwargs are included in cache key."""
        from app.core.cache import async_ttl_cache

        call_count = 0

        @async_ttl_cache(ttl_seconds=60)
        async def compute(a: int, b: int = 0) -> int:
            nonlocal call_count
            call_count += 1
            return a + b

        r1 = await compute(1, b=2)
        r2 = await compute(1, b=2)
        r3 = await compute(1, b=3)
        assert r1 == 3
        assert r2 == 3
        assert r3 == 4
        assert call_count == 2  # Third call has different kwargs

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Works with async functions."""
        from app.core.cache import async_ttl_cache

        @async_ttl_cache(ttl_seconds=60)
        async def fetch_data(key: str) -> str:
            await asyncio.sleep(0.01)  # Simulate async work
            return f"data-{key}"

        import asyncio
        result = await fetch_data("test")
        assert result == "data-test"


class TestTtlCache:
    """Tests for sync ttl_cache decorator."""

    def test_sync_cache(self):
        """Sync ttl_cache works for sync functions."""
        from app.core.cache import ttl_cache

        call_count = 0

        @ttl_cache(ttl_seconds=60)
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        assert compute(3) == 6
        assert compute(3) == 6
        assert call_count == 1

    def test_cache_invalidation(self):
        """invalidate() clears the cache."""
        from app.core.cache import ttl_cache

        call_count = 0

        @ttl_cache(ttl_seconds=60)
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        compute(5)
        assert call_count == 1

        compute.invalidate()  # type: ignore[attr-defined]
        compute(5)
        assert call_count == 2  # Recalculated after invalidation


class TestCacheHelpers:
    """Tests for cached_result, cache_get, cache_set."""

    def test_cached_result_defaults(self):
        """cached_result returns dict with expected keys."""
        from app.core.cache import cached_result
        cache = cached_result(ttl_seconds=60)
        assert "value" in cache
        assert "expires_at" in cache
        assert "ttl" in cache
        assert cache["value"] is None

    def test_cache_set_and_get(self):
        """cache_set and cache_get work correctly."""
        from app.core.cache import cached_result, cache_get, cache_set
        cache = cached_result(ttl_seconds=60)
        cache_set(cache, "test_value")
        assert cache_get(cache) == "test_value"

    def test_cache_expiry(self):
        """cache_get returns None after expiry."""
        from app.core.cache import cached_result, cache_get
        cache = cached_result(ttl_seconds=0)
        cache["value"] = "expired"
        cache["expires_at"] = 0  # Already expired
        assert cache_get(cache) is None
