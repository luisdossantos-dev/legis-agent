import type { DocumentSummary } from "../api/client";
import { t } from "../i18n";

interface DocumentListProps {
  documents: DocumentSummary[];
  onSelect: (doc: DocumentSummary) => void;
  onChat: (doc: DocumentSummary) => void;
  onDraftEmail: (doc: DocumentSummary) => void;
  apiConfigured: boolean;
}

function DocumentList({ documents, onSelect, onChat, onDraftEmail, apiConfigured }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <div className="doc-list" role="region" aria-label={t("documents.title")}>
        <div className="doc-list-title">{t("documents.title")}</div>
        <div style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>
          {t("documents.empty")}
        </div>
        {!apiConfigured && (
          <div
            role="alert"
            style={{
              marginTop: 12,
              padding: "10px 14px",
              backgroundColor: "rgba(245,158,11,0.1)",
              border: "1px solid var(--color-warning)",
              borderRadius: "var(--radius)",
              fontSize: 12,
              color: "var(--color-warning)",
              lineHeight: 1.5,
            }}
          >
            ⚠️ {t("documents.noApiKey")}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="doc-list" role="region" aria-label={t("documents.title")}>
      <div className="doc-list-title">
        {`${t("documents.title")} (${documents.length})`}
      </div>
      {!apiConfigured && (
        <div
          role="alert"
          style={{
            padding: "10px 12px",
            marginBottom: 8,
            backgroundColor: "rgba(239,68,68,0.12)",
            border: "1px solid var(--color-error)",
            borderRadius: "var(--radius)",
            fontSize: 12,
            color: "var(--color-error)",
            fontWeight: 600,
            lineHeight: 1.4,
          }}
        >
          🔑 {t("documents.apiKeyRequired")}
        </div>
      )}
      {documents.map((doc) => {
        const isProcessing = doc.status === "processing";
        const btnDisabled = isProcessing || !apiConfigured;
        const btnTitle = !apiConfigured
          ? t("documents.btnTooltip.noApiKey")
          : isProcessing
          ? t("documents.btnTooltip.indexing")
          : "";
        return (
          <div key={doc.id} className="doc-item">
            <div className="doc-name">
              {doc.filename}
              {isProcessing && (
                <span
                  style={{
                    marginLeft: 8,
                    fontSize: 11,
                    color: "var(--color-warning)",
                    fontWeight: 600,
                  }}
                >
                  {t("documents.indexing")}
                </span>
              )}
              {doc.status === "error" && (
                <span
                  style={{
                    marginLeft: 8,
                    fontSize: 11,
                    color: "var(--color-error)",
                    fontWeight: 600,
                  }}
                >
                  {t("documents.error")}
                </span>
              )}
            </div>
            <div className="doc-meta">
              {t("documents.pagesChunks", String(doc.pages), String(doc.chunks))}
            </div>
            <div className="doc-actions">
              <span
                title={btnTitle}
                style={{ display: "inline-block" }}
              >
                <button
                  className="doc-btn"
                  disabled={btnDisabled}
                  onClick={() => onSelect(doc)}
                  aria-label={`${t("documents.analyze")} ${doc.filename}`}
                  style={{ opacity: btnDisabled ? 0.5 : 1 }}
                >
                  <span className="doc-btn-icon">🔍</span>
                  <span className="doc-btn-label">{t("documents.analyze")}</span>
                </button>
              </span>
              <span
                title={btnTitle}
                style={{ display: "inline-block" }}
              >
                <button
                  className="doc-btn"
                  disabled={btnDisabled}
                  onClick={() => onChat(doc)}
                  aria-label={`${t("documents.chat")} ${doc.filename}`}
                  style={{ opacity: btnDisabled ? 0.5 : 1 }}
                >
                  <span className="doc-btn-icon">💬</span>
                  <span className="doc-btn-label">{t("documents.chat")}</span>
                </button>
              </span>
              <span
                title={!apiConfigured ? t("documents.btnTooltip.noApiKey") : ""}
                style={{ display: "inline-block" }}
              >
                <button
                  className="doc-btn"
                  disabled={!apiConfigured}
                  onClick={() => onDraftEmail(doc)}
                  aria-label={`${t("documents.email")} ${doc.filename}`}
                  style={{ opacity: !apiConfigured ? 0.5 : 1, fontWeight: 600 }}
                >
                  <span className="doc-btn-icon">📧</span>
                  <span className="doc-btn-label">{t("documents.email")}</span>
                </button>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default DocumentList;
