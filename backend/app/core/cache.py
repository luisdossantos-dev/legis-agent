"""
Simple in-memory TTL cache for repetitive operations.

Uses functools.lru_cache for zero-overhead caching of pure functions
and a manual TTL cache for operations that need periodic refresh.

Usage:
    from app.core.cache import ttl_cache

    @ttl_cache(ttl_seconds=300)
    def get_expensive_data():
        ...
"""

import functools
import time
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")

# ── Decorator: TTL cache ────────────────────────────────────────


def ttl_cache(ttl_seconds: int = 300) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that caches a function's return value for *ttl_seconds*.

    After the TTL expires, the next call recomputes the value.
    Thread-safe via the GIL for pure functions.

    Usage:
        @ttl_cache(ttl_seconds=60)
        def get_email_templates():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache: Dict[str, tuple[float, T]] = {}

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Build a simple cache key from args/kwargs
            key = str(args) + str(sorted(kwargs.items()))

            now = time.monotonic()
            if key in cache:
                expires_at, value = cache[key]
                if now < expires_at:
                    return value

            value = func(*args, **kwargs)
            cache[key] = (now + ttl_seconds, value)
            return value

        # Expose cache control so callers can invalidate if needed
        wrapper.invalidate = lambda: cache.clear()  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ── Pre-configured caches ───────────────────────────────────────


def cached_result(ttl_seconds: int = 300) -> dict:
    """
    Simple mutable cache container for manual cache control.

    Returns a dict with:
      - "value": the cached result (None if not cached)
      - "expires_at": monotonic timestamp when the cache expires
      - "valid": bool indicating if the cache is still fresh

    Callers use their own logic to check and populate the cache.
    """
    return {"value": None, "expires_at": 0.0, "ttl": ttl_seconds}


def cache_get(cache: dict) -> Any:
    """Get the cached value if still valid, else None."""
    if cache["value"] is not None and time.monotonic() < cache["expires_at"]:
        return cache["value"]
    return None


def cache_set(cache: dict, value: Any) -> None:
    """Set the cached value with the configured TTL."""
    cache["value"] = value
    cache["expires_at"] = time.monotonic() + cache["ttl"]


# ── Async TTL cache ────────────────────────────────────────────


class async_ttl_cache:
    """
    Decorator that caches an async function's return value for *ttl_seconds*.

    Usage:
        @async_ttl_cache(ttl_seconds=300)
        async def expensive_operation(key: str) -> Result:
            ...

    Supports cache invalidation via `.invalidate()` on the wrapped function.
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple[float, Any]] = {}

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        cache = self._cache
        ttl = self.ttl_seconds

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = str(args) + str(sorted(kwargs.items()))
            now = time.monotonic()
            if key in cache:
                expires_at, value = cache[key]
                if now < expires_at:
                    return value

            value = await func(*args, **kwargs)
            cache[key] = (now + ttl, value)
            return value

        wrapper.invalidate = lambda: cache.clear()  # type: ignore[attr-defined]
        return wrapper
