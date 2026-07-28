import { useState } from "react";
import { inputBase, errorBox } from "../theme";

const API_BASE = "http://localhost:8000";
const API_PREFIX = "/api/v1";

interface ActionResult {
  action_name: string;
  status: string;
  params: Record<string, unknown>;
  result: string | null;
  cost_estimated_usd: number;
  error: string | null;
}

interface DetectedAction {
  action_name: string;
  params: Record<string, unknown>;
  confidence: number;
  reasoning: string;
}

interface ActionResponse {
  email_id: string;
  detected_actions: DetectedAction[];
  execution_results: ActionResult[];
  total_estimated_cost: number;
}

const ACTION_EMOJI: Record<string, string> = {
  mark_as_read: "👁️",
  draft_reply: "✍️",
  create_task: "📋",
  forward_to_notary: "➡️",
  archive: "📁",
};

const STATUS_COLOR: Record<string, string> = {
  success: "var(--color-success)",
  validation_error: "var(--color-error)",
  cost_guard: "var(--color-warning)",
  execution_error: "var(--color-error)",
  skipped: "var(--color-text-secondary)",
};

const CATEGORY_OPTIONS = [
  { value: "cliente_nuevo", label: "🆕 New Client" },
  { value: "seguimiento_escritura", label: "📝 Deed Follow-up" },
  { value: "consulta_hipoteca", label: "🏠 Mortgage Inquiry" },
  { value: "notificacion_banco", label: "🏦 Bank Notification" },
  { value: "spam", label: "🚫 Spam" },
  { value: "interno", label: "🏢 Internal" },
];

function ActionDetector() {
  const [category, setCategory] = useState("cliente_nuevo");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ActionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDetect = async () => {
    if (!body.trim()) {
      setError("Email body is required.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}/email/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email_id: "test-" + Date.now(),
          category,
          subject,
          body,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Action detection failed");
      }

      const data: ActionResponse = await res.json();
      setResult(data);
    } catch (err) {
      console.error("Action detection failed:", err);
      setError("Failed to detect action");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <h2 style={{ fontSize: 22, marginBottom: 8 }}>⚡ Action Detector</h2>
      <p
        style={{
          fontSize: 13,
          color: "var(--color-text-secondary)",
          marginBottom: 20,
        }}
      >
        Detect and execute actions from classified emails using LangGraph + cost guards.
      </p>

      <div style={{ display: "flex", gap: 24 }}>
        {/* ── Form ──────────────────────────────── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ marginBottom: 12 }}>
            <label className="section-label">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={inputBase}
            >
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: 12 }}>
            <label className="section-label">Subject</label>
            <input
              type="text"
              placeholder="Email subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              style={inputBase}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="section-label">Body *</label>
            <textarea
              placeholder="Paste the email content..."
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              style={{ ...inputBase, resize: "vertical" }}
            />
          </div>

          <button
            onClick={handleDetect}
            disabled={loading}
            style={{
              padding: "12px 28px",
              backgroundColor: "var(--color-primary)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius)",
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: 14,
              fontWeight: 600,
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? "🤖 Detecting..." : "⚡ Detect & Execute"}
          </button>

          {error && (
            <div role="alert" style={errorBox}>
              {error}
            </div>
          )}
        </div>

        {/* ── Result ─────────────────────────────── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {loading && (
            <div
              role="status"
              aria-live="polite"
              style={{
                padding: 24,
                textAlign: "center",
                color: "var(--color-text-secondary)",
              }}
            >
              <div style={{ fontSize: 32, marginBottom: 12 }} aria-hidden="true">⏳</div>
              Running LangGraph pipeline...
            </div>
          )}

          {result && (
            <div aria-live="polite">
              <h3 style={{ margin: "0 0 16px 0", fontSize: 16 }}>📋 Pipeline Result</h3>

              {/* Detected action */}
              {result.detected_actions.map((action, i) => (
                <div
                  key={i}
                  style={{
                    padding: 16,
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    marginBottom: 16,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      marginBottom: 8,
                    }}
                  >
                    <span style={{ fontSize: 28 }}>
                      {ACTION_EMOJI[action.action_name] || "❓"}
                    </span>
                    <div>
                      <div
                        style={{
                          fontSize: 18,
                          fontWeight: 700,
                          color: "var(--color-text)",
                        }}
                      >
                        {action.action_name.replace(/_/g, " ")}
                      </div>
                      <div
                        style={{
                          fontSize: 12,
                          color: "var(--color-text-secondary)",
                        }}
                      >
                        Confidence: {(action.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>

                  {action.reasoning && (
                    <div
                      style={{
                        fontSize: 13,
                        color: "var(--color-text-secondary)",
                        padding: "8px 12px",
                        backgroundColor: "var(--color-bg)",
                        borderRadius: "var(--radius)",
                        marginTop: 8,
                      }}
                    >
                      {action.reasoning}
                    </div>
                  )}
                </div>
              ))}

              {/* Execution results */}
              {result.execution_results.map((exec, i) => (
                <div
                  key={i}
                  style={{
                    padding: 14,
                    borderRadius: "var(--radius)",
                    border: `1px solid ${STATUS_COLOR[exec.status] || "var(--color-border)"}`,
                    backgroundColor: "var(--color-surface)",
                    marginBottom: 10,
                    fontSize: 13,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 6,
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>
                      {exec.status === "success" ? "✅" : exec.status === "validation_error" ? "❌" : "⚠️"}{" "}
                      Status: <span style={{ color: STATUS_COLOR[exec.status] }}>{exec.status}</span>
                    </span>
                    <span style={{ color: "var(--color-text-secondary)", fontSize: 12 }}>
                      ${exec.cost_estimated_usd.toFixed(6)}
                    </span>
                  </div>

                  {exec.result && (
                    <div style={{ color: "var(--color-text-secondary)", marginTop: 4 }}>
                      {exec.result}
                    </div>
                  )}

                  {exec.error && (
                    <div
                      style={{
                        color: "var(--color-error)",
                        marginTop: 4,
                        padding: "6px 10px",
                        backgroundColor: "rgba(239,68,68,0.08)",
                        borderRadius: "var(--radius)",
                      }}
                    >
                      {exec.error}
                    </div>
                  )}
                </div>
              ))}

              {/* Cost summary */}
              <div
                style={{
                  fontSize: 12,
                  color: "var(--color-text-secondary)",
                  textAlign: "right",
                  marginTop: 8,
                }}
              >
                Total estimated cost: ${result.total_estimated_cost.toFixed(6)} USD
              </div>
            </div>
          )}

          {!result && !loading && (
            <div
              style={{
                padding: 24,
                textAlign: "center",
                color: "var(--color-text-secondary)",
                fontSize: 13,
                border: "2px dashed var(--color-border)",
                borderRadius: "var(--radius-lg)",
              }}
            >
              Paste an email and select a category, then click "Detect & Execute".
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ActionDetector;
