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

const PRESET_TEMPLATES = [
  {
    id: "full",
    labelEn: "Full Analysis",
    labelFr: "Analyse Complète",
    steps: ["extract", "analyze", "review", "draft", "send"],
  },
  {
    id: "quick",
    labelEn: "Quick Extract",
    labelFr: "Extraction Rapide",
    steps: ["extract"],
  },
  {
    id: "analyze-draft",
    labelEn: "Analyze + Draft",
    labelFr: "Analyser + Rédiger",
    steps: ["extract", "analyze", "draft"],
  },
  {
    id: "review-send",
    labelEn: "Review + Send",
    labelFr: "Réviser + Envoyer",
    steps: ["review", "draft", "send"],
  },
];

function PipelineWorkflow({ document }: PipelineWorkflowProps) {
  const [selectedSteps, setSelectedSteps] = useState<string[]>(["extract", "analyze", "draft"]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [customQuery, setCustomQuery] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [currentStepIdx, setCurrentStepIdx] = useState(-1);
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

  // Simulate step progression during execution
  useEffect(() => {
    if (!running) {
      setCurrentStepIdx(-1);
      return;
    }
    setCurrentStepIdx(0);
    const stepInterval = setInterval(() => {
      setCurrentStepIdx((prev) => {
        if (prev >= selectedSteps.length - 1) return prev;
        return prev + 1;
      });
    }, 4000);
    return () => clearInterval(stepInterval);
  }, [running, selectedSteps.length]);

  const toggleStep = (stepId: string) => {
    setSelectedSteps((prev) =>
      prev.includes(stepId)
        ? prev.filter((s) => s !== stepId)
        : [...prev, stepId]
    );
  };

  const moveStep = (stepId: string, direction: -1 | 1) => {
    setSelectedSteps((prev) => {
      const idx = prev.indexOf(stepId);
      if (idx === -1) return prev;
      const newIdx = idx + direction;
      if (newIdx < 0 || newIdx >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[newIdx]] = [next[newIdx], next[idx]];
      return next;
    });
  };

  const applyPreset = (steps: string[]) => {
    setSelectedSteps(steps);
  };

  const handleRun = async () => {
    if (selectedSteps.length === 0) return;

    const stepCount = selectedSteps.length;
    if (!window.confirm(t("pipeline.confirm", String(stepCount), document.filename))) {
      return;
    }

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
        throw new Error(errData.detail || t("pipeline.toast.error"));
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error("Pipeline execution failed:", err);
      setError(t("pipeline.toast.error"));
    } finally {
      setRunning(false);
    }
  };

  // ── Style constants ─────────────────────────────────

  const cardStyle: React.CSSProperties = {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-lg)",
    padding: 20,
    marginBottom: 20,
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 10,
    color: "var(--color-text)",
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <h2 style={{ fontSize: 22, marginBottom: 8 }}>{t("pipeline.title")}</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", marginBottom: 20 }}>
        {t("pipeline.description")}
      </p>

      {/* Document info */}
      <div style={cardStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          📄 <strong>{document.filename}</strong>
          <span style={{ color: "var(--color-text-secondary)" }}>
            {t("documents.pagesChunks", String(document.pages), String(document.chunks))}
          </span>
        </div>
      </div>

      {/* Preset templates */}
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>⚡ {t("pipeline.presets")}</label>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {PRESET_TEMPLATES.map((tmpl) => {
            const isActive = tmpl.steps.join(",") === selectedSteps.join(",");
            return (
              <button
                key={tmpl.id}
                onClick={() => applyPreset(tmpl.steps)}
                disabled={running}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius)",
                  border: `1px solid ${isActive ? "var(--color-primary)" : "var(--color-border)"}`,
                  backgroundColor: isActive ? "var(--color-primary-bg)" : "var(--color-bg)",
                  color: isActive ? "var(--color-primary)" : "var(--color-text-secondary)",
                  cursor: running ? "not-allowed" : "pointer",
                  fontSize: 12,
                  fontWeight: isActive ? 700 : 500,
                  transition: "all 0.15s ease",
                }}
              >
                {tmpl.labelEn}
              </button>
            );
          })}
        </div>
      </div>

      {/* Step selector with visual flow */}
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>{t("pipeline.steps")}</label>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            flexWrap: "wrap",
            padding: 16,
            backgroundColor: "var(--color-bg)",
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--color-border)",
          }}
        >
          {AVAILABLE_STEPS.map((step, idx) => {
            const isSelected = selectedSteps.includes(step.id);
            const orderIdx = selectedSteps.indexOf(step.id);
            const isInFlow = isSelected;
            const isCurrentlyExecuting = running && isInFlow && selectedSteps.indexOf(step.id) === currentStepIdx;
            const hasBeenExecuted = running && isInFlow && selectedSteps.indexOf(step.id) < currentStepIdx;

            return (
              <div key={step.id} style={{ display: "flex", alignItems: "center", gap: 2 }}>
                {/* Arrow connector between steps */}
                {idx > 0 && <span style={{ color: "var(--color-text-secondary)", fontSize: 12, margin: "0 2px" }}>→</span>}

                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                  <button
                    onClick={() => toggleStep(step.id)}
                    disabled={running}
                    style={{
                      padding: "8px 14px",
                      borderRadius: "var(--radius)",
                      border: `2px solid ${
                        isCurrentlyExecuting
                          ? "var(--color-success)"
                          : isSelected
                          ? "var(--color-primary)"
                          : "var(--color-border)"
                      }`,
                      backgroundColor: isCurrentlyExecuting
                        ? "rgba(34,197,94,0.15)"
                        : isSelected
                        ? "var(--color-primary-bg)"
                        : "var(--color-surface)",
                      color: isCurrentlyExecuting
                        ? "var(--color-success)"
                        : isSelected
                        ? "var(--color-primary)"
                        : "var(--color-text-secondary)",
                      cursor: running ? "not-allowed" : "pointer",
                      fontSize: 13,
                      fontWeight: isSelected ? 700 : 500,
                      transition: "all 0.15s ease",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 1,
                      minWidth: 70,
                      opacity: hasBeenExecuted ? 0.6 : 1,
                      position: "relative",
                    }}
                    title={t(`pipeline.steps.${step.id}.desc`)}
                  >
                    <span style={{ fontSize: 18 }}>{isCurrentlyExecuting ? "⏳" : step.icon}</span>
                    <span style={{ fontSize: 11 }}>{t(`pipeline.steps.${step.id}`)}</span>
                    {isCurrentlyExecuting && (
                      <span
                        style={{
                          position: "absolute",
                          top: -4,
                          right: -4,
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          backgroundColor: "var(--color-success)",
                          animation: "pulse 1s infinite",
                        }}
                      />
                    )}
                  </button>

                  {/* Reorder buttons */}
                  {isSelected && !running && (
                    <div style={{ display: "flex", gap: 4, marginTop: 2 }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); moveStep(step.id, -1); }}
                        disabled={orderIdx === 0}
                        title="Move left"
                        style={{
                          border: "none",
                          background: "none",
                          cursor: orderIdx === 0 ? "default" : "pointer",
                          fontSize: 10,
                          color: orderIdx === 0 ? "var(--color-border)" : "var(--color-text-secondary)",
                          padding: "1px 4px",
                          borderRadius: 4,
                        }}
                      >
                        ◀
                      </button>
                      <span style={{ fontSize: 10, color: "var(--color-text-secondary)" }}>{orderIdx + 1}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); moveStep(step.id, 1); }}
                        disabled={orderIdx === selectedSteps.length - 1}
                        title="Move right"
                        style={{
                          border: "none",
                          background: "none",
                          cursor: orderIdx === selectedSteps.length - 1 ? "default" : "pointer",
                          fontSize: 10,
                          color: orderIdx === selectedSteps.length - 1 ? "var(--color-border)" : "var(--color-text-secondary)",
                          padding: "1px 4px",
                          borderRadius: 4,
                        }}
                      >
                        ▶
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Flow visualization: show order of selected steps */}
        {selectedSteps.length > 1 && !running && (
          <div
            style={{
              marginTop: 10,
              fontSize: 12,
              color: "var(--color-text-secondary)",
              textAlign: "center",
              padding: "6px 12px",
              backgroundColor: "rgba(99,102,241,0.06)",
              borderRadius: "var(--radius)",
            }}
          >
            {selectedSteps.map((id, i) => (
              <span key={id}>
                {i > 0 && <span style={{ margin: "0 6px" }}>→</span>}
                {t(`pipeline.steps.${id}`)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Custom query */}
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>
          {t("pipeline.query")} <span style={{ fontWeight: 400, color: "var(--color-text-secondary)" }}>{t("pipeline.queryOptional")}</span>
        </label>
        <textarea
          value={customQuery}
          onChange={(e) => setCustomQuery(e.target.value)}
          disabled={running}
          placeholder={t("pipeline.queryPlaceholder")}
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
          <span>{t("pipeline.run")} ({t("pipeline.stepsCount", String(selectedSteps.length))})</span>
        )}
      </button>

      {/* Running state */}
      {running && (
        <div style={cardStyle}>
          <div className="progress-bar" style={{ marginBottom: 8 }}>
            <div className="progress-bar-indeterminate" />
          </div>
          <div style={{ fontSize: 13, color: "var(--color-text-secondary)", textAlign: "center", marginBottom: 12 }}>
            ⏳ {t("pipeline.running")}... {t("pipeline.elapsed", String(elapsedSeconds))}
          </div>

          {/* Current step indicator */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 8,
              flexWrap: "wrap",
              marginTop: 8,
            }}
          >
            {selectedSteps.map((id, i) => {
              const step = AVAILABLE_STEPS.find((s) => s.id === id);
              const isDone = i < currentStepIdx;
              const isCurrent = i === currentStepIdx;
              return (
                <div
                  key={id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: "var(--radius)",
                    backgroundColor: isCurrent
                      ? "rgba(34,197,94,0.12)"
                      : isDone
                      ? "rgba(99,102,241,0.08)"
                      : "var(--color-surface)",
                    border: `1px solid ${
                      isCurrent ? "var(--color-success)" : isDone ? "var(--color-primary)" : "var(--color-border)"
                    }`,
                    fontSize: 12,
                    color: isCurrent || isDone ? "var(--color-text)" : "var(--color-text-secondary)",
                    opacity: isDone ? 0.7 : 1,
                  }}
                >
                  {isDone ? "✅" : isCurrent ? "⏳" : step?.icon || "○"}
                  <span>{t(`pipeline.steps.${id}`)}</span>
                </div>
              );
            })}
          </div>
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
        <div style={cardStyle}>
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
            <span>📄 {t("pipeline.type")} {result.document_type || t("pipeline.unknown")}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default PipelineWorkflow;
