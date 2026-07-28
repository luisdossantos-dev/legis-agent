import type { DocumentSummary, AnalysisResult as AnalysisResultType } from "../api/client";
import { t } from "../i18n";

interface AnalysisResultProps {
  document: DocumentSummary;
  analysis: AnalysisResultType | null;
}

function AnalysisResult({ document, analysis }: AnalysisResultProps) {
  if (!analysis) {
    return (
      <div className="analysis-container">
        <h2 className="analysis-title">{document.filename}</h2>
        <div className="loading" style={{ marginTop: 24 }} role="status" aria-live="polite">
          {t("analysis.analyzing")}
        </div>
      </div>
    );
  }

  return (
    <div className="analysis-container">
      <h2 className="analysis-title">
        {analysis.document_type || t("analysis.title")}
      </h2>
      <p style={{ color: "var(--color-text-secondary)", marginBottom: 24 }}>
        {document.filename}
      </p>

      {/* Summary */}
      {analysis.summary && (
        <div className="analysis-section">
          <div className="section-label">{t("analysis.summary")}</div>
          <div className="section-content">{analysis.summary}</div>
        </div>
      )}

      {/* Parties */}
      {analysis.parties.length > 0 && (
        <div className="analysis-section">
          <div className="section-label">{t("analysis.parties")}</div>
          <ul className="section-list">
            {analysis.parties.map((party, i) => (
              <li key={i}>{party}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Dates */}
      {analysis.dates.length > 0 && (
        <div className="analysis-section">
          <div className="section-label">{t("analysis.dates")}</div>
          <ul className="section-list">
            {analysis.dates.map((date, i) => (
              <li key={i}>{date}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Amounts */}
      {analysis.amounts.length > 0 && (
        <div className="analysis-section">
          <div className="section-label">{t("analysis.amounts")}</div>
          <ul className="section-list">
            {analysis.amounts.map((amt, i) => (
              <li key={i}>{amt.description}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Clauses */}
      {analysis.clauses.length > 0 && (
        <div className="analysis-section">
          <div className="section-label">{t("analysis.clauses")}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {analysis.clauses.map((clause, i) => (
              <div
                key={i}
                className="doc-item"
                style={{ cursor: "default" }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {clause.title}
                </div>
                <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
                  {clause.content.slice(0, 200)}
                  {clause.content.length > 200 ? "..." : ""}
                </div>
                {clause.risk_level && (
                  <div
                    style={{
                      marginTop: 8,
                      fontSize: 12,
                      color:
                        clause.risk_level === "high"
                          ? "var(--color-error)"
                          : clause.risk_level === "medium"
                          ? "var(--color-warning)"
                          : "var(--color-success)",
                    }}
                  >
                    {t("analysis.risks")}: {clause.risk_level}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risks */}
      {analysis.risks.length > 0 && (
        <div className="analysis-section">
          <div className="section-label">{t("analysis.risks")}</div>
          <ul className="section-list">
            {analysis.risks.map((risk, i) => (
              <li key={i} style={{ color: "var(--color-warning)" }}>
                ⚠️ {risk}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default AnalysisResult;
