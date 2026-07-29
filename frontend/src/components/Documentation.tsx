import { t } from "../i18n";

// ── Style helpers ──────────────────────────────

const pageStyle: React.CSSProperties = {
  maxWidth: 900,
  margin: "0 auto",
  paddingBottom: 40,
};

const sectionStyle: React.CSSProperties = {
  marginBottom: 28,
  padding: 20,
  backgroundColor: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-lg)",
};

const headingStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
  marginBottom: 8,
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const subheadingStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 600,
  marginTop: 16,
  marginBottom: 6,
  color: "var(--color-text)",
};

const textStyle: React.CSSProperties = {
  fontSize: 14,
  lineHeight: 1.7,
  color: "var(--color-text-secondary)",
  marginBottom: 8,
};

const kbdStyle: React.CSSProperties = {
  padding: "2px 6px",
  borderRadius: 4,
  border: "1px solid var(--color-border)",
  backgroundColor: "var(--color-bg)",
  fontFamily: "monospace",
  fontSize: 12,
};

const listStyle: React.CSSProperties = {
  fontSize: 14,
  lineHeight: 1.8,
  color: "var(--color-text-secondary)",
  paddingLeft: 20,
  marginBottom: 8,
};

function Section({
  icon,
  title,
  children,
}: {
  icon: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={sectionStyle}>
      <h3 style={headingStyle}>
        <span>{icon}</span> {title}
      </h3>
      {children}
    </div>
  );
}

function Documentation() {
  return (
    <div style={pageStyle}>
      <h2 style={{ fontSize: 26, marginBottom: 4 }}>📖 {t("docs.title")}</h2>
      <p style={{ ...textStyle, marginBottom: 24 }}>
        {t("docs.description")}
      </p>

      {/* ── Overview ───────────────────────────── */}
      <Section icon="🏠" title={t("docs.overview")}>
        <p style={textStyle}>{t("docs.overviewText")}</p>
      </Section>

      {/* ── Document Upload & Analysis ────────── */}
      <Section icon="📄" title={t("docs.uploadTitle")}>
        <p style={textStyle}>{t("docs.uploadText")}</p>
        <div style={subheadingStyle}>{t("docs.steps")}</div>
        <ol style={listStyle}>
          <li>{t("docs.uploadStep1")}</li>
          <li>{t("docs.uploadStep2")}</li>
          <li>{t("docs.uploadStep3")}</li>
          <li>{t("docs.uploadStep4")}</li>
        </ol>
        <p style={textStyle}>
          <strong>{t("docs.supportedFormats")}:</strong> PDF, DOCX, TXT
        </p>
      </Section>

      {/* ── Chat ──────────────────────────────── */}
      <Section icon="💬" title={t("docs.chatTitle")}>
        <p style={textStyle}>{t("docs.chatText")}</p>
        <div style={subheadingStyle}>{t("docs.shortcuts")}</div>
        <ul style={listStyle}>
          <li>
            <kbd style={kbdStyle}>Ctrl+Enter</kbd> — {t("docs.shortcutSend")}
          </li>
          <li>
            <kbd style={kbdStyle}>Ctrl+U</kbd> — {t("docs.shortcutUpload")}
          </li>
          <li>
            <kbd style={kbdStyle}>Ctrl+K</kbd> — {t("docs.shortcutPalette")}
          </li>
          <li>
            <kbd style={kbdStyle}>Ctrl+,</kbd> — {t("docs.shortcutSettings")}
          </li>
          <li>
            <kbd style={kbdStyle}>Ctrl+1–7</kbd> — {t("docs.shortcutNav")}
          </li>
          <li>
            <kbd style={kbdStyle}>Esc</kbd> — {t("docs.shortcutClose")}
          </li>
        </ul>
      </Section>

      {/* ── Email Drafting ────────────────────── */}
      <Section icon="📧" title={t("docs.emailTitle")}>
        <p style={textStyle}>{t("docs.emailText")}</p>
        <ul style={listStyle}>
          <li>{t("docs.emailBullet1")}</li>
          <li>{t("docs.emailBullet2")}</li>
          <li>{t("docs.emailBullet3")}</li>
        </ul>
      </Section>

      {/* ── Email Classification ──────────────── */}
      <Section icon="📬" title={t("docs.classifyTitle")}>
        <p style={textStyle}>{t("docs.classifyText")}</p>
        <ul style={listStyle}>
          <li>{t("docs.classifyBullet1")}</li>
          <li>{t("docs.classifyBullet2")}</li>
        </ul>
      </Section>

      {/* ── Action Detection ──────────────────── */}
      <Section icon="⚡" title={t("docs.actionTitle")}>
        <p style={textStyle}>{t("docs.actionText")}</p>
      </Section>

      {/* ── Clause Review ─────────────────────── */}
      <Section icon="🔍" title={t("docs.reviewTitle")}>
        <p style={textStyle}>{t("docs.reviewText")}</p>
      </Section>

      {/* ── Pipeline ──────────────────────────── */}
      <Section icon="🔧" title={t("docs.pipelineTitle")}>
        <p style={textStyle}>{t("docs.pipelineText")}</p>
        <div style={subheadingStyle}>{t("docs.steps")}</div>
        <ol style={listStyle}>
          <li>{t("docs.pipelineStep1")}</li>
          <li>{t("docs.pipelineStep2")}</li>
          <li>{t("docs.pipelineStep3")}</li>
          <li>{t("docs.pipelineStep4")}</li>
        </ol>
        <p style={textStyle}>
          <strong>{t("docs.pipelinePresets")}:</strong>{" "}
          {t("docs.pipelinePresetsText")}
        </p>
      </Section>

      {/* ── Dashboard ─────────────────────────── */}
      <Section icon="📊" title={t("docs.dashboardTitle")}>
        <p style={textStyle}>{t("docs.dashboardText")}</p>
        <ul style={listStyle}>
          <li>{t("docs.dashboardBullet1")}</li>
          <li>{t("docs.dashboardBullet2")}</li>
          <li>{t("docs.dashboardBullet3")}</li>
        </ul>
      </Section>

      {/* ── User Management ───────────────────── */}
      <Section icon="🔐" title={t("docs.usersTitle")}>
        <p style={textStyle}>{t("docs.usersText")}</p>
      </Section>

      {/* ── Settings ──────────────────────────── */}
      <Section icon="⚙️" title={t("docs.settingsTitle")}>
        <p style={textStyle}>{t("docs.settingsText")}</p>
      </Section>

      {/* ── Language & Theme ──────────────────── */}
      <Section icon="🌐" title={t("docs.langThemeTitle")}>
        <p style={textStyle}>{t("docs.langThemeText1")}</p>
        <p style={textStyle}>{t("docs.langThemeText2")}</p>
      </Section>
    </div>
  );
}

export default Documentation;
