import { useState, useEffect, useCallback } from "react";
import { t } from "../i18n";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line, Bar, Doughnut } from "react-chartjs-2";

// ── Register Chart.js components ─────────────────────────────
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

// ── Types ──────────────────────────────────────────────────────

interface DashboardData {
  uptime_seconds: number;
  total_cost_usd: number;
  monthly_estimate_usd: number;
  total_operations: number;
  total_tokens: number;
  cost_by_provider: Record<string, number>;
  cost_by_model: Record<string, number>;
  model_usage: Array<{ model: string; calls: number }>;
  daily_cost: Array<{ date: string; cost: number; calls: number }>;
  latency_distribution: Record<string, number>;
  latency_by_operation: Record<string, { p50: number; p95: number; p99: number; count: number; avg: number }>;
  success_rates: Record<string, { rate: number; success: number; failure: number }>;
  tokens_by_provider: Record<string, { input: number; output: number }>;
  recent_errors: Array<{ timestamp: string; operation: string; provider: string; model: string; error: string; request_id: string }>;
}

const API_BASE = "http://localhost:8000";
const API_PREFIX = "/api/v1";

// ── Helpers ────────────────────────────────────────────────────

function fmtMoney(n: number): string {
  if (n < 0.0001) return `$${n.toFixed(8)}`;
  if (n < 0.01) return `$${n.toFixed(6)}`;
  if (n < 1) return `$${n.toFixed(4)}`;
  if (n < 1000) return `$${n.toFixed(2)}`;
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

function fmtDuration(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  if (m > 0) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(" ");
}

function fmtNumber(n: number): string {
  return n.toLocaleString();
}

function getProviderColor(provider: string): string {
  if (provider.includes("openai")) return "#10a37f";
  if (provider.includes("anthropic") || provider.includes("claude")) return "#d97706";
  if (provider.includes("google") || provider.includes("gemini")) return "#4285f4";
  if (provider.includes("deepseek")) return "#4f46e5";
  if (provider.includes("mistral")) return "#7c3aed";
  if (provider.includes("groq")) return "#22c55e";
  return "#6366f1";
}

const PROVIDER_COLORS = ["#10a37f", "#d97706", "#4285f4", "#4f46e5", "#7c3aed", "#22c55e", "#6366f1", "#ec4899"];

// ── Component ───────────────────────────────────────────────────

const DEFAULT_PRICE_PER_MILLION = 10; // USD

function CostDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pricePerMillion, setPricePerMillion] = useState<number>(() => {
    const saved = localStorage.getItem("legis-price-per-million");
    return saved ? parseFloat(saved) : DEFAULT_PRICE_PER_MILLION;
  });

  const calcCost = (tokens: number) => (tokens / 1_000_000) * pricePerMillion;

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE}${API_PREFIX}/observability/stats`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error("Dashboard load failed:", err);
      setError(t("dashboard.loadError"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--color-text-secondary)" }}>
        <div style={{ fontSize: 24, marginBottom: 12 }}>📊</div>
        {t("app.loading")}
      </div>
    );
  }

  if (error && !data) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <div style={{ fontSize: 24, marginBottom: 12 }}>❌</div>
        <div style={{ color: "var(--color-error)", marginBottom: 16 }}>{error}</div>
        <button onClick={fetchData} className="doc-btn">↻ Retry</button>
      </div>
    );
  }

  if (!data) return null;

  // ── Chart configs ──────────────────────────────────────────
  const dailyCostData = {
    labels: data.daily_cost.map((d) => {
      const parts = d.date.split("-");
      return `${parts[2]}/${parts[1]}`;
    }),
    datasets: [
      {
        label: "Cost ($)",
        data: data.daily_cost.map((d) => d.cost),
        borderColor: "#6366f1",
        backgroundColor: "rgba(99, 102, 241, 0.1)",
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 6,
      },
    ],
  };

  const dailyCallsData = {
    labels: data.daily_cost.map((d) => {
      const parts = d.date.split("-");
      return `${parts[2]}/${parts[1]}`;
    }),
    datasets: [
      {
        label: "Calls",
        data: data.daily_cost.map((d) => d.calls),
        backgroundColor: "rgba(34, 197, 94, 0.6)",
        borderRadius: 4,
      },
    ],
  };

  const modelUsageData = {
    labels: data.model_usage.slice(0, 8).map((m) => {
      const parts = m.model.split("/");
      return parts[parts.length - 1];
    }),
    datasets: [
      {
        label: "Calls",
        data: data.model_usage.slice(0, 8).map((m) => m.calls),
        backgroundColor: PROVIDER_COLORS.slice(0, data.model_usage.slice(0, 8).length),
        borderWidth: 0,
      },
    ],
  };

  const costByModelData = {
    labels: Object.entries(data.cost_by_model)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 6)
      .map(([model]) => {
        const parts = model.split("/");
        return parts[parts.length - 1];
      }),
    datasets: [
      {
        label: "Cost ($)",
        data: Object.entries(data.cost_by_model)
          .sort(([, a], [, b]) => b - a)
          .slice(0, 6)
          .map(([, cost]) => cost),
        backgroundColor: PROVIDER_COLORS,
        borderWidth: 0,
      },
    ],
  };

  const latencyDistData = {
    labels: Object.keys(data.latency_distribution),
    datasets: [
      {
        label: "Calls",
        data: Object.values(data.latency_distribution),
        backgroundColor: ["#22c55e", "#22c55e", "#f59e0b", "#f59e0b", "#ef4444", "#ef4444"],
        borderRadius: 4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "rgba(15, 17, 23, 0.9)",
        titleColor: "#e1e4ea",
        bodyColor: "#8b8fa3",
        borderColor: "#2a2d3a",
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        ticks: { color: "#8b8fa3", maxTicksLimit: 10 },
        grid: { color: "rgba(42, 45, 58, 0.5)" },
      },
      y: {
        ticks: { color: "#8b8fa3" },
        grid: { color: "rgba(42, 45, 58, 0.5)" },
      },
    },
  };

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "right" as const,
        labels: { color: "#8b8fa3", font: { size: 11 }, boxWidth: 12, padding: 8 },
      },
      tooltip: {
        backgroundColor: "rgba(15, 17, 23, 0.9)",
        titleColor: "#e1e4ea",
        bodyColor: "#8b8fa3",
      },
    },
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      {/* ── Header ─────────────────────────────── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <div>
          <h2 style={{ fontSize: 22, margin: 0 }}>{t("dashboard.title")}</h2>
          <div style={{ fontSize: 13, color: "var(--color-text-secondary)", marginTop: 4 }}>
            Uptime: {fmtDuration(data.uptime_seconds)} · Auto-refresh every 30s
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <label style={{ fontSize: 12, color: "var(--color-text-secondary)", whiteSpace: "nowrap" }}>
            {t("dashboard.pricePerMillion")}
          </label>
          <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>$</span>
          <input
            type="number"
            min={0}
            step={0.5}
            value={pricePerMillion}
            onChange={(e) => {
              const val = parseFloat(e.target.value) || 0;
              setPricePerMillion(val);
              localStorage.setItem("legis-price-per-million", String(val));
            }}
            style={{
              width: 70,
              padding: "6px 8px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-bg)",
              color: "var(--color-text)",
              fontSize: 13,
              textAlign: "right",
              outline: "none",
            }}
          />
          <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>/M tokens</span>
          <button onClick={fetchData} className="doc-btn" style={{ padding: "8px 18px" }}>
            ↻ {t("app.refresh")}
          </button>
        </div>
      </div>

      {/* ── Summary Cards ───────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
          marginBottom: 24,
        }}
      >
        {[
          { label: t("dashboard.card.totalCost"), value: fmtMoney(calcCost(data.total_tokens)), color: "var(--color-warning)" },
          { label: t("dashboard.card.monthlyEst"), value: fmtMoney(calcCost(data.total_tokens) * 30) + "/mo", color: "var(--color-primary)" },
          { label: t("dashboard.card.operations"), value: fmtNumber(data.total_operations), color: "var(--color-success)" },
          { label: t("dashboard.card.tokens"), value: fmtNumber(data.total_tokens), color: "var(--color-accent)" },
          { label: "Input Tokens", value: fmtNumber(Object.values(data.tokens_by_provider).reduce((s, t) => s + t.input, 0)), color: "var(--color-accent)" },
          { label: "Output Tokens", value: fmtNumber(Object.values(data.tokens_by_provider).reduce((s, t) => s + t.output, 0)), color: "var(--color-primary)" },
        ].map((card) => (
          <div
            key={card.label}
            style={{
              padding: "16px 18px",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
            }}
          >
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
              {card.label}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: card.color }}>
              {card.value}
            </div>
          </div>
        ))}
      </div>

      {/* ── Charts Row 1 ────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Daily Cost */}
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>{t("dashboard.chart.dailyCost")}</h3>
          <div style={{ height: 220 }}>
            {data.daily_cost.some((d) => d.cost > 0) ? (
              <Line data={dailyCostData} options={chartOptions} />
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
                {t("dashboard.noCostData")}
              </div>
            )}
          </div>
        </div>

        {/* Daily Calls */}
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>{t("dashboard.chart.dailyCalls")}</h3>
          <div style={{ height: 220 }}>
            {data.daily_cost.some((d) => d.calls > 0) ? (
              <Bar data={dailyCallsData} options={chartOptions} />
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
                {t("dashboard.noCallData")}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Charts Row 2 ────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Model Usage */}
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>{t("dashboard.chart.modelUsage")}</h3>
          <div style={{ height: 200 }}>
            {data.model_usage.length > 0 ? (
              <Doughnut data={modelUsageData} options={doughnutOptions} />
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
                {t("app.noData")}
              </div>
            )}
          </div>
        </div>

        {/* Cost by Model */}
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>{t("dashboard.chart.costByModel")}</h3>
          <div style={{ height: 200 }}>
            {Object.keys(data.cost_by_model).length > 0 ? (
              <Doughnut data={costByModelData} options={doughnutOptions} />
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
                {t("app.noData")}
              </div>
            )}
          </div>
        </div>

        {/* Latency Distribution */}
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>{t("dashboard.chart.latencyDist")}</h3>
          <div style={{ height: 200 }}>
            {Object.values(data.latency_distribution).some((v) => v > 0) ? (
              <Bar data={latencyDistData} options={chartOptions} />
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
                {t("app.noData")}
              </div>
            )}
          </div>
        </div>
      </div>

        {/* ── Tables Row ──────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Latency by Operation */}
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>{t("dashboard.table.latency")}</h3>
          {Object.keys(data.latency_by_operation).length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Operation</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Count</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>p50</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>p95</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Avg</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.latency_by_operation).map(([op, info]) => {
                  const p50Color = info.p50 > 5000 ? "var(--color-error)" : info.p50 > 2000 ? "var(--color-warning)" : "inherit";
                  return (
                    <tr key={op} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <td style={{ padding: "6px 8px", fontWeight: 600 }}>{op}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>{info.count}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: p50Color }}>{info.p50.toFixed(0)}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>{info.p95.toFixed(0)}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>{info.avg.toFixed(0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
              No latency data recorded yet.
            </div>
          )}
        </div>

        {/* Success Rates */}
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>{t("dashboard.table.success")}</h3>
          {Object.keys(data.success_rates).length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Operation</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Rate</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Success</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Failed</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.success_rates).map(([op, info]) => {
                  const badgeColor = info.rate >= 99 ? "var(--color-success)" : info.rate >= 90 ? "var(--color-warning)" : "var(--color-error)";
                  const badgeBg = info.rate >= 99 ? "rgba(34,197,94,0.15)" : info.rate >= 90 ? "rgba(245,158,11,0.15)" : "rgba(239,68,68,0.15)";
                  return (
                    <tr key={op} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <td style={{ padding: "6px 8px", fontWeight: 600 }}>{op}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 600, backgroundColor: badgeBg, color: badgeColor }}>
                          {info.rate.toFixed(1)}%
                        </span>
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>{info.success}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>{info.failure}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
              No operations recorded yet.
            </div>
          )}
        </div>
      </div>

      {/* ── Recent Errors ───────────────────────── */}
      {data.recent_errors.length > 0 && (
        <div
          style={{
            padding: 18,
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            marginBottom: 16,
          }}
        >
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600, color: "var(--color-error)" }}>
            ❌ Recent Errors ({data.recent_errors.length})
          </h3>
          {data.recent_errors.map((err, i) => (
            <div
              key={i}
              style={{
                padding: "8px 12px",
                marginBottom: 6,
                borderLeft: "3px solid var(--color-error)",
                backgroundColor: "rgba(239,68,68,0.05)",
                borderRadius: "var(--radius)",
                fontSize: 12,
              }}
            >
              <div style={{ fontWeight: 600 }}>
                {err.operation || "unknown"}
                {err.request_id && (
                  <code style={{ marginLeft: 8, fontSize: 10, color: "var(--color-text-secondary)" }}>
                    [{err.request_id}]
                  </code>
                )}
              </div>
              <div style={{ color: "var(--color-text-secondary)", marginTop: 2 }}>{err.error}</div>
              <div style={{ color: "var(--color-text-secondary)", fontSize: 11, marginTop: 2, opacity: 0.7 }}>
                {err.timestamp} · {err.provider}/{err.model}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Cost by Provider ──────────────────────── */}
      <div
        style={{
          padding: 18,
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
        }}
      >
        <h3 style={{ fontSize: 14, margin: "0 0 12px 0", fontWeight: 600 }}>💰 Cost by Provider</h3>
        {Object.keys(data.cost_by_provider).length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {Object.entries(data.cost_by_provider)
              .sort(([, a], [, b]) => b - a)
              .map(([provider, cost]) => {
                const maxCost = Math.max(...Object.values(data.cost_by_provider));
                const pct = maxCost > 0 ? (cost / maxCost) * 100 : 0;
                const color = getProviderColor(provider);
                return (
                  <div key={provider}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600 }}>{provider}</span>
                      <span>{fmtMoney(cost)}</span>
                    </div>
                    <div style={{ backgroundColor: "var(--color-border)", borderRadius: 4, height: 20, overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.max(pct, 3)}%`,
                          backgroundColor: color,
                          borderRadius: 4,
                          display: "flex",
                          alignItems: "center",
                          paddingLeft: 8,
                          fontSize: 11,
                          color: "#fff",
                          fontWeight: 600,
                          minWidth: "fit-content",
                        }}
                      >
                        {cost.toFixed(4)}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        ) : (
          <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
            No costs recorded yet.
          </div>
        )}
      </div>
    </div>
  );
}

export default CostDashboard;
