import { useState, useEffect } from "react";
import { apiClient, EmailDraftResponse, DocumentSummary } from "../api/client";
import { validateEmailDraft } from "../api/validation";
import { t } from "../i18n";
import { inputBase, errorBox } from "../theme";

const ACT_TYPES = [
  { value: "escritura" },
  { value: "poder" },
  { value: "testamento" },
  { value: "matrimonio" },
  { value: "general" },
];

interface TemplateInfo {
  act_type: string;
  name: string;
  description: string;
  required_fields: string[];
}

interface EmailDraftProps {
  /** Optional document to use as RAG context for the email */
  document?: DocumentSummary | null;
}

function EmailDraft({ document }: EmailDraftProps) {
  const [actType, setActType] = useState("escritura");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [language, setLanguage] = useState("es");
  const [sensitivity, setSensitivity] = useState("normal");
  const [customQuery, setCustomQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EmailDraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [template, setTemplate] = useState<TemplateInfo | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [useDocContext, setUseDocContext] = useState(!!document);

  // Fetch template info when act type changes
  useEffect(() => {
    apiClient.getEmailTemplates().then((data) => {
      const t = data.templates.find((tmpl: TemplateInfo) => tmpl.act_type === actType);
      setTemplate(t || null);
      // Reset fields for new template
      if (t) {
        const defaultFields: Record<string, string> = {};
        t.required_fields.forEach((f: string) => (defaultFields[f] = ""));
        setFields(defaultFields);
      }
    });
  }, [actType]);

  const updateField = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }));
  };

  const handleGenerate = async () => {
    const validation = validateEmailDraft(actType, fields, template?.required_fields || []);
    if (!validation.valid) {
      setError(Object.values(validation.errors).join("\n"));
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await apiClient.draftEmail({
        act_type: actType,
        fields: Object.fromEntries(Object.entries(fields).filter(([_, v]) => v)),
        sensitivity,
        language,
        custom_query: customQuery || undefined,
        document_id: document && useDocContext ? document.id : undefined,
      });
      setResult(res);
    } catch (err) {
      console.error("Email generation failed:", err);
      setError("Failed to generate email");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <h2 style={{ fontSize: 22, marginBottom: 20 }}>{t("email.title")}</h2>

      {/* Document context banner — unified Document → Email flow */}
      {document && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 16px",
            marginBottom: 20,
            background: "linear-gradient(135deg, rgba(99,102,241,0.12), rgba(6,182,212,0.08))",
            border: "1px solid var(--color-primary)",
            borderRadius: "var(--radius-lg)",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 24, lineHeight: 1 }}>📄</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-primary)" }}>
                📨 {t("email.generate")} {t("documents.email")}
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text)", marginTop: 2 }}>
                <strong>{document.filename}</strong>
                <span style={{ color: "var(--color-text-secondary)" }}>
                  {" "}— {document.pages} pages, {document.chunks} chunks
                </span>
              </div>
            </div>
          </div>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              cursor: "pointer",
              color: "var(--color-primary)",
              fontWeight: 600,
              padding: "6px 12px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-primary)",
              backgroundColor: "var(--color-primary-bg)",
              userSelect: "none",
            }}
          >
            <input
              type="checkbox"
              checked={useDocContext}
              onChange={(e) => setUseDocContext(e.target.checked)}
              style={{ cursor: "pointer" }}
            />
            {t("email.useDocContext")}
          </label>
        </div>
      )}

      <div style={{ display: "flex", gap: 24 }}>
        {/* ── Left: Form ───────────────────────────── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ marginBottom: 16 }}>
            <label className="section-label">{t("email.actTypeLabel")}</label>
            <select
              value={actType}
              onChange={(e) => setActType(e.target.value)}
              style={inputBase}
            >
              {ACT_TYPES.map((a) => (
                <option key={a.value} value={a.value}>
                  {t(`email.actType.${a.value}`)}
                </option>
              ))}
            </select>
          </div>

          {template && (
            <div
              style={{
                fontSize: 12,
                color: "var(--color-text-secondary)",
                marginBottom: 16,
                padding: "8px 12px",
                backgroundColor: "var(--color-surface)",
                borderRadius: "var(--radius)",
              }}
            >
              {template.name} — {template.description}
            </div>
          )}

          {/* Dynamic fields */}
          {template?.required_fields.map((field) => (
            <div key={field} style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 600,
                  marginBottom: 4,
                  color: "var(--color-text-secondary)",
                  textTransform: "capitalize",
                }}
              >
                {field.replace(/_/g, " ")}
              </label>
              <input
                type="text"
                placeholder={field.replace(/_/g, " ")}
                value={fields[field] || ""}
                onChange={(e) => updateField(field, e.target.value)}
                style={inputBase}
              />
            </div>
          ))}

          {/* Options */}
          <div
            style={{
              display: "flex",
              gap: 12,
              marginTop: 16,
              marginBottom: 16,
            }}
          >
            <div style={{ flex: 1 }}>
              <label className="section-label">{t("email.language")}</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                style={inputBase}
              >
                <option value="es">Spanish</option>
                <option value="en">English</option>
                <option value="fr">French</option>
                <option value="pt">Portuguese</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label className="section-label">{t("email.sensitivity")}</label>
              <select
                value={sensitivity}
                onChange={(e) => setSensitivity(e.target.value)}
                style={inputBase}
              >
                <option value="normal">Normal</option>
                <option value="private">Private (local model)</option>
              </select>
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="section-label">
              {t("email.customQuery")}{" "}
              <span style={{ fontWeight: 400, color: "var(--color-text-secondary)" }}>
                (optional)
              </span>
            </label>
            <textarea
              placeholder="e.g. Add a note about payment deadline..."
              value={customQuery}
              onChange={(e) => setCustomQuery(e.target.value)}
              rows={3}
              style={{ ...inputBase, resize: "vertical" }}
            />
          </div>

          <button
            onClick={handleGenerate}
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
            {loading ? t("email.generating") : `✍️ ${t("email.generate")}`}
          </button>

          {error && (
            <div role="alert" style={errorBox}>
              {error}
            </div>
          )}
        </div>

        {/* ── Right: Result ────────────────────────── */}
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
              <div className="loading" style={{ fontSize: 32, marginBottom: 12 }} aria-hidden="true">
                ⏳
              </div>
              {t("email.generating")}
            </div>
          )}

          {result && (
            <div aria-live="polite">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 12,
                }}
              >
                <h3 style={{ margin: 0, fontSize: 16 }}>📨 {t("email.result.to")}</h3>
                <button
                  onClick={() => setShowRaw(!showRaw)}
                  className="doc-btn"
                >
                  {showRaw ? t("app.close") : t("email.showRaw")}
                </button>
              </div>

              {/* Meta info */}
              <div
                style={{
                  display: "flex",
                  gap: 12,
                  fontSize: 11,
                  color: "var(--color-text-secondary)",
                  marginBottom: 12,
                }}
              >
                <span>Model: {result.model_used}</span>
                {result.template_used && <span>Template: {result.template_used}</span>}
                <span>{t("dashboard.card.tokens")}: {result.tokens_used}</span>
              </div>

              {showRaw ? (
                <pre
                  style={{
                    backgroundColor: "var(--color-surface)",
                    padding: 16,
                    borderRadius: "var(--radius)",
                    fontSize: 12,
                    overflowX: "auto",
                    whiteSpace: "pre-wrap",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  {JSON.stringify(result, null, 2)}
                </pre>
              ) : (
                <div
                  style={{
                    backgroundColor: "var(--color-surface)",
                    padding: 20,
                    borderRadius: "var(--radius)",
                    border: "1px solid var(--color-border)",
                    fontSize: 14,
                    lineHeight: 1.7,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {result.body}
                </div>
              )}

              {/* Copy button */}
              <button
                onClick={() => navigator.clipboard.writeText(result.body)}
                className="doc-btn"
                style={{ marginTop: 12 }}
              >
                📋 {t("app.copy")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default EmailDraft;
