/**
 * Shared style objects for consistent UI across components.
 * Use these instead of repeating inline styles.
 */

import type { CSSProperties } from "react";

/** Base input / textarea / select field */
export const inputBase: CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: "var(--radius)",
  border: "1px solid var(--color-border)",
  backgroundColor: "var(--color-bg)",
  color: "var(--color-text)",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
};

/** Error / alert box */
export const errorBox: CSSProperties = {
  marginTop: 16,
  padding: 12,
  backgroundColor: "rgba(239,68,68,0.1)",
  border: "1px solid var(--color-error)",
  borderRadius: "var(--radius)",
  color: "var(--color-error)",
  fontSize: 13,
};

/** Card container */
export const cardStyle: CSSProperties = {
  padding: 20,
  backgroundColor: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-lg)",
};

/** Inline label (matches .section-label sizing) */
export const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 6,
  color: "var(--color-text)",
};

/** Primary action button */
export const primaryBtn: CSSProperties = {
  padding: "12px 28px",
  backgroundColor: "var(--color-primary)",
  color: "white",
  border: "none",
  borderRadius: "var(--radius)",
  cursor: "pointer",
  fontSize: 14,
  fontWeight: 600,
};
