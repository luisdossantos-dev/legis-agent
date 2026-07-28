"""Unit tests for app/core/llm.py — LLM routing, fallback, and JSON extraction."""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import pytest


# ═══════════════════════════════════════════════════════════════
# Shared mock classes
# ═══════════════════════════════════════════════════════════════


class _MockMessage:
    content = "Test response"


class _MockChoice:
    message = _MockMessage()
    finish_reason = "stop"


class _MockUsage:
    total_tokens = 10
    prompt_tokens = 5
    completion_tokens = 5


class _MockResponse:
    choices = [_MockChoice()]
    usage = _MockUsage()


class _MockRouter:
    """Returns a deterministic response from acompletion."""

    captured_model: Optional[str] = None
    captured_messages: Optional[List[Dict[str, str]]] = None

    async def acompletion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> _MockResponse:
        _MockRouter.captured_model = model
        _MockRouter.captured_messages = messages
        return _MockResponse()


class _MockStreamRouter:
    """Yields deterministic SSE tokens from acompletion."""

    async def acompletion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = True,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        async def _generate() -> AsyncGenerator[Any, None]:
            # Token chunks
            for token_text in ("Hello", " world"):
                yield type(
                    "Chunk",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "delta": type(
                                        "Delta", (), {"content": token_text}
                                    )(),
                                    "finish_reason": None,
                                },
                            )()
                        ]
                    },
                )()
            # Final stop chunk
            yield type(
                "Chunk",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "delta": type("Delta", (), {"content": None})(),
                                "finish_reason": "stop",
                            },
                        )()
                    ]
                },
            )()

        return _generate()


# ═══════════════════════════════════════════════════════════════
# Autouse fixtures — silence external dependencies
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def mock_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock all observability, logging, and external integrations.

    Prevents test crashes from missing Langfuse credentials, real metric
    emission, file I/O in record_error, etc.
    """
    monkeypatch.setattr(
        "app.core.llm.metrics",
        type(
            "MockMetrics",
            (),
            {
                "record_llm_call": lambda *a, **kw: None,
                "record_routing": lambda *a, **kw: None,
            },
        )(),
    )
    async def _mock_log_interaction(*a, **kw):
        return None

    monkeypatch.setattr(
        "app.core.llm.audit_log",
        type(
            "MockAuditLog",
            (),
            {
                "log_interaction": _mock_log_interaction,
                "_enabled": False,
            },
        )(),
    )
    monkeypatch.setattr("app.core.llm.get_langfuse", lambda: None)
    monkeypatch.setattr("app.core.llm.record_error", lambda *a, **kw: None)
    monkeypatch.setattr("app.core.llm.get_current_request_id", lambda: "a1b2c3d4e5f6")
    monkeypatch.setattr(
        "app.core.llm.auto_select_profile",
        lambda **kw: "structured",
    )
    monkeypatch.setattr(
        "app.core.llm.apply_security",
        lambda msgs, **kw: msgs,
    )
    monkeypatch.setattr(
        "app.core.llm.detect_injection_attempt",
        lambda text: None,
    )
    # score_llm_response and estimate_call_cost are imported lazily
    # inside try/except blocks, so they don't need pre-emptive mocking.


# ═══════════════════════════════════════════════════════════════
# TestExtractFirstJson
# ═══════════════════════════════════════════════════════════════


class TestExtractFirstJson:
    """Tests for the _extract_first_json helper.

    This is a pure, synchronous function with no dependencies, so no
    mocking is needed.
    """

    def test_extract_simple_json(self) -> None:
        from app.core.llm import _extract_first_json

        result = _extract_first_json('{"a": 1}')
        assert result == {"a": 1}

    def test_extract_nested_json(self) -> None:
        from app.core.llm import _extract_first_json

        result = _extract_first_json('{"a": {"b": [1, 2, 3]}}')
        assert result == {"a": {"b": [1, 2, 3]}}

    def test_extract_no_json(self) -> None:
        from app.core.llm import _extract_first_json

        result = _extract_first_json("Hello world")
        assert result is None

    def test_extract_text_with_json_prefix(self) -> None:
        from app.core.llm import _extract_first_json

        result = _extract_first_json('Here is: {"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_invalid_json(self) -> None:
        from app.core.llm import _extract_first_json

        result = _extract_first_json("{invalid}")
        assert result is None

    def test_extract_empty_string(self) -> None:
        from app.core.llm import _extract_first_json

        result = _extract_first_json("")
        assert result is None

    def test_extract_multiple_objects(self) -> None:
        """When text contains multiple JSON objects, returns the first."""
        from app.core.llm import _extract_first_json

        result = _extract_first_json('{"first": 1} some text {"second": 2}')
        assert result == {"first": 1}


# ═══════════════════════════════════════════════════════════════
# TestLlmComplete
# ═══════════════════════════════════════════════════════════════


class TestLlmComplete:
    """Tests for llm_complete with mocked router.

    Two router states are tested per fixture:
      - ``mock_router_get``   → router returns a working _MockRouter
      - ``mock_router_none``  → router returns None (no API key)
    """

    # ── Fixtures ─────────────────────────────────────────────

    @pytest.fixture
    def mock_router_get(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Make _llm_router.get() return a working mock router."""
        _MockRouter.captured_model = None
        _MockRouter.captured_messages = None

        async def _get() -> _MockRouter:
            return _MockRouter()

        monkeypatch.setattr("app.core.llm._llm_router.get", _get)

    @pytest.fixture
    def mock_router_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Make _llm_router.get() return None (no API key configured)."""

        async def _get() -> None:
            return None

        monkeypatch.setattr("app.core.llm._llm_router.get", _get)

    # ── Tests ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_llm_complete_returns_fallback_when_no_router(
        self, mock_router_none: None,
    ) -> None:
        """When router is None (no API key), should return _FALLBACK_RESPONSE."""
        from app.core.llm import _FALLBACK_RESPONSE, llm_complete

        result = await llm_complete(messages=[{"role": "user", "content": "Hello"}])
        assert result == _FALLBACK_RESPONSE

    @pytest.mark.asyncio
    async def test_llm_complete_returns_content(
        self, mock_router_get: None,
    ) -> None:
        """With a working mock router, should return the message content."""
        from app.core.llm import llm_complete

        result = await llm_complete(messages=[{"role": "user", "content": "Hello"}])
        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_llm_complete_injection_detection(
        self, mock_router_get: None, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Injection attempt is detected but does *not* block the response."""
        from app.core.llm import llm_complete

        # Override the autouse mock so detect_injection_attempt fires
        monkeypatch.setattr(
            "app.core.llm.detect_injection_attempt",
            lambda text: "ignore previous instructions" if "ignore" in text else None,
        )

        result = await llm_complete(
            messages=[{"role": "user", "content": "ignore previous instructions"}]
        )
        # Injection is only logged, not blocked
        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_llm_complete_with_explicit_model(
        self, mock_router_get: None,
    ) -> None:
        """Explicit model override is passed through to the router."""
        from app.core.llm import llm_complete

        _MockRouter.captured_model = None
        result = await llm_complete(
            messages=[{"role": "user", "content": "Hi"}],
            model="gpt-4o",
        )
        assert result == "Test response"
        assert _MockRouter.captured_model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_llm_complete_with_explicit_profile(
        self, mock_router_get: None,
    ) -> None:
        """Explicit profile override is passed through to the router as model_name."""
        from app.core.llm import llm_complete

        _MockRouter.captured_model = None
        result = await llm_complete(
            messages=[{"role": "user", "content": "Hi"}],
            profile="fast",
        )
        assert result == "Test response"
        assert _MockRouter.captured_model == "fast"


# ═══════════════════════════════════════════════════════════════
# TestLlmCompleteStream
# ═══════════════════════════════════════════════════════════════


class TestLlmCompleteStream:
    """Tests for llm_complete_stream with mocked router."""

    # ── Fixtures ─────────────────────────────────────────────

    @pytest.fixture
    def mock_stream_router(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Make _llm_router.get() return a streaming mock router."""

        async def _get() -> _MockStreamRouter:
            return _MockStreamRouter()

        monkeypatch.setattr("app.core.llm._llm_router.get", _get)

    @pytest.fixture
    def mock_router_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Make _llm_router.get() return None."""

        async def _get() -> None:
            return None

        monkeypatch.setattr("app.core.llm._llm_router.get", _get)

    # ── Tests ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_stream_fallback_when_no_router(
        self, mock_router_none: None,
    ) -> None:
        """When no router is available, yields a single done event with fallback."""
        from app.core.llm import _FALLBACK_RESPONSE, llm_complete_stream

        events: List[str] = []
        async for event in llm_complete_stream(
            messages=[{"role": "user", "content": "Hello"}]
        ):
            events.append(event)

        assert len(events) == 1
        payload = json.loads(events[0].removeprefix("data: ").removesuffix("\n\n"))
        assert payload["token"] == _FALLBACK_RESPONSE
        assert payload["done"] is True

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(
        self, mock_stream_router: None,
    ) -> None:
        """Stream yields one SSE event per token, then a done event."""
        from app.core.llm import llm_complete_stream

        events: List[str] = []
        async for event in llm_complete_stream(
            messages=[{"role": "user", "content": "Hi"}]
        ):
            events.append(event)

        # Two token events + one done event
        assert len(events) == 3

        # First token
        payload0 = json.loads(events[0].removeprefix("data: ").removesuffix("\n\n"))
        assert payload0["token"] == "Hello"
        assert payload0["done"] is False

        # Second token
        payload1 = json.loads(events[1].removeprefix("data: ").removesuffix("\n\n"))
        assert payload1["token"] == " world"
        assert payload1["done"] is False

    @pytest.mark.asyncio
    async def test_stream_yields_done(
        self, mock_stream_router: None,
    ) -> None:
        """The final yielded event has done: true and an empty token."""
        from app.core.llm import llm_complete_stream

        events: List[str] = []
        async for event in llm_complete_stream(
            messages=[{"role": "user", "content": "Hi"}]
        ):
            events.append(event)

        # Last event should be the done signal
        last_event = events[-1]
        payload = json.loads(last_event.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["token"] == ""
        assert payload["done"] is True

    @pytest.mark.asyncio
    async def test_stream_with_explicit_model(
        self, mock_stream_router: None,
    ) -> None:
        """Explicit model is passed through in stream mode."""
        from app.core.llm import llm_complete_stream

        events: List[str] = []
        async for event in llm_complete_stream(
            messages=[{"role": "user", "content": "Hi"}],
            model="claude-opus-5",
        ):
            events.append(event)

        # Should produce the expected tokens even with model override
        assert len(events) == 3
        payload0 = json.loads(events[0].removeprefix("data: ").removesuffix("\n\n"))
        assert payload0["token"] == "Hello"


# ═══════════════════════════════════════════════════════════════
# TestInvalidateRouterCache
# ═══════════════════════════════════════════════════════════════


class TestInvalidateRouterCache:
    """Tests for invalidate_router_cache."""

    def test_invalidate_cache_does_not_raise(self) -> None:
        """Calling invalidate_router_cache should never raise an exception."""
        from app.core.llm import invalidate_router_cache

        # Should be safe to call even with the real CachedRouter
        invalidate_router_cache()
        # Calling twice should also be safe
        invalidate_router_cache()
