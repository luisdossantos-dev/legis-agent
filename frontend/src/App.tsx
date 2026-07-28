import { useState, useEffect, useCallback } from "react";
import Header from "./components/Header";
import DocumentUpload from "./components/DocumentUpload";
import DocumentList from "./components/DocumentList";
import AnalysisResult from "./components/AnalysisResult";
import AgentChat from "./components/AgentChat";
import EmailDraft from "./components/EmailDraft";
import EmailClassifier from "./components/EmailClassifier";
import ActionDetector from "./components/ActionDetector";
import ClauseReview from "./components/ClauseReview";
import UserManager from "./components/UserManager";
import CostDashboard from "./components/CostDashboard";
import PipelineWorkflow from "./components/PipelineWorkflow";
import SettingsModal from "./components/SettingsModal";
import SidebarNav from "./components/SidebarNav";
import ToastContainer, { showToast } from "./components/Toast";
import { apiClient } from "./api/client";
import { t } from "./i18n";
import type { DocumentSummary, AnalysisResult as AnalysisResultType } from "./api/client";

type View = "upload" | "analyze" | "chat" | "email" | "classify" | "action" | "review" | "users" | "dashboard" | "pipeline";

const API_BASE = "http://localhost:8000";
const API_PREFIX = "/api/v1";

async function checkApiConfigured(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}${API_PREFIX}/system/config`);
    const data = await res.json();
    return data.status?.llm_available === true;
  } catch {
    return false;
  }
}

function App() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentSummary | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResultType | null>(null);
  const [currentView, setCurrentView] = useState<View>("upload");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiConfigured, setApiConfigured] = useState(false);

  const checkHealth = useCallback(async () => {
    try {
      const healthy = await apiClient.health();
      setBackendStatus(healthy ? "online" : "offline");
      if (healthy) {
        const configured = await checkApiConfigured();
        setApiConfigured(configured);
      }
    } catch {
      setBackendStatus("offline");
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // Poll for document status changes (processing → indexed)
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === "processing");
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      apiClient.listDocuments().then(setDocuments).catch(console.error);
    }, 2000);

    return () => clearInterval(interval);
  }, [documents]);

  // Show warning toast if backend is online but no API key configured
  useEffect(() => {
    if (backendStatus === "online" && !apiConfigured) {
      showToast(
        "warning",
        t("toast.apiKeyWarning.title"),
        t("toast.apiKeyWarning.message"),
        true
      );
    }
  }, [backendStatus, apiConfigured]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+, or Cmd+, → Open settings
      if ((e.metaKey || e.ctrlKey) && e.key === ",") {
        e.preventDefault();
        setSettingsOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleUploadComplete = () => {
    apiClient.listDocuments().then(setDocuments).catch(console.error);
  };

  const handleSelectDocument = async (doc: DocumentSummary) => {
    // Check API key before analysis
    if (!apiConfigured) {
      showToast(
        "warning",
        t("toast.apiKeyMissing.title"),
        t("toast.apiKeyMissing.analyze"),
        false
      );
      setSettingsOpen(true);
      return;
    }

    setSelectedDoc(doc);
    setCurrentView("analyze");
    setAnalysis(null);

    try {
      const result = await apiClient.analyze(doc.id);
      setAnalysis(result.analysis);
    } catch (err) {
      console.error("Analysis failed:", err);
      showToast("error", t("analysis.toast.error"), t("analysis.toast.error"));
    }
  };

  const handleChat = (doc: DocumentSummary) => {
    if (!apiConfigured) {
      showToast(
        "warning",
        t("toast.apiKeyMissing.title"),
        t("toast.apiKeyMissing.chat"),
        false
      );
      setSettingsOpen(true);
      return;
    }
    setSelectedDoc(doc);
    setCurrentView("chat");
  };

  const handleDraftEmail = (doc: DocumentSummary) => {
    if (!apiConfigured) {
      showToast(
        "warning",
        t("toast.apiKeyMissing.title"),
        t("toast.apiKeyMissing.email"),
        false
      );
      setSettingsOpen(true);
      return;
    }
    setSelectedDoc(doc);
    setCurrentView("email");
  };

  const handlePipeline = (doc: DocumentSummary) => {
    if (!apiConfigured) {
      showToast(
        "warning",
        t("toast.apiKeyMissing.title"),
        t("toast.apiKeyMissing.analyze"),
        false
      );
      setSettingsOpen(true);
      return;
    }
    setSelectedDoc(doc);
    setCurrentView("pipeline");
  };

  const handleSettingsSave = () => {
    checkHealth(); // re-check to update apiConfigured status
  };

  const handleNavigate = (view: string) => {
    // Views that don't require a selected document
    const globalViews = ["email", "classify", "action", "review", "users", "dashboard", "pipeline"];
    if (globalViews.includes(view)) {
      setSelectedDoc(null);
    }
    setCurrentView(view as View);
  };

  return (
    <div className="app">
      <Header
        backendStatus={backendStatus}
        onOpenSettings={() => setSettingsOpen(true)}
        apiConfigured={apiConfigured}
      />

      <main className="main-content">
        <aside className="sidebar" aria-label="Document management">
          <SidebarNav currentView={currentView} onNavigate={handleNavigate} />
          <DocumentUpload onUploadComplete={handleUploadComplete} />
          <DocumentList
            documents={documents}
            onSelect={handleSelectDocument}
            onChat={handleChat}
            onDraftEmail={handleDraftEmail}
            apiConfigured={apiConfigured}
          />
        </aside>

        <section className="content" aria-label="Main content">
          {currentView === "analyze" && selectedDoc && (
            <AnalysisResult
              document={selectedDoc}
              analysis={analysis}
              onChat={handleChat}
              onDraftEmail={handleDraftEmail}
              onPipeline={handlePipeline}
            />
          )}
          {currentView === "chat" && selectedDoc && (
            <AgentChat document={selectedDoc} />
          )}
          {currentView === "email" && (
            <EmailDraft document={selectedDoc} />
          )}
          {currentView === "classify" && (
            <EmailClassifier />
          )}
          {currentView === "action" && (
            <ActionDetector />
          )}
          {currentView === "review" && (
            <ClauseReview />
          )}
          {currentView === "users" && (
            <UserManager />
          )}
          {currentView === "dashboard" && (
            <CostDashboard />
          )}
          {currentView === "pipeline" && selectedDoc && (
            <PipelineWorkflow document={selectedDoc} />
          )}

          {!selectedDoc && currentView !== "email" && currentView !== "classify" && currentView !== "action" && currentView !== "review" && currentView !== "users" && currentView !== "dashboard" && currentView !== "pipeline" && (
            <div className="welcome">
              <h2>{t("welcome.title")}</h2>
              <p>{t("welcome.description")}</p>
              {!apiConfigured && (
                <div
                  role="alert"
                  style={{
                    marginTop: 20,
                    padding: "12px 20px",
                    backgroundColor: "rgba(245,158,11,0.1)",
                    border: "1px solid var(--color-warning)",
                    borderRadius: "var(--radius)",
                    fontSize: 13,
                    color: "var(--color-warning)",
                  }}
                >
                  {t("welcome.noApiKey")}{" "}
                  <button
                    onClick={() => setSettingsOpen(true)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--color-primary)",
                      cursor: "pointer",
                      textDecoration: "underline",
                      fontSize: 13,
                      padding: 0,
                    }}
                  >
                    {t("welcome.openSettings")}
                  </button>{" "}
                  {t("welcome.toAddOne")}
                </div>
              )}
            </div>
          )}
        </section>
      </main>

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSave={handleSettingsSave}
      />

      <ToastContainer />
    </div>
  );
}

export default App;
