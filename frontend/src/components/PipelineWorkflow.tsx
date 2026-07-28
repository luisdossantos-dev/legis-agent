import { useState, useRef, useEffect } from "react";
import type { DocumentSummary } from "../api/client";
import { t } from "../i18n";

interface PipelineWorkflowProps {
  document: DocumentSummary;
}

const AVAILABLE_STEPS = [
  { id: "extract", icon: "📋" },
  { id: "analyze", icon: "🔍" },
  { id: "review", icon: "⚖️" },
  { id: "draft", icon: "✍️" },
  { id: "send", icon: "📨" },
];

function PipelineWorkflow({ document }: PipelineWorkflowProps) {
  const [selectedSteps, setSelectedSteps] = useState<string[]>(["extract", "analyze", "draft"]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [customQuery, setCustomQuery] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (running) {
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
  }, [running]);

  const toggleStep = (stepId: string) => {
    setSelectedSteps((prev) =>
      prev.includes(stepId)
        ? prev.filter((s) => s !== stepId)
        : [...prev, stepId]
    );
  };

  const handleRun = async () => {
    if (selectedSteps.length === 0) return;

    startTimeRef.current = Date.now();
    setElapsedSeconds(0);
    setRunning(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("http://localhost:8000/api/v1/agents/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: document.id,
          query: customQuery || "Analyze this legal document and extract its main components.",
          steps: selectedSteps,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Pipeline failed");
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pipeline execution failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <h2 style={{ fontSize: 22, marginBottom: 8 }}>{t("pipeline.title")}</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", marginBottom: 20 }}>
        {t("pipeline.description")}
      </p>

      {/* Document info */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 14px",
          marginBottom: 20,
          backgroundColor: "rgba(99,102,241,0.08)",
          border: "1px solid var(--color-primary)",
          borderRadius: "var(--radius)",
          fontSize: 13,
        }}
      >
        📄 <strong>{document.filename}</strong>
        <span style={{ color: "var(--color-text-secondary)" }}>
          ({document.pages} pages, {document.chunks} chunks)
        </span>
      </div>

      {/* Step selector */}
      <div style={{ marginBottom: 20 }}>
        <label
          style={{
            display: "block",
            fontSize: 13,
            fontWeight: 600,
            marginBottom: 10,
            color: "var(--color-text)",
          }}
        >
          {t("pipeline.steps")}
        </label>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {AVAILABLE_STEPS.map((step) => {
            const isSelected = selectedSteps.includes(step.id);
            return (
              <button
                key={step.id}
                onClick={() => toggleStep(step.id)}
                disabled={running}
                style={{
                  padding: "10px 18px",
                  borderRadius: "var(--radius)",
                  border: `2px solid ${
                    isSelected ? "var(--color-primary)" : "var(--color-border)"
                  }`,
                  backgroundColor: isSelected
                    ? "var(--color-primary-bg)"
                    : "var(--color-surface)",
                  color: isSelected
                    ? "var(--color-primary)"
                    : "var(--color-text-secondary)",
                  cursor: running ? "not-allowed" : "pointer",
                  fontSize: 13,
                  fontWeight: isSelected ? 700 : 500,
                  transition: "all 0.15s ease",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 2,
                  minWidth: 90,
                }}
                title={t(`pipeline.steps.${step.id}.desc`)}
              >
                <span style={{ fontSize: 20 }}>{step.icon}</span>
                <span>{t(`pipeline.steps.${step.id}`)}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Custom query */}
      <div style={{ marginBottom: 20 }}>
        <label
          style={{
            display: "block",
            fontSize: 13,
            fontWeight: 600,
            marginBottom: 6,
            color: "var(--color-text)",
          }}
        >
          Query <span style={{ fontWeight: 400, color: "var(--color-text-secondary)" }}>(optional)</span>
        </label>
        <textarea
          value={customQuery}
          onChange={(e) => setCustomQuery(e.target.value)}
          disabled={running}
          placeholder="Analyze this legal document and extract its main components."
          rows={2}
          style={{
            width: "100%",
            padding: "10px 12px",
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-bg)",
            color: "var(--color-text)",
            fontSize: 14,
            outline: "none",
            resize: "vertical",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* Run button */}
      <button
        onClick={handleRun}
        disabled={running || selectedSteps.length === 0}
        className="btn-primary"
        style={{ marginBottom: 20 }}
      >
        {running ? (
          <span>⏳ {t("pipeline.running")}</span>
        ) : (
          <span>{t("pipeline.run")} ({selectedSteps.length} steps)</span>
        )}
      </button>

      {running && (
        <div style={{ marginBottom: 20 }}>
          <div className="progress-bar" style={{ marginBottom: 8 }}>
            <div className="progress-bar-indeterminate" />
          </div>
          <div style={{ fontSize: 13, color: "var(--color-text-secondary)", textAlign: "center", marginBottom: 12 }}>
            ⏳ {t("pipeline.running")}... {elapsedSeconds}s
          </div>

          {selectedSteps.includes("analyze") && (
            <div style={{ marginTop: 12 }}>
              <div className="section-label">{t("analysis.summary")}</div>
              <div className="skeleton" style={{ height: 60, marginTop: 6 }} />
            </div>
          )}
          {selectedSteps.includes("review") && (
            <div style={{ marginTop: 12 }}>
              <div className="section-label">{t("pipeline.steps.review")}</div>
              <div className="skeleton" style={{ height: 80, marginTop: 6 }} />
            </div>
          )}
          {selectedSteps.includes("draft") && (
            <div style={{ marginTop: 12 }}>
              <div className="section-label">{t("pipeline.steps.draft")}</div>
              <div className="skeleton" style={{ height: 80, marginTop: 6 }} />
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          role="alert"
          style={{
            padding: 12,
            marginBottom: 16,
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

      {/* Result */}
      {result && (
        <div
          style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            padding: 20,
          }}
        >
          <h3 style={{ fontSize: 16, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
            {t("pipeline.result")}
            <span style={{ fontSize: 12, color: "var(--color-text-secondary)", fontWeight: 400 }}>
              {t("pipeline.stepsExecuted")}: {result.steps_executed?.join(" → ") || "—"}
            </span>
          </h3>

          {/* Summary */}
          {result.analysis?.summary && (
            <div style={{ marginBottom: 16 }}>
              <div className="section-label">{t("analysis.summary")}</div>
              <div style={{ fontSize: 14, lineHeight: 1.6, marginTop: 6 }}>
                {result.analysis.summary}
              </div>
            </div>
          )}

          {/* Review */}
          {result.review && (
            <div style={{ marginBottom: 16 }}>
              <div className="section-label">{t("pipeline.steps.review")}</div>
              <div
                style={{
                  fontSize: 14,
                  lineHeight: 1.6,
                  marginTop: 6,
                  padding: 12,
                  backgroundColor: "rgba(245,158,11,0.06)",
                  borderRadius: "var(--radius)",
                  border: "1px solid rgba(245,158,11,0.2)",
                  whiteSpace: "pre-wrap",
                }}
              >
                {result.review}
              </div>
            </div>
          )}

          {/* Draft */}
          {result.draft && (
            <div style={{ marginBottom: 16 }}>
              <div className="section-label">{t("pipeline.steps.draft")}</div>
              <div
                style={{
                  fontSize: 14,
                  lineHeight: 1.6,
                  marginTop: 6,
                  padding: 12,
                  backgroundColor: "rgba(99,102,241,0.06)",
                  borderRadius: "var(--radius)",
                  border: "1px solid rgba(99,102,241,0.2)",
                  whiteSpace: "pre-wrap",
                }}
              >
                {result.draft}
              </div>
            </div>
          )}

          {/* Metadata */}
          <div
            style={{
              display: "flex",
              gap: 16,
              fontSize: 12,
              color: "var(--color-text-secondary)",
              borderTop: "1px solid var(--color-border)",
              paddingTop: 12,
              marginTop: 12,
            }}
          >
            <span>⏱️ {t("pipeline.processingTime")}: {(result.processing_time_ms / 1000).toFixed(1)}s</span>
            <span>📄 Type: {result.document_type || "Unknown"}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default PipelineWorkflow;
