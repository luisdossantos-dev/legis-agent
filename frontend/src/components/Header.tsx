import { useLanguage, t, type Lang } from "../i18n";

interface HeaderProps {
  backendStatus: "checking" | "online" | "offline";
  onRefresh: () => void;
  onOpenSettings: () => void;
  onNewEmail: () => void;
  onClassify: () => void;
  onAction: () => void;
  onReview: () => void;
  onUsers: () => void;
  onDashboard: () => void;
  apiConfigured: boolean;
}

function Header({ backendStatus, onRefresh, onOpenSettings, onNewEmail, onClassify, onAction, onReview, onUsers, onDashboard, apiConfigured }: HeaderProps) {
  const { lang, setLanguage } = useLanguage();

  const statusLabels: Record<string, string> = {
    checking: t("header.status.checking"),
    online: apiConfigured ? t("header.status.connected") : t("status.noApiKey"),
    offline: t("header.status.disconnected"),
  };

  return (
    <header className="header">
      <div className="header-left">
        <span className="header-logo">{t("app.name")}</span>
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

        <button
          className="doc-btn"
          onClick={onNewEmail}
          title={t("header.email")}
          aria-label={t("header.email")}
          style={{ fontWeight: 600 }}
        >
          {t("header.email")}
        </button>
        <button
          className="doc-btn"
          onClick={onClassify}
          title={t("header.classify")}
          aria-label={t("header.classify")}
          style={{ fontWeight: 600 }}
        >
          {t("header.classify")}
        </button>
        <button
          className="doc-btn"
          onClick={onAction}
          title={t("header.actions")}
          aria-label={t("header.actions")}
          style={{ fontWeight: 600 }}
        >
          {t("header.actions")}
        </button>
        <button
          className="doc-btn"
          onClick={onReview}
          title={t("header.review")}
          aria-label={t("header.review")}
          style={{ fontWeight: 600 }}
        >
          {t("header.review")}
        </button>
        <button
          className="doc-btn"
          onClick={onDashboard}
          title={t("header.dashboard")}
          aria-label={t("header.dashboard")}
          style={{ fontWeight: 600 }}
        >
          {t("header.dashboard")}
        </button>
        <button
          className="doc-btn"
          onClick={onUsers}
          title={t("header.users")}
          aria-label={t("header.users")}
          style={{ fontWeight: 600 }}
        >
          {t("header.users")}
        </button>
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
        {!apiConfigured && backendStatus === "online" && (
          <span style={{ fontSize: 12, color: "var(--color-warning)" }} aria-hidden="true">
            ⚠️
          </span>
        )}
        <button
          className="doc-btn"
          onClick={onOpenSettings}
          title={t("header.settings")}
          aria-label={t("header.settings")}
          style={{ fontWeight: 600 }}
        >
          ⚙️
        </button>
        <button
          className="doc-btn"
          onClick={onRefresh}
          title={t("header.refresh")}
          aria-label={t("header.refresh")}
        >
          ↻
        </button>
      </div>
    </header>
  );
}

export default Header;
