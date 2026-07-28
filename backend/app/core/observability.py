"""
Observability module — Langfuse + custom metrics + Prometheus.

Tracks:
  - Agent executions (full trace tree)
  - Tool calls (input, output, cost, latency)
  - Routing decisions (why a model was chosen)
  - Errors and retries
  - Cost per model/provider

Metrics exposed via:
  - GET /api/v1/observability/stats   (in-memory JSON, resets on restart)
  - GET /api/v1/observability/metrics (Prometheus, survives restarts if scraped)
  - Langfuse traces                   (persistent, requires credentials)
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.request_id import get_current_request_id


# ── Prometheus metrics ─────────────────────────────────────────

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Dummy no-op stubs so the rest of the module works without prometheus_client
    class _NoopMetric:
        def labels(self, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def observe(self, amount):
            pass
        def set(self, value):
            pass

    class _NoopRegistry:
        def get_sample_value(self, name):
            return None

    def generate_latest():
        return b""

    REGISTRY = _NoopRegistry()


if PROMETHEUS_AVAILABLE:
    # LLM call counters
    llm_calls_total = Counter(
        "legis_llm_calls_total",
        "Total LLM calls by provider, model, operation, and success",
        ["provider", "model", "operation", "success"],
    )
    llm_tokens_total = Counter(
        "legis_llm_tokens_total",
        "Total LLM tokens by provider and direction",
        ["provider", "direction"],
    )
    llm_cost_total = Counter(
        "legis_llm_cost_usd_total",
        "Total LLM cost in USD by provider",
        ["provider"],
    )
    llm_latency_seconds = Histogram(
        "legis_llm_latency_seconds",
        "LLM call latency in seconds by operation",
        ["operation"],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf")),
    )

    # Routing counters
    routing_decisions_total = Counter(
        "legis_routing_decisions_total",
        "Total routing decisions by profile",
        ["profile"],
    )

    # Error and retry counters
    errors_total = Counter(
        "legis_errors_total",
        "Total errors by operation",
        ["operation"],
    )
    retries_total = Counter(
        "legis_retries_total",
        "Total retry attempts by operation",
        ["operation"],
    )

    # Health gauge: 1 = running, 0 = not
    up_gauge = Gauge("legis_up", "Backend is running and responsive")
    up_gauge.set(1)
else:
    # Dummy metric references when prometheus-client is not installed
    class _DummyMetrics:
        pass
    llm_calls_total = _NoopMetric()
    llm_tokens_total = _NoopMetric()
    llm_cost_total = _NoopMetric()
    llm_latency_seconds = _NoopMetric()
    routing_decisions_total = _NoopMetric()
    errors_total = _NoopMetric()
    retries_total = _NoopMetric()
    up_gauge = _NoopMetric()

logger = logging.getLogger(__name__)


# ── Langfuse client ───────────────────────────────────────────

_langfuse = None


def get_langfuse():
    """Get the Langfuse client instance (initialized on first call)."""
    global _langfuse
    if _langfuse is not None:
        return _langfuse

    if not (settings.LANGFUSE_PUBLIC_KEY.strip() and settings.LANGFUSE_SECRET_KEY.strip()):
        return None

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning("Langfuse package not installed")
        return None

    try:
        import os
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST
        _langfuse = Langfuse()
        logger.info("🔍 Langfuse observability initialized")
        return _langfuse
    except (OSError, ConnectionError, ValueError) as e:
        logger.warning("Langfuse init failed: %s", e)
        return None


# ── In-memory metrics store ───────────────────────────────────

class MetricsStore:
    """
    In-memory metrics store for observability.

    Stores per-minute aggregates of:
      - Cost per model/provider
      - Latency per operation
      - Token counts
      - Success/failure rates
      - Routing decisions
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.cost_by_provider: Dict[str, float] = defaultdict(float)
        self.cost_by_model: Dict[str, float] = defaultdict(float)
        self.latency_by_op: Dict[str, list] = defaultdict(list)
        self.tokens_by_provider: Dict[str, Dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
        self.routing_decisions: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.retries: List[Dict[str, Any]] = []
        self.operation_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.start_time = datetime.now(timezone.utc)
        # Time-series data for dashboard charts
        self.cost_by_day: Dict[str, float] = defaultdict(float)  # "YYYY-MM-DD" -> cost
        self.calls_by_hour: Dict[str, int] = defaultdict(int)    # "YYYY-MM-DD HH:00" -> count
        self.model_usage: Dict[str, int] = defaultdict(int)      # model_name -> call count
        self.latency_samples: List[float] = []                   # raw latency for distribution

    def record_llm_call(
        self,
        provider: str,
        model: str,
        operation: str,
        latency_ms: float,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Record an LLM call."""
        self.operation_counts[operation] += 1
        self.latency_by_op[operation].append(latency_ms)
        self.cost_by_provider[provider] += cost_usd
        self.cost_by_model[model] += cost_usd
        self.tokens_by_provider[provider]["input"] += tokens_input
        self.tokens_by_provider[provider]["output"] += tokens_output
        # Time-series tracking
        now = datetime.now(timezone.utc)
        day_key = now.strftime("%Y-%m-%d")
        hour_key = now.strftime("%Y-%m-%d %H:00")
        self.cost_by_day[day_key] += cost_usd
        self.calls_by_hour[hour_key] += 1
        self.model_usage[model] += 1
        self.latency_samples.append(latency_ms)

        if success:
            self.success_counts[operation] += 1
        else:
            self.failure_counts[operation] += 1
            if error:
                self.errors.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_id": get_current_request_id()[:12],
                    "operation": operation,
                    "provider": provider,
                    "model": model,
                    "error": error[:200],
                })

    def record_routing(self, profile: str, reason: str, messages_count: int) -> None:
        """Record a routing decision."""
        self.routing_decisions.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": get_current_request_id()[:12],
            "profile": profile,
            "reason": reason,
            "messages_count": messages_count,
        })

    def record_retry(self, operation: str, attempt: int, error: str) -> None:
        """Record a retry attempt."""
        self.retries.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": get_current_request_id()[:12],
            "operation": operation,
            "attempt": attempt,
            "error": error[:200],
        })

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics."""
        now = datetime.now(timezone.utc)
        uptime = (now - self.start_time).total_seconds()

        # Latency percentiles
        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            idx = int(len(sorted_data) * p / 100)
            return round(sorted_data[min(idx, len(sorted_data) - 1)], 1)

        latency_stats = {}
        for op, times in self.latency_by_op.items():
            latency_stats[op] = {
                "p50": percentile(times, 50),
                "p95": percentile(times, 95),
                "p99": percentile(times, 99),
                "count": len(times),
                "avg": round(sum(times) / len(times), 1) if times else 0,
            }

        # Success rates
        success_rates = {}
        all_ops = set(self.success_counts.keys()) | set(self.failure_counts.keys())
        for op in all_ops:
            total = self.success_counts[op] + self.failure_counts[op]
            success_rates[op] = {
                "rate": round(self.success_counts[op] / total * 100, 1) if total else 0,
                "success": self.success_counts[op],
                "failure": self.failure_counts[op],
            }

        # Budget alert: monthly estimate
        total_cost = sum(self.cost_by_provider.values())
        monthly_estimate = (total_cost / max(uptime, 1)) * 3600 * 24 * 30 if uptime > 0 else 0

        # Time-series: daily cost (last 30 days)
        today = now.strftime("%Y-%m-%d")
        daily_cost = []
        for i in range(30):
            from datetime import timedelta
            day = (now - timedelta(days=29 - i)).strftime("%Y-%m-%d")
            daily_cost.append({
                "date": day,
                "cost": round(self.cost_by_day.get(day, 0), 6),
                "calls": self.calls_by_hour.get(day + " 00:00", 0),  # approximate
            })

        # Count calls per day from hourly data
        day_counts: Dict[str, int] = defaultdict(int)
        for hour_key, count in self.calls_by_hour.items():
            day = hour_key.split(" ")[0]
            day_counts[day] += count
        for entry in daily_cost:
            entry["calls"] = day_counts.get(entry["date"], 0)

        # Model usage breakdown
        model_usage_list = [
            {"model": model, "calls": count}
            for model, count in sorted(self.model_usage.items(), key=lambda x: x[1], reverse=True)
        ]

        # Latency distribution (bucketed)
        latency_dist = {
            "0-1s": 0, "1-2s": 0, "2-5s": 0, "5-10s": 0, "10-30s": 0, ">30s": 0
        }
        for ms in self.latency_samples:
            s = ms / 1000
            if s < 1: latency_dist["0-1s"] += 1
            elif s < 2: latency_dist["1-2s"] += 1
            elif s < 5: latency_dist["2-5s"] += 1
            elif s < 10: latency_dist["5-10s"] += 1
            elif s < 30: latency_dist["10-30s"] += 1
            else: latency_dist[">30s"] += 1

        return {
            "uptime_seconds": round(uptime),
            "total_cost_usd": round(total_cost, 6),
            "monthly_estimate_usd": round(monthly_estimate, 2),
            "total_operations": sum(self.operation_counts.values()),
            "cost_by_provider": dict(self.cost_by_provider),
            "cost_by_model": dict(self.cost_by_model),
            "latency_by_operation": latency_stats,
            "tokens_by_provider": dict(self.tokens_by_provider),
            "success_rates": success_rates,
            "total_errors": len(self.errors),
            "total_retries": len(self.retries),
            "routing_decisions_count": len(self.routing_decisions),
            "recent_errors": self.errors[-10:],
            "recent_routing": self.routing_decisions[-10:],
            # Dashboard-specific time-series data
            "daily_cost": daily_cost,
            "model_usage": model_usage_list,
            "latency_distribution": latency_dist,
            "total_tokens": sum(t["input"] + t["output"] for t in self.tokens_by_provider.values()),
        }


# Singleton
metrics = MetricsStore()


# ── Integration helpers ───────────────────────────────────────


def trace_routing(profile: str, reason: str, messages_count: int = 0) -> None:
    """Record a routing decision (called by routing.py)."""
    metrics.record_routing(profile, reason, messages_count)

    # Prometheus counter
    routing_decisions_total.labels(profile=profile).inc()

    # Also create a Langfuse event if available (non-critical — log only on failure)
    lf = get_langfuse()
    if lf:
        try:
            lf.trace(
                name="routing_decision",
                input={"profile": profile, "reason": reason},
                metadata={"messages_count": messages_count},
            )
        except (OSError, ConnectionError, ValueError) as e:
            logger.debug("Langfuse routing trace failed: %s", e)


def trace_llm_call(
    provider: str,
    model: str,
    operation: str,
    latency_ms: float,
    tokens_input: int = 0,
    tokens_output: int = 0,
    cost_usd: float = 0.0,
    success: bool = True,
    error: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """Record an LLM call (called by llm.py after completion)."""
    metrics.record_llm_call(
        provider=provider,
        model=model,
        operation=operation,
        latency_ms=latency_ms,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_usd=cost_usd,
        success=success,
        error=error,
    )

    # Prometheus metrics (best-effort, no crash on failure)
    try:
        success_str = "1" if success else "0"
        llm_calls_total.labels(
            provider=provider, model=model, operation=operation, success=success_str
        ).inc()
        llm_tokens_total.labels(provider=provider, direction="input").inc(tokens_input)
        llm_tokens_total.labels(provider=provider, direction="output").inc(tokens_output)
        llm_cost_total.labels(provider=provider).inc(cost_usd)
        llm_latency_seconds.labels(operation=operation).observe(latency_ms / 1000.0)
        if not success:
            errors_total.labels(operation=operation).inc()
    except Exception:
        logger.debug("Prometheus metric update failed (non-critical)")


def trace_retry(operation: str, attempt: int, error: str) -> None:
    """Record a retry attempt (called by agent_tools.py)."""
    metrics.record_retry(operation, attempt, error)

    # Prometheus counter
    retries_total.labels(operation=operation).inc()


# ── Cost estimation for observability ─────────────────────────

# Approximate pricing per 1M tokens (input / output)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "deepseek-v4-flash": {"input": 0.50, "output": 2.00},
    "mistral-large": {"input": 2.00, "output": 6.00},
}


# ── Langfuse scoring ───────────────────────────────────────────

# Score thresholds for quality evaluation
QUALITY_THRESHOLDS = {
    "relevance": 0.7,      # Response must be relevant to the query
    "completeness": 0.8,   # Response must cover all requested aspects
    "formatting": 0.7,     # Response must follow the expected format
    "factual_accuracy": 0.8, # Response must not contain hallucinations
}


def score_llm_response(
    trace_id: str,
    response: str,
    query: str,
    operation: str = "llm_complete",
    expected_format: Optional[str] = None,
) -> Dict[str, float]:
    """
    Score an LLM response using Langfuse scores.

    Evaluates the response on multiple dimensions:
    - relevance: How well the response addresses the query
    - completeness: Coverage of all requested aspects
    - format_compliance: Adherence to expected output format
    - no_hallucination: Absence of fabricated information

    Args:
        trace_id: Langfuse trace ID to attach scores to.
        response: The LLM response text.
        query: The original user query.
        operation: The operation type for scoring context.
        expected_format: Expected output format hint ("json", "email", "clause", etc.)

    Returns:
        Dict of score names to values (0.0 to 1.0).
        Returns all zeros if Langfuse is unavailable.
    """
    lf = get_langfuse()
    if not lf:
        return {k: 0.0 for k in QUALITY_THRESHOLDS}

    if not response or not query:
        return {k: 0.0 for k in QUALITY_THRESHOLDS}

    try:
        # Basic heuristic scores (can be enhanced with LLM-as-judge)
        scores = {}

        # Relevance: check that key terms from the query appear in the response
        query_terms = set(query.lower().split())
        response_lower = response.lower()
        term_overlap = sum(1 for t in query_terms if len(t) > 3 and t in response_lower)
        relevant_terms = sum(1 for t in query_terms if len(t) > 3)
        scores["relevance"] = round(term_overlap / max(relevant_terms, 1), 2)

        # Completeness: response length as a proxy (short = probably incomplete)
        min_expected = 50 if operation == "routing" else 200
        length_ratio = min(len(response) / max(min_expected, 200), 1.0)
        scores["completeness"] = round(length_ratio, 2)

        # Format compliance: check response structure
        if expected_format == "json":
            import json as _json
            try:
                _json.loads(response)
                scores["format_compliance"] = 1.0
            except (_json.JSONDecodeError, ValueError):
                scores["format_compliance"] = 0.0
        elif expected_format == "email":
            has_subject = "subject:" in response_lower or "objet:" in response_lower
            has_greeting = any(g in response_lower for g in ["bonjour", "cher", "madame", "monsieur", "dear", "hello"])
            scores["format_compliance"] = 1.0 if (has_subject and has_greeting) else 0.5 if (has_subject or has_greeting) else 0.0
        elif expected_format == "clause":
            has_structure = any(s in response_lower for s in ["article", "clause", "section", "§"])
            scores["format_compliance"] = 1.0 if has_structure else 0.5
        else:
            scores["format_compliance"] = 0.5  # neutral for free-form text

        # No hallucination: check for common hallucination patterns
        hallucination_indicators = [
            "i don't have access", "i cannot provide", "as an ai",
            "as a language model", "i am an ai", "i do not have",
        ]
        has_hallucination_indicator = any(h in response_lower for h in hallucination_indicators)
        scores["no_hallucination"] = 0.0 if has_hallucination_indicator else 1.0

        # Send scores to Langfuse
        for name, value in scores.items():
            try:
                lf.score(
                    trace_id=trace_id,
                    name=name,
                    value=value,
                    comment=f"auto-eval (heuristic) for {operation}",
                )
            except (OSError, ConnectionError, ValueError):
                logger.debug("Langfuse score failed for %s", name)

        logger.debug(
            "Langfuse scores for %s: relevance=%.2f completeness=%.2f format=%.2f hallucination=%.2f",
            trace_id[:8],
            scores.get("relevance", 0),
            scores.get("completeness", 0),
            scores.get("format_compliance", 0),
            scores.get("no_hallucination", 0),
        )

        return scores

    except Exception as e:
        logger.debug("Failed to score LLM response: %s", e)
        return {k: 0.0 for k in QUALITY_THRESHOLDS}


def estimate_call_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    """Estimate the cost of an LLM call based on token counts."""
    # Find matching pricing
    pricing = None
    for key, prices in MODEL_PRICING.items():
        if key in model.lower():
            pricing = prices
            break

    if not pricing:
        # Default: gpt-4o pricing
        pricing = {"input": 2.50, "output": 10.00}

    input_cost = (tokens_input / 1_000_000) * pricing["input"]
    output_cost = (tokens_output / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)
