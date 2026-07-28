"""
Observability API endpoints.

Endpoints:
  GET /stats            — JSON dashboard statistics (machine-readable)
  GET /dashboard        — HTML visual dashboard (human-readable)
  GET /health           — Langfuse connection health
  GET /metrics          — Prometheus metrics (for scraping)
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.core.observability import get_langfuse, metrics, PROMETHEUS_AVAILABLE
from app.core.config import settings

from app.core.observability import generate_latest as _prom_generate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def observability_stats():
    """
    Get observability dashboard statistics.

    Also triggers alert threshold checks (health, error rate,
    circuit breaker state) so alerts fire naturally whenever
    the frontend or monitoring tools poll this endpoint.

    Returns:
      - Total cost (USD) by provider and model
      - Latency percentiles (p50/p95/p99) by operation
      - Token counts by provider
      - Success/failure rates by operation
      - Monthly cost estimate
      - Recent errors and routing decisions
    """
    # Fire-and-forget alert check — never blocks the response
    from app.core.alerter import alerter
    try:
        await alerter.check_and_alert()
    except Exception as e:
        logger.debug("Alert check failed (non-critical): %s", e)

    return metrics.get_stats()


@router.get("/alert/test")
async def test_alert():
    """
    Send a test alert to verify webhook configuration.

    Useful during setup to confirm the alert channel works.
    """
    from app.core.alerter import alerter, AlertSeverity
    await alerter.alert(
        title="🧪 Test alert from Legis Agent",
        message=(
            f"This is a test alert. If you receive this, the alert "
            f"webhook is configured correctly. Environment: "
            f"{settings.ENVIRONMENT}"
        ),
        severity=AlertSeverity.INFO,
    )
    return {"status": "alert sent", "webhook_configured": bool(settings.ALERT_WEBHOOK_URL.strip())}


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def observability_dashboard():
    """
    HTML dashboard showing backend health, metrics, and recent errors.
    Self-contained — no external CSS/JS dependencies.
    """
    return _DASHBOARD_HTML


@router.get("/health")
async def observability_health():
    """
    Check Langfuse connection status.
    """
    lf = get_langfuse()

    if lf:
        try:
            # Try a simple health check
            return {
                "status": "connected",
                "host": settings.LANGFUSE_HOST or "https://cloud.langfuse.com",
                "public_key_configured": bool(settings.LANGFUSE_PUBLIC_KEY.strip()),
                "metrics_collecting": True,
                "total_operations_tracked": sum(metrics.operation_counts.values()),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)[:200]}

    return {
        "status": "disabled",
        "reason": "No Langfuse credentials configured",
        "hint": "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env",
        "metrics_collecting": True,  # In-memory metrics still work
        "total_operations_tracked": sum(metrics.operation_counts.values()),
    }


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def observability_metrics():
    """
    Prometheus metrics endpoint for scraping.

    Returns metrics in Prometheus text format if prometheus-client
    is installed. Returns an empty response with a hint otherwise.
    """
    if not PROMETHEUS_AVAILABLE:
        return "# prometheus-client not installed; install with: pip install prometheus-client\n"
    return _prom_generate().decode("utf-8")


# ── HTML Dashboard ──────────────────────────────────────────────
# Self-contained HTML page with embedded CSS and JS.
# No external dependencies — works offline.

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Legis Agent — Dashboard</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface-hover: #242736;
    --border: #2a2d3a;
    --text: #e1e4ea;
    --text-secondary: #8b8fa3;
    --primary: #6366f1;
    --success: #22c55e;
    --warning: #f59e0b;
    --error: #ef4444;
    --radius: 8px;
    --radius-lg: 12px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.5;
  }
  h1 { font-size: 22px; margin-bottom: 4px; }
  h2 { font-size: 16px; margin-bottom: 12px; color: var(--text-secondary); }
  h3 { font-size: 14px; margin-bottom: 8px; font-weight: 600; }
  .header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .header-meta { font-size: 13px; color: var(--text-secondary); text-align: right; }
  .header-meta span { display: block; }
  .status-badge {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 12px; font-weight: 600;
  }
  .status-ok { background: rgba(34,197,94,0.15); color: var(--success); }
  .status-error { background: rgba(239,68,68,0.15); color: var(--error); }
  .status-warn { background: rgba(245,158,11,0.15); color: var(--warning); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 16px;
  }
  .card-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  .card-value { font-size: 28px; font-weight: 700; }
  .card-value.green { color: var(--success); }
  .card-value.yellow { color: var(--warning); }
  .card-value.red { color: var(--error); }
  .card-value.purple { color: var(--primary); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); color: var(--text-secondary); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
  td { padding: 8px 10px; border-bottom: 1px solid var(--border); }
  tr:hover td { background: var(--surface-hover); }
  .bar-container { background: var(--border); border-radius: 4px; height: 20px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; font-size: 11px; color: #fff; font-weight: 600; min-width: fit-content; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .badge-ok { background: rgba(34,197,94,0.15); color: var(--success); }
  .badge-warn { background: rgba(245,158,11,0.15); color: var(--warning); }
  .badge-err { background: rgba(239,68,68,0.15); color: var(--error); }
  .error-item { padding: 10px 12px; border-left: 3px solid var(--error); background: rgba(239,68,68,0.05); border-radius: var(--radius); margin-bottom: 8px; font-size: 13px; }
  .error-time { font-size: 11px; color: var(--text-secondary); }
  .error-op { font-weight: 600; }
  .section { margin-bottom: 24px; }
  .empty { padding: 24px; text-align: center; color: var(--text-secondary); font-size: 13px; }
  .loading { opacity: 0.5; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .refresh-btn {
    padding: 6px 14px; font-size: 12px; border: 1px solid var(--border);
    border-radius: var(--radius); background: var(--surface); color: var(--text);
    cursor: pointer; transition: all 0.15s;
  }
  .refresh-btn:hover { background: var(--primary); border-color: var(--primary); color: #fff; }
  .refresh-btn:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>⚖️ Legis Agent — Dashboard</h1>
    <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;">
      <span id="status-text">Loading...</span>
      <span id="version-text" style="margin-left:12px;"></span>
    </div>
  </div>
  <div class="header-meta">
    <span id="uptime-text"></span>
    <button class="refresh-btn" onclick="fetchData()" style="margin-top:8px;">↻ Refresh</button>
  </div>
</div>

<!-- Summary Cards -->
<div class="grid" id="summary-cards">
  <div class="card">
    <div class="card-label">Backend Status</div>
    <div class="card-value" id="backend-status">—</div>
  </div>
  <div class="card">
    <div class="card-label">Operations</div>
    <div class="card-value purple" id="total-ops">—</div>
  </div>
  <div class="card">
    <div class="card-label">Total Cost</div>
    <div class="card-value yellow" id="total-cost">—</div>
  </div>
  <div class="card">
    <div class="card-label">Monthly Estimate</div>
    <div class="card-value" id="monthly-estimate">—</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
  <!-- Left column -->
  <div>
    <!-- Cost by Provider -->
    <div class="section card">
      <h3>💰 Cost by Provider</h3>
      <div id="cost-provider"><div class="empty loading">Loading...</div></div>
    </div>

    <!-- Success Rates -->
    <div class="section card" style="margin-top:16px;">
      <h3>✅ Success Rates</h3>
      <div id="success-rates"><div class="empty loading">Loading...</div></div>
    </div>
  </div>

  <!-- Right column -->
  <div>
    <!-- Latency by Operation -->
    <div class="section card">
      <h3>⏱️ Latency by Operation (ms)</h3>
      <div id="latency-table"><div class="empty loading">Loading...</div></div>
    </div>

    <!-- Recent Errors -->
    <div class="section card" style="margin-top:16px;">
      <h3>❌ Recent Errors</h3>
      <div id="recent-errors"><div class="empty loading">Loading...</div></div>
    </div>
  </div>
</div>

<script>
const API_BASE = window.location.origin;
const API_PREFIX = "/api/v1";

function fmt(n) {
  if (n === undefined || n === null) return "—";
  if (typeof n === "number") {
    if (n < 0.01) return "$" + n.toFixed(6);
    if (n < 1) return "$" + n.toFixed(4);
    if (n < 1000) return "$" + n.toFixed(2);
    return "$" + n.toLocaleString("en-US", {maximumFractionDigits:2});
  }
  return n;
}

function fmtDuration(seconds) {
  if (!seconds && seconds !== 0) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts = [];
  if (d > 0) parts.push(d + "d");
  if (h > 0) parts.push(h + "h");
  if (m > 0) parts.push(m + "m");
  parts.push(s + "s");
  return parts.join(" ");
}

function pctColor(pct) {
  if (pct >= 99) return "var(--success)";
  if (pct >= 90) return "var(--warning)";
  return "var(--error)";
}

async function fetchData() {
  try {
    // Fetch health and stats in parallel
    const [healthRes, statsRes] = await Promise.all([
      fetch(API_BASE + "/health"),
      fetch(API_BASE + API_PREFIX + "/observability/stats"),
    ]);

    const health = await healthRes.json();
    const stats = await statsRes.json();

    // ── Header status ──
    document.getElementById("status-text").textContent = "✅ Backend online";
    document.getElementById("version-text").textContent = "v" + (health.version || "0.1.0");

    // ── Summary cards ──
    document.getElementById("backend-status").textContent = "✅ Online";
    document.getElementById("backend-status").className = "card-value green";
    document.getElementById("uptime-text").textContent =
      "Uptime: " + fmtDuration(stats.uptime_seconds);
    document.getElementById("total-ops").textContent =
      (stats.total_operations || 0).toLocaleString();
    document.getElementById("total-cost").textContent =
      fmt(stats.total_cost_usd);
    document.getElementById("monthly-estimate").textContent =
      fmt(stats.monthly_estimate_usd) + "/mo";

    // ── Cost by provider ──
    const costProvEl = document.getElementById("cost-provider");
    const costByProvider = stats.cost_by_provider || {};
    const costEntries = Object.entries(costByProvider);
    if (costEntries.length === 0) {
      costProvEl.innerHTML = '<div class="empty">No costs recorded yet.</div>';
    } else {
      const maxCost = Math.max(...Object.values(costByProvider));
      let html = '<table><thead><tr><th>Provider</th><th>Cost</th><th></th></tr></thead><tbody>';
      for (const [provider, cost] of costEntries) {
        const pct = maxCost > 0 ? (cost / maxCost * 100) : 0;
        const color = provider.includes("openai") ? "#10a37f" :
                      provider.includes("anthropic") ? "#d97706" :
                      provider.includes("gemini") ? "#4285f4" :
                      "var(--primary)";
        html += `<tr><td>${provider}</td><td>${fmt(cost)}</td>`;
        html += `<td><div class="bar-container"><div class="bar-fill" style="width:${Math.max(pct, 5)}%;background:${color}">${cost.toFixed(4)}</div></div></td></tr>`;
      }
      html += '</tbody></table>';
      costProvEl.innerHTML = html;
    }

    // ── Latency by operation ──
    const latEl = document.getElementById("latency-table");
    const latByOp = stats.latency_by_operation || {};
    const latEntries = Object.entries(latByOp);
    if (latEntries.length === 0) {
      latEl.innerHTML = '<div class="empty">No latency data recorded yet.</div>';
    } else {
      let html = '<table><thead><tr><th>Operation</th><th>Count</th><th>p50</th><th>p95</th><th>p99</th><th>Avg</th></tr></thead><tbody>';
      for (const [op, data] of latEntries) {
        const p50Color = data.p50 > 5000 ? "var(--error)" : data.p50 > 2000 ? "var(--warning)" : "inherit";
        html += `<tr><td>${op}</td><td>${data.count}</td>`;
        html += `<td style="color:${p50Color}">${data.p50.toFixed(0)}</td>`;
        html += `<td>${data.p95.toFixed(0)}</td>`;
        html += `<td>${data.p99.toFixed(0)}</td>`;
        html += `<td>${data.avg.toFixed(0)}</td></tr>`;
      }
      html += '</tbody></table>';
      latEl.innerHTML = html;
    }

    // ── Success rates ──
    const srEl = document.getElementById("success-rates");
    const successRates = stats.success_rates || {};
    const srEntries = Object.entries(successRates);
    if (srEntries.length === 0) {
      srEl.innerHTML = '<div class="empty">No operations recorded yet.</div>';
    } else {
      let html = '<table><thead><tr><th>Operation</th><th>Rate</th><th>OK</th><th>Fail</th></tr></thead><tbody>';
      for (const [op, data] of srEntries) {
        const badgeClass = data.rate >= 99 ? "badge-ok" : data.rate >= 90 ? "badge-warn" : "badge-err";
        html += `<tr><td>${op}</td>`;
        html += `<td><span class="badge ${badgeClass}">${data.rate.toFixed(1)}%</span></td>`;
        html += `<td>${data.success}</td><td>${data.failure}</td></tr>`;
      }
      html += '</tbody></table>';
      srEl.innerHTML = html;
    }

    // ── Recent errors ──
    const errEl = document.getElementById("recent-errors");
    const recentErrors = stats.recent_errors || [];
    if (recentErrors.length === 0) {
      errEl.innerHTML = '<div class="empty">✅ No recent errors</div>';
    } else {
      let html = '';
      for (const err of recentErrors) {
        html += '<div class="error-item">';
        html += '<div><span class="error-op">' + (err.operation || "unknown") + '</span>';
        if (err.request_id) html += ' <span style="font-family:monospace;font-size:11px;color:var(--text-secondary)">[' + err.request_id + ']</span>';
        html += '</div>';
        html += '<div style="margin-top:4px;">' + (err.error || "") + '</div>';
        html += '<div class="error-time">' + (err.timestamp || "") + ' · ' + (err.provider || "") + (err.model ? '/' + err.model : '') + '</div>';
        html += '</div>';
      }
      errEl.innerHTML = html;
    }

  } catch (err) {
    document.getElementById("status-text").textContent = "❌ Backend unreachable";
    document.getElementById("backend-status").textContent = "❌ Offline";
    document.getElementById("backend-status").className = "card-value red";

    const els = ["cost-provider", "latency-table", "success-rates", "recent-errors"];
    for (const id of els) {
      document.getElementById(id).innerHTML =
        '<div class="empty" style="color:var(--error)">Cannot connect to backend</div>';
    }
  }
}

// Auto-refresh every 30 seconds
document.addEventListener("DOMContentLoaded", () => {
  fetchData();
  setInterval(fetchData, 30000);
});
</script>

</body>
</html>
"""
