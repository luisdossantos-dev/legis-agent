"""
Alerting module for production monitoring.

Sends notifications via webhook (Slack, Discord, generic) when
configured thresholds are exceeded. Falls back to logging-only
when no webhook URL is configured — useful for development.

Fire-and-forget: all HTTP calls are async with short timeouts
so alerting never blocks the main request path.

Usage:
    from app.core.alerter import alerter

    # Check threshold-based rules and fire alerts if needed
    await alerter.check_and_alert()
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Alert severity levels ───────────────────────────────────────

class AlertSeverity:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ── Alert payload ───────────────────────────────────────────────

@dataclass
class Alert:
    """A single alert event."""
    title: str
    message: str
    severity: str = AlertSeverity.WARNING
    source: str = "legis-agent"
    timestamp: float = field(default_factory=time.time)


# ── Alert channel: webhook ─────────────────────────────────────

async def _send_slack_webhook(webhook_url: str, alert: Alert) -> bool:
    """Send an alert as a Slack message via Incoming Webhook."""
    color_map = {
        AlertSeverity.INFO: "#36a64f",
        AlertSeverity.WARNING: "#f59e0b",
        AlertSeverity.CRITICAL: "#ef4444",
    }
    payload = {
        "attachments": [
            {
                "color": color_map.get(alert.severity, "#cccccc"),
                "title": alert.title,
                "text": alert.message,
                "footer": alert.source,
                "ts": int(alert.timestamp),
            }
        ]
    }
    return await _send_json_to_webhook(webhook_url, payload)


async def _send_generic_webhook(webhook_url: str, alert: Alert) -> bool:
    """Send an alert as a generic JSON payload."""
    payload = {
        "title": alert.title,
        "message": alert.message,
        "severity": alert.severity,
        "source": alert.source,
        "timestamp": alert.timestamp,
    }
    return await _send_json_to_webhook(webhook_url, payload)


# Shared HTTP client with connection pooling — reused across all
# outbound HTTP calls from the alerter (webhooks, health checks).
# Pool limits keep resource usage bounded while avoiding the overhead
# of creating a new TCP connection per request.
_http_client: httpx.AsyncClient | None = None
_HTTP_CLIENT_LIMITS = httpx.Limits(
    max_keepalive_connections=5,
    max_connections=10,
    keepalive_expiry=30.0,
)


def _get_http_client() -> httpx.AsyncClient:
    """Return a shared AsyncClient with connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            limits=_HTTP_CLIENT_LIMITS,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
    return _http_client


async def _send_json_to_webhook(url: str, payload: Dict[str, Any]) -> bool:
    """POST a JSON payload to a webhook URL with a short timeout."""
    client = _get_http_client()
    try:
        resp = await client.post(url, json=payload)
        if resp.status_code not in (200, 201, 202, 204):
            logger.warning(
                "Webhook returned HTTP %d for alert: %s",
                resp.status_code,
                payload.get("title", ""),
            )
            return False
        return True
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
        logger.warning("Webhook request failed: %s", e)
        return False


# ── Alert cooldown tracker ──────────────────────────────────────

class CooldownTracker:
    """Tracks the last time each alert type was sent to avoid spam."""

    def __init__(self, default_cooldown: float = 300.0):
        self._cooldown = default_cooldown
        self._sent: Dict[str, float] = {}

    def can_send(self, alert_key: str) -> bool:
        """Check if enough time has passed since the last alert of this type."""
        now = time.monotonic()
        last = self._sent.get(alert_key, 0.0)
        return (now - last) >= self._cooldown

    def mark_sent(self, alert_key: str) -> None:
        """Record that an alert was sent now."""
        self._sent[alert_key] = time.monotonic()

    @property
    def cooldown(self) -> float:
        return self._cooldown


# ── Alerter ─────────────────────────────────────────────────────

class Alerter:
    """
    Central alert coordinator.

    Checks health conditions and sends notifications through
    configured channels with cooldown-based spam protection.

    When no webhook URL is configured, alerts are logged only.
    """

    def __init__(self) -> None:
        self._cooldown = CooldownTracker(
            default_cooldown=settings.ALERT_COOLDOWN_SECONDS,
        )
        self._last_known_healthy: Optional[bool] = None
        self._last_known_error_count: int = 0

    # ── Public API ──────────────────────────────────────────────

    async def check_and_alert(self) -> None:
        """
        Evaluate all alert rules and fire notifications for any
        thresholds that have been exceeded.

        Safe to call on every request (stateless checks, cooldown
        prevents spam).
        """
        await self._check_health()
        await self._check_error_rate()
        await self._check_circuit_breakers()

    async def alert(
        self,
        title: str,
        message: str,
        severity: str = AlertSeverity.WARNING,
    ) -> None:
        """
        Fire an immediate alert bypassing threshold checks.

        Cooldown is still applied per alert_key (derived from title)
        to prevent spam from repeated calls.
        """
        alert = Alert(title=title, message=message, severity=severity)
        await self._dispatch(alert)

    # ── Rule checks ─────────────────────────────────────────────

    async def _check_health(self) -> None:
        """Check if the backend health endpoint responds successfully."""
        client = _get_http_client()
        try:
            resp = await client.get("http://localhost:8000/health")
            healthy = resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutError):
            healthy = False

        # State transition: healthy → unhealthy
        if not healthy and self._last_known_healthy is not False:
            await self._dispatch(Alert(
                title="🚨 Backend health check failed",
                message=(
                    f"The /health endpoint did not return 200 OK. "
                    f"The backend may be down or unresponsive. "
                    f"Check the service status and logs immediately."
                ),
                severity=AlertSeverity.CRITICAL,
            ))
        # Recovery: unhealthy → healthy
        elif healthy and self._last_known_healthy is False:
            await self._dispatch(Alert(
                title="✅ Backend recovered",
                message="The /health endpoint is responding normally again.",
                severity=AlertSeverity.INFO,
            ))

        self._last_known_healthy = healthy

    async def _check_error_rate(self) -> None:
        """Check if the accumulated error count exceeds the threshold."""
        threshold = settings.ALERT_ERROR_THRESHOLD
        if threshold <= 0:
            return

        from app.core.observability import metrics
        current_errors = metrics.get_stats().get("total_errors", 0)

        if current_errors >= threshold and self._last_known_error_count < threshold:
            await self._dispatch(Alert(
                title="⚠️ High error rate detected",
                message=(
                    f"The system has recorded {current_errors} errors "
                    f"(threshold: {threshold}). Review recent errors at "
                    f"/api/v1/observability/stats or the HTML dashboard."
                ),
                severity=AlertSeverity.WARNING,
            ))

        self._last_known_error_count = current_errors

    async def _check_circuit_breakers(self) -> None:
        """Check if any circuit breaker has opened."""
        if not settings.ALERT_ON_CIRCUIT_OPEN:
            return

        from app.core.circuit_breaker import (
            llm_circuit_breaker,
            vector_store_circuit_breaker,
        )

        for cb in (llm_circuit_breaker, vector_store_circuit_breaker):
            if cb.state.value == "open":
                await self._dispatch(Alert(
                    title=f"🔴 Circuit breaker open: {cb.name}",
                    message=(
                        f"The circuit breaker for '{cb.name}' is OPEN "
                        f"after {cb.failure_threshold} consecutive failures. "
                        f"Requests to this service are being rejected. "
                        f"Auto-recovery in {cb._remaining_cooldown():.0f}s."
                    ),
                    severity=AlertSeverity.CRITICAL,
                ))

    # ── Dispatch ────────────────────────────────────────────────

    async def _dispatch(self, alert: Alert) -> None:
        """
        Send an alert through all configured channels.

        Applies cooldown: if the same alert type was sent recently,
        this alert is suppressed (but still logged at DEBUG level).
        """
        alert_key = alert.title

        if not self._cooldown.can_send(alert_key):
            logger.debug(
                "Alert suppressed by cooldown: %s (%s)",
                alert.title, alert.severity,
            )
            return

        self._cooldown.mark_sent(alert_key)

        # Always log to the Python logger
        log_msg = f"[{alert.severity.upper()}] {alert.title} — {alert.message}"
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(log_msg)
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Send via webhook if configured
        webhook = settings.ALERT_WEBHOOK_URL.strip()
        if webhook:
            await _send_slack_webhook(webhook, alert)

    def reset_state(self) -> None:
        """Reset tracked state (useful for testing or manual recovery)."""
        self._last_known_healthy = None
        self._last_known_error_count = 0


# Singleton
alerter = Alerter()
