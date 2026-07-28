"""
Circuit breaker pattern for resilient external service calls.

Prevents cascading failures by stopping calls to a failing service
after a threshold of consecutive failures, allowing recovery time.

States:
  CLOSED   — normal operation, requests pass through
  OPEN     — failures exceeded threshold, requests are rejected immediately
  HALF_OPEN — recovery timeout elapsed, limited test requests allowed

Usage:
    cb = CircuitBreaker("llm", failure_threshold=5, recovery_timeout=30.0)

    async with cb:
        result = await call_llm(...)

    # Or with explicit call:
    result = await cb.call(call_llm, arg1, arg2)
"""

import asyncio
import logging
import time
from enum import Enum
from collections.abc import Awaitable, Callable
from typing import Any, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Async circuit breaker with configurable thresholds.

    Thread-safe via asyncio.Lock. Each circuit breaker is identified by
    a name for logging and observability.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        """
        Args:
            name: Service name (used in logs).
            failure_threshold: Consecutive failures before opening the circuit.
            recovery_timeout: Seconds to wait before transitioning to HALF_OPEN.
            half_open_max_calls: Successful probes needed to close the circuit.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_successes = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    # ── Public API ─────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        """Current circuit state (read-only, use in logs/metrics)."""
        return self._state

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """
        Execute *func* guarded by the circuit breaker.

        Raises CircuitBreakerOpenError if the circuit is OPEN.
        """
        async with self._lock:
            self._check_recovery_timeout()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' is OPEN. "
                    f"Failure count: {self._failure_count}/{self.failure_threshold}. "
                    f"Retry after {self._remaining_cooldown():.1f}s."
                )
            if self._state == CircuitState.HALF_OPEN and self._half_open_successes >= self.half_open_max_calls:
                # Already enough successes in half-open — close the circuit
                self._close()

        try:
            result = await func(*args, **kwargs)
        except Exception as e:
            async with self._lock:
                self._on_failure()
            raise e

        async with self._lock:
            self._on_success()
        return result

    async def __aenter__(self) -> "CircuitBreaker":
        """Context manager entry — checks circuit state."""
        async with self._lock:
            self._check_recovery_timeout()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' is OPEN. "
                    f"Retry after {self._remaining_cooldown():.1f}s."
                )
            if self._state == CircuitState.HALF_OPEN and self._half_open_successes >= self.half_open_max_calls:
                self._close()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Context manager exit — records success or failure."""
        if exc_type is None:
            async with self._lock:
                self._on_success()
        elif exc_type is not asyncio.CancelledError:
            async with self._lock:
                self._on_failure()

    # ── Internal helpers ───────────────────────────────────────

    def _close(self) -> None:
        """Transition to CLOSED state."""
        if self._state != CircuitState.CLOSED:
            logger.info("🟢 Circuit '%s' CLOSED (recovered)", self.name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_successes = 0
        self._last_failure_time = None

    def _open(self) -> None:
        """Transition to OPEN state."""
        if self._state != CircuitState.OPEN:
            logger.warning(
                "🔴 Circuit '%s' OPEN — %d consecutive failures",
                self.name, self.failure_threshold,
            )
        self._state = CircuitState.OPEN
        self._last_failure_time = time.monotonic()

    def _half_open(self) -> None:
        """Transition to HALF_OPEN state (recovery probe)."""
        if self._state != CircuitState.HALF_OPEN:
            logger.info("🟡 Circuit '%s' HALF_OPEN — testing recovery", self.name)
        self._state = CircuitState.HALF_OPEN
        self._half_open_successes = 0

    def _on_success(self) -> None:
        """Handle a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.half_open_max_calls:
                self._close()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # A single failure in half-open re-opens the circuit
            self._open()
        elif self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold:
            self._open()

    def _check_recovery_timeout(self) -> None:
        """Transition OPEN → HALF_OPEN if recovery timeout elapsed."""
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._half_open()

    def _remaining_cooldown(self) -> float:
        """Seconds remaining until recovery timeout."""
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        return max(0.0, self.recovery_timeout - elapsed)

    async def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        async with self._lock:
            self._close()

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker('{self.name}', "
            f"state={self._state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""
    pass


# ── Pre-configured circuit breakers for known services ──────────

# LLM provider circuit: aggressive because LLM calls are expensive
# and repeated failures waste time and tokens
llm_circuit_breaker = CircuitBreaker(
    name="llm",
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=2,
)

# Vector store circuit: more lenient (non-critical path for reads)
vector_store_circuit_breaker = CircuitBreaker(
    name="vector_store",
    failure_threshold=10,
    recovery_timeout=15.0,
    half_open_max_calls=3,
)
