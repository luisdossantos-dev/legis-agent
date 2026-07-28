import { useState } from "react";
import { validateClauseReview } from "../api/validation";

interface ReviewIssue {
  type: string;
  severity: string;
  description: string;
  suggested_fix: string;
}

interface ReviewResponse {
  risk_level: string;
  summary: string;
  issues: ReviewIssue[];
  missing_elements: string[];
  recommendations: string[];
  processing_time_ms: number;
  clause_type: string;
  checklist_summary: Record<string, number> | null;
}

const CLAUSE_TYPES = [
  { value: "prix", label: "💰 Price & Payment Terms" },
  { value: "delai", label: "⏰ Deadline & Time Limits" },
  { value: "condition_suspensive", label: "🔗 Suspensive Conditions" },
  { value: "renonciation", label: "✋ Waiver of Rights" },
  { value: "garantie", label: "🛡️ Warranties & Guarantees" },
  { value: "penalite", label: "⚠️ Penalty Clauses" },
  { value: "autre", label: "📄 Other / General" },
];

const RISK_LABELS: Record<string, { label: string; color: string }> = {
  green: { label: "✅ Low Risk", color: "var(--color-success, #22c55e)" },
  yellow: { label: "⚠️ Medium Risk", color: "var(--color-warning, #eab308)" },
  red: { label: "🚫 High Risk", color: "var(--color-error, #ef4444)" },
};

function ClauseReview() {
  const [clauseText, setClauseText] = useState("");
  const [clauseType, setClauseType] = useState("autre");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleReview = async () => {
    const validation = validateClauseReview(clauseText);
    if (!validation.valid) {
      setError(validation.errors.clause_text);
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("http://localhost:8000/api/v1/clauses/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clause_text: clauseText,
          clause_type: clauseType,
          context: context,
        }),
      });

      if (!res.ok) {
        const errBody = await res.text();
        throw new Error(`HTTP ${res.status}: ${errBody}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const riskInfo = result ? RISK_LABELS[result.risk_level] || RISK_LABELS["yellow"] : null;

  const getSeverityClass = (severity: string) => {
    switch (severity) {
      case "red": return "sev-red";
      case "yellow": return "sev-yellow";
      default: return "sev-green";
    }
  };

  return (
    <div className="clause-review">
      <h2>🔍 Clause Review</h2>
      <p style={{ color: "var(--color-text-secondary)", marginBottom: 16, fontSize: 13 }}>
        Analyze a notarial clause against risk checklists, legal references, and best practices.
      </p>

      <div className="review-form" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <label style={{ fontWeight: 600, fontSize: 13 }}>Clause Type</label>
          <select
            value={clauseType}
            onChange={(e) => setClauseType(e.target.value)}
            className="form-input"
            style={{ width: "100%", marginTop: 4 }}
          >
            {CLAUSE_TYPES.map((ct) => (
              <option key={ct.value} value={ct.value}>{ct.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ fontWeight: 600, fontSize: 13 }}>
            Clause Text <span style={{ color: "var(--color-error)" }}>*</span>
          </label>
          <textarea
            value={clauseText}
            onChange={(e) => setClauseText(e.target.value)}
            className="form-input"
            placeholder="Paste the clause text here..."
            rows={8}
            style={{ width: "100%", marginTop: 4, fontFamily: "monospace", fontSize: 13 }}
          />
        </div>

        <div>
          <label style={{ fontWeight: 600, fontSize: 13 }}>
            Context (optional)
            <span style={{ fontWeight: 400, color: "var(--color-text-secondary)", marginLeft: 8 }}>
              Other clauses from the same document
            </span>
          </label>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            className="form-input"
            placeholder="Other clauses from the same document, for cross-reference..."
            rows={4}
            style={{ width: "100%", marginTop: 4, fontSize: 13 }}
          />
        </div>

        <button
          onClick={handleReview}
          disabled={loading || !clauseText.trim()}
          className="doc-btn"
          style={{
            alignSelf: "flex-start",
            padding: "8px 24px",
            fontWeight: 600,
            opacity: loading || !clauseText.trim() ? 0.6 : 1,
          }}
        >
          {loading ? "⏳ Reviewing..." : "🔍 Review Clause"}
        </button>
      </div>

      {error && (
        <div role="alert" className="error-message" style={{
          marginTop: 16,
          padding: "12px 16px",
          backgroundColor: "rgba(239, 68, 68, 0.1)",
          border: "1px solid var(--color-error)",
          borderRadius: "var(--radius)",
          fontSize: 13,
          color: "var(--color-error)",
        }}>
          ❌ {error}
        </div>
      )}

      {loading && (
        <div role="status" aria-live="polite" className="review-loading" style={{
          marginTop: 16,
          padding: 24,
          textAlign: "center",
          color: "var(--color-text-secondary)",
        }}>
          <div style={{ fontSize: 24, marginBottom: 8 }} aria-hidden="true">⏳</div>
          <div>Analyzing clause against checklists and legal references...</div>
        </div>
      )}

      {result && !loading && (
        <div className="review-result" style={{ marginTop: 20 }} aria-live="polite">
          {/* Risk Level Banner */}
          {riskInfo && (
            <div style={{
              padding: "16px 20px",
              borderRadius: "var(--radius)",
              backgroundColor: `${riskInfo.color}15`,
              border: `2px solid ${riskInfo.color}`,
              marginBottom: 16,
            }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: riskInfo.color }}>
                {riskInfo.label}
                {result.processing_time_ms > 0 && (
                  <span style={{ fontSize: 12, fontWeight: 400, marginLeft: 12, opacity: 0.7 }}>
                    {(result.processing_time_ms / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
              <div style={{ marginTop: 6, fontSize: 13, color: "var(--color-text-secondary)" }}>
                {result.summary}
              </div>
            </div>
          )}

          {/* Checklist Summary */}
          {result.checklist_summary && (
            <div className="checklist-summary" style={{
              marginBottom: 16,
              display: "flex",
              gap: 16,
              fontSize: 13,
            }}>
              <span>📋 {result.checklist_summary.required_count} required elements</span>
              <span>🔍 {result.checklist_summary.issue_templates_count} issue checks</span>
              <span>⚠️ {result.checklist_summary.risk_patterns_count} risk patterns</span>
            </div>
          )}

          {/* Issues */}
          {result.issues.length > 0 && (
            <div className="issues-section" style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, marginBottom: 8 }}>
                🐛 Issues ({result.issues.length})
              </h3>
              {result.issues.map((issue, i) => (
                <div
                  key={i}
                  className={`issue-card ${getSeverityClass(issue.severity)}`}
                  style={{
                    padding: "10px 14px",
                    marginBottom: 8,
                    borderRadius: "var(--radius)",
                    border: `1px solid ${
                      issue.severity === "red" ? "var(--color-error)" :
                      issue.severity === "yellow" ? "var(--color-warning)" :
                      "var(--color-success)"
                    }`,
                    backgroundColor: `${
                      issue.severity === "red" ? "rgba(239,68,68,0.05)" :
                      issue.severity === "yellow" ? "rgba(234,179,8,0.05)" :
                      "rgba(34,197,94,0.05)"
                    }`,
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong>{issue.type}</strong>
                    <span style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 10,
                      backgroundColor: issue.severity === "red" ? "rgba(239,68,68,0.15)" :
                                       issue.severity === "yellow" ? "rgba(234,179,8,0.15)" :
                                       "rgba(34,197,94,0.15)",
                      color: issue.severity === "red" ? "var(--color-error)" :
                             issue.severity === "yellow" ? "var(--color-warning)" :
                             "var(--color-success)",
                      fontWeight: 600,
                    }}>
                      {issue.severity}
                    </span>
                  </div>
                  <div style={{ marginTop: 4, color: "var(--color-text-secondary)" }}>
                    {issue.description}
                  </div>
                  {issue.suggested_fix && (
                    <div style={{ marginTop: 4, color: "var(--color-primary)", fontSize: 12 }}>
                      💡 {issue.suggested_fix}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Missing Elements */}
          {result.missing_elements.length > 0 && (
            <div className="missing-section" style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, marginBottom: 8 }}>
                ❌ Missing Elements ({result.missing_elements.length})
              </h3>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
                {result.missing_elements.map((el, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>{el}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <div className="recommendations-section">
              <h3 style={{ fontSize: 14, marginBottom: 8 }}>
                💡 Recommendations ({result.recommendations.length})
              </h3>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
                {result.recommendations.map((rec, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ClauseReview;
