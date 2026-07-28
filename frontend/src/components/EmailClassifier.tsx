import { useState, useRef, useEffect } from "react";
import { t } from "../i18n";

const API_BASE = "http://localhost:8000";
const API_PREFIX = "/api/v1";

interface ClassificationResult {
  email_id: string;
  category: string;
  confidence: number;
  method: string;
  details: string | null;
}

function EmailClassifier() {
  const [fromAddress, setFromAddress] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (loading) {
      timerRef.current = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [loading]);

  const handleClassify = async () => {
    if (!body.trim()) {
      setError(t("classifier.bodyRequired"));
      return;
    }

    startTimeRef.current = Date.now();
    setElapsedSeconds(0);
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}/email/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_address: fromAddress,
          subject,
          body,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || t("classifier.toast.error"));
      }

      const data: ClassificationResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("classifier.toast.error"));
    } finally {
      setLoading(false);
    }
  };

  const confidenceColor = (conf: number) => {
    if (conf >= 0.7) return "var(--color-success)";
    if (conf >= 0.4) return "var(--color-warning)";
    return "var(--color-error)";
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <h2 style={{ fontSize: 22, marginBottom: 8 }}>{t("classifier.title")}</h2>
      <p
        style={{
          fontSize: 13,
          color: "var(--color-text-secondary)",
          marginBottom: 20,
        }}
      >
        {t("classifier.description")}
      </p>

      <div style={{ display: "flex", gap: 24 }}>
        {/* ── Form ──────────────────────────────── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ marginBottom: 12 }}>
            <label className="section-label">{t("classifier.from")}</label>
            <input
              type="text"
              placeholder="sender@example.com"
              value={fromAddress}
              onChange={(e) => setFromAddress(e.target.value)}
              style={inputStyle}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label className="section-label">{t("classifier.subject")}</label>
            <input
              type="text"
              placeholder="Email subject line"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              style={inputStyle}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="section-label">{t("classifier.body")} *</label>
            <textarea
              placeholder="Paste the email content here..."
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              style={{ ...inputStyle, resize: "vertical" }}
            />
          </div>

          <button
            onClick={handleClassify}
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
            {loading ? t("classifier.classifying") : `🏷️ ${t("classifier.classify")}`}
          </button>

          {error && (
            <div
              role="alert"
              style={{
                marginTop: 16,
                padding: 12,
                backgroundColor: "rgba(239,68,68,0.1)",
                border: "1px solid var(--color-error)",
                borderRadius: "var(--radius)",
                color: "var(--color-error)",
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* ── Result ─────────────────────────────── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {loading && (
            <div role="status" aria-live="polite">
              <div className="progress-bar" style={{ marginBottom: 8 }}>
                <div className="progress-bar-indeterminate" />
              </div>
              <div style={{ fontSize: 13, color: "var(--color-text-secondary)", textAlign: "center", marginBottom: 16 }}>
                ⏳ {t("classifier.classifying")}... {elapsedSeconds}s
              </div>

              <div
                style={{
                  padding: 24,
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-surface)",
                }}
              >
                <div style={{ textAlign: "center", marginBottom: 16 }}>
                  <div
                    className="skeleton"
                    style={{ width: 48, height: 48, borderRadius: "50%", margin: "0 auto 8px" }}
                  />
                  <div className="skeleton" style={{ width: "60%", height: 24, margin: "0 auto" }} />
                </div>
                <div className="skeleton" style={{ height: 8, marginBottom: 4 }} />
                <div className="skeleton" style={{ width: "40%", height: 8 }} />
              </div>
            </div>
          )}

          {result && (
            <div aria-live="polite">
              <h3 style={{ margin: "0 0 16px 0", fontSize: 16 }}>📊 {t("classifier.result")}</h3>

              {/* Category badge */}
              <div
                style={{
                  padding: "16px 20px",
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-surface)",
                  marginBottom: 16,
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 36, marginBottom: 8 }}>
                  {result.category === "cliente_nuevo"
                    ? "🆕"
                    : result.category === "seguimiento_escritura"
                    ? "📝"
                    : result.category === "consulta_hipoteca"
                    ? "🏠"
                    : result.category === "notificacion_banco"
                    ? "🏦"
                    : result.category === "spam"
                    ? "🚫"
                    : "🏢"}
                </div>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: "var(--color-text)",
                    marginBottom: 4,
                  }}
                >
                  {t("category." + result.category) || result.category}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    color: "var(--color-text-secondary)",
                  }}
                >
                  {t("classifier.method")}: {result.method === "embedding" ? "⚡ embeddings" : "🧠 LLM"}
                </div>
              </div>

              {/* Confidence bar */}
              <div style={{ marginBottom: 12 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    marginBottom: 4,
                    color: "var(--color-text-secondary)",
                  }}
                >
                  <span>{t("classifier.confidence")}</span>
                  <span style={{ fontWeight: 600, color: confidenceColor(result.confidence) }}>
                    {(result.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <div
                  style={{
                    height: 8,
                    borderRadius: 4,
                    backgroundColor: "var(--color-border)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${result.confidence * 100}%`,
                      backgroundColor: confidenceColor(result.confidence),
                      borderRadius: 4,
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
              </div>

              {/* Details */}
              {result.details && (
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--color-text-secondary)",
                    padding: "8px 12px",
                    backgroundColor: "var(--color-surface)",
                    borderRadius: "var(--radius)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  {result.details}
                </div>
              )}
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
              {t("classifier.description")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: "var(--radius)",
  border: "1px solid var(--color-border)",
  backgroundColor: "var(--color-bg)",
  color: "var(--color-text)",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
};

export default EmailClassifier;
