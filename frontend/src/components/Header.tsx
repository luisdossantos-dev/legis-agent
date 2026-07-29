import { useState, useEffect } from "react";
import { useLanguage, t, type Lang } from "../i18n";

interface HeaderProps {
  backendStatus: "checking" | "online" | "offline";
  onOpenSettings: () => void;
  apiConfigured: boolean;
}

function Header({ backendStatus, onOpenSettings, apiConfigured }: HeaderProps) {
  const { lang, setLanguage } = useLanguage();

  // ── Theme management ──────────────────────────
  const [theme, setTheme] = useState<string>(() => {
    return localStorage.getItem("legis-theme") || "light";
  });

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("legis-theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const statusLabels: Record<string, string> = {
    checking: t("header.status.checking"),
    online: apiConfigured ? t("header.status.connected") : t("status.noApiKey"),
    offline: t("header.status.disconnected"),
  };

  return (
    <header className="header">
      <div className="header-left">
        <span className="header-logo">{t("app.name")}</span>
        {!apiConfigured && backendStatus === "online" && (
          <span
            onClick={onOpenSettings}
            style={{
              fontSize: 11,
              color: "var(--color-warning)",
              backgroundColor: "rgba(245,158,11,0.12)",
              border: "1px solid var(--color-warning)",
              borderRadius: "var(--radius)",
              padding: "2px 10px",
              cursor: "pointer",
              fontWeight: 600,
              whiteSpace: "nowrap",
            }}
            title="Configure API Key"
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter') onOpenSettings(); }}
          >
            ⚠️ {t("status.noApiKey")}
          </span>
        )}
      </div>
      <div className="header-right">
        {/* ── Language switcher ─────────────────── */}
        <select
          value={lang}
          onChange={(e) => setLanguage(e.target.value as Lang)}
          aria-label="Language / Langue"
          style={{
            padding: "4px 6px",
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-bg)",
            color: "var(--color-text)",
            fontSize: 12,
            cursor: "pointer",
            outline: "none",
          }}
        >
          <option value="en">{t("language.en")}</option>
          <option value="fr">{t("language.fr")}</option>
        </select>

        <span
          className={`status-dot ${backendStatus}`}
          title={statusLabels[backendStatus]}
          aria-hidden="true"
        />
        <span
          style={{ fontSize: 13, color: "var(--color-text-secondary)" }}
          role="status"
          aria-live="polite"
        >
          {statusLabels[backendStatus]}
        </span>
        <button
          className="doc-btn keep-visible"
          onClick={toggleTheme}
          title={t("header.theme")}
          aria-label={t("header.theme")}
          style={{ fontWeight: 600, fontSize: 16 }}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
        <button
          className="doc-btn keep-visible"
          onClick={onOpenSettings}
          title={t("header.settings")}
          aria-label={t("header.settings")}
          style={{ fontWeight: 600 }}
        >
          ⚙️
        </button>
      </div>
    </header>
  );
}

export default Header;
