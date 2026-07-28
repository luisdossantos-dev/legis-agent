import { useState, useCallback, useEffect } from "react";
import { t } from "../i18n";

interface ProviderField {
  key: string;
  label: string;
  type: "password" | "text";
  placeholder: string;
}

interface ProviderOption {
  id: string;
  label: string;
  litellm_prefix: string;
  docs_url: string;
  default_model: string;
  models: string[];
  fields: ProviderField[];
  defaults: Record<string, string>;
  configured: boolean;
  current_model: string;
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
}

function SettingsModal({ isOpen, onClose, onSave }: SettingsModalProps) {
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [activeProvider, setActiveProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [extraFields, setExtraFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [wasConfigured, setWasConfigured] = useState(false);

  // Load providers and current config when modal opens
  useEffect(() => {
    if (!isOpen) return;
    fetch("http://localhost:8000/api/v1/system/config")
      .then((r) => r.json())
      .then((data) => {
        setProviders(data.providers || []);
        const active = data.status?.active_provider || "openai";
        setActiveProvider(active);

        // Pre-fill from saved config
        const providerData = data.providers?.find((p: ProviderOption) => p.id === active);
        if (providerData) {
          // Track if this provider had a key saved (backend never returns the actual key for security)
          setWasConfigured(!!providerData.configured);
          setApiKey("");
          setModel(providerData.current_model || providerData.default_model);
          // Pre-fill extra fields with saved or default values
          const savedExtra: Record<string, string> = {};
          for (const field of providerData.fields) {
            if (field.key !== "api_key") {
              savedExtra[field.key] = providerData.defaults[field.key] || "";
            }
          }
          setExtraFields(savedExtra);
        }
      })
      .catch(() => setMessage({ type: "error", text: t("settings.configError") }));
  }, [isOpen]);

  const currentProvider = providers.find((p) => p.id === activeProvider);

  const switchProvider = (pid: string) => {
    setActiveProvider(pid);
    setApiKey("");
    const p = providers.find((pr) => pr.id === pid);
    if (p) {
      setWasConfigured(!!p.configured);
      setModel(p.current_model || p.default_model);
      // Pre-fill defaults for extra fields
      const defaults: Record<string, string> = {};
      for (const field of p.fields) {
        if (field.key !== "api_key") {
          defaults[field.key] = p.defaults[field.key] || "";
        }
      }
      setExtraFields(defaults);
    }
    setMessage(null);
  };

  const handleSave = useCallback(async () => {
    // If the provider was previously configured and user didn't enter a new key,
    // don't send api_key (backend keeps the saved one)
    if (!apiKey && !wasConfigured && !Object.values(extraFields).some(Boolean)) {
      setMessage({ type: "error", text: t("settings.keyRequired") });
      return;
    }

    setSaving(true);
    setMessage(null);

    // Extract short model name (strip prefix like "openai/" if present)
    let shortModel = model;
    if (currentProvider && shortModel.startsWith(currentProvider.litellm_prefix + "/")) {
      shortModel = shortModel.slice(currentProvider.litellm_prefix.length + 1);
    }

    const body: Record<string, string> = {
      provider: activeProvider,
      model: shortModel || "",
    };

    // Only send api_key if the user entered one (don't overwrite saved key)
    if (apiKey) {
      body.api_key = apiKey;
    }

    // Add extra fields (api_base, api_version)
    for (const [key, val] of Object.entries(extraFields)) {
      if (val) body[key] = val;
    }

    try {
      const res = await fetch("http://localhost:8000/api/v1/system/config/provider", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Save failed");
      }

      const responseData = await res.json();
      setMessage({
        type: "success",
        text: `${t("settings.saveSuccess", currentProvider?.label || "Provider")} ${responseData.status?.llm_available ? "✅ LLM ready" : "⚠️ LLM not available"}`,
      });
      setTimeout(() => {
        onSave();
        onClose();
      }, 1200);
    } catch (err) {
      console.error("Settings save failed:", err);
      setMessage({
        type: "error",
        text: t("settings.saveError"),
      });
    } finally {
      setSaving(false);
    }
  }, [activeProvider, apiKey, model, extraFields, currentProvider, onSave, onClose]);

  if (!isOpen) return null;

  const settingsTitleId = "settings-dialog-title";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby={settingsTitleId}
    >
      <div
        style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          padding: 28,
          width: 520,
          maxWidth: "90vw",
          maxHeight: "85vh",
          overflowY: "auto",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ─────────────────────────────── */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 20,
          }}
        >
          <h2 id={settingsTitleId} style={{ margin: 0, fontSize: 20 }}>⚙️ Settings</h2>
          <button
            onClick={onClose}
            aria-label="Close settings"
            style={{
              background: "none",
              border: "none",
              color: "var(--color-text-secondary)",
              fontSize: 20,
              cursor: "pointer",
              padding: "4px 8px",
            }}
          >
            ✕
          </button>
        </div>

        {/* ── Provider dropdown ──────────────────── */}
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
            {t("settings.provider")}
          </label>
          <select
            value={activeProvider}
            onChange={(e) => switchProvider(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-bg)",
              color: "var(--color-text)",
              fontSize: 14,
              outline: "none",
              cursor: "pointer",
              boxSizing: "border-box",
              appearance: "auto",
            }}
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label} {p.configured ? "✓" : ""}
              </option>
            ))}
          </select>
        </div>

        {currentProvider && (
          <>
            {/* ── Provider info ────────────────────── */}
            <p style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 16 }}>
              {t("settings.getKeyFrom", "")}
              <a
                href={currentProvider.docs_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "var(--color-primary)" }}
              >
                {currentProvider.docs_url}
              </a>
            </p>

            {/* ── API Key ──────────────────────────── */}
            <div style={{ marginBottom: 14 }}>
              <label
                style={{
                  display: "block",
                  fontSize: 13,
                  fontWeight: 600,
                  marginBottom: 6,
                  color: "var(--color-text)",
                }}
              >
                {t("settings.apiKey")}
              </label>
              <input
                type="password"
                placeholder={currentProvider.fields.find((f) => f.key === "api_key")?.placeholder || "..."}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-bg)",
                  color: "var(--color-text)",
                  fontSize: 14,
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              {currentProvider.configured && (
                <div style={{ fontSize: 11, color: "var(--color-success)", marginTop: 4 }}>
                  {t("settings.keepKey")}
                </div>
              )}
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginTop: 6, fontStyle: "italic" }}>
                {t("settings.persistsNote")}
              </div>
            </div>

            {/* ── Model selector ──────────────────── */}
            <div style={{ marginBottom: 14 }}>
              <label
                style={{
                  display: "block",
                  fontSize: 13,
                  fontWeight: 600,
                  marginBottom: 6,
                  color: "var(--color-text)",
                }}
              >
                {t("settings.model")}
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-bg)",
                  color: "var(--color-text)",
                  fontSize: 14,
                  outline: "none",
                  cursor: "pointer",
                  boxSizing: "border-box",
                  appearance: "auto",
                }}
              >
                {currentProvider.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            {/* ── Extra fields (api_base, api_version) ─── */}
            {currentProvider.fields
              .filter((f) => f.key !== "api_key")
              .map((field) => (
                <div key={field.key} style={{ marginBottom: 14 }}>
                  <label
                    style={{
                      display: "block",
                      fontSize: 13,
                      fontWeight: 600,
                      marginBottom: 6,
                      color: "var(--color-text)",
                    }}
                  >
                    {field.label}
                  </label>
                  <input
                    type={field.type}
                    placeholder={field.placeholder}
                    value={extraFields[field.key] ?? ""}
                    onChange={(e) =>
                      setExtraFields((prev) => ({ ...prev, [field.key]: e.target.value }))
                    }
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: "var(--radius)",
                      border: "1px solid var(--color-border)",
                      backgroundColor: "var(--color-bg)",
                      color: "var(--color-text)",
                      fontSize: 14,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
              ))}

            {/* ── Status ───────────────────────────── */}
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius)",
                fontSize: 12,
                backgroundColor: currentProvider.configured
                  ? "rgba(34,197,94,0.08)"
                  : "rgba(245,158,11,0.08)",
                color: currentProvider.configured
                  ? "var(--color-success)"
                  : "var(--color-warning)",
                marginBottom: 16,
                border: `1px solid ${
                  currentProvider.configured
                    ? "var(--color-success)"
                    : "var(--color-warning)"
                }`,
              }}
            >
              {currentProvider.configured
                ? t("settings.configured")
                : t("settings.notConfigured")}
            </div>
          </>
        )}

        {/* ── Message ─────────────────────────────── */}
        {message && (
          <div
            role="alert"
            style={{
              padding: "10px 14px",
              borderRadius: "var(--radius)",
              fontSize: 13,
              marginBottom: 16,
              backgroundColor:
                message.type === "success"
                  ? "rgba(34,197,94,0.1)"
                  : "rgba(239,68,68,0.1)",
              color:
                message.type === "success"
                  ? "var(--color-success)"
                  : "var(--color-error)",
              border: `1px solid ${
                message.type === "success"
                  ? "var(--color-success)"
                  : "var(--color-error)"
              }`,
            }}
          >
            {message.text}
          </div>
        )}

        {/* ── Actions ──────────────────────────────── */}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button
            onClick={onClose}
            style={{
              padding: "10px 20px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-border)",
              backgroundColor: "transparent",
              color: "var(--color-text)",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            {t("app.cancel")}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: "10px 20px",
              borderRadius: "var(--radius)",
              border: "none",
              backgroundColor: "var(--color-primary)",
              color: "white",
              cursor: saving ? "not-allowed" : "pointer",
              fontSize: 14,
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? t("settings.saving") : t("settings.saveActivate")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;
