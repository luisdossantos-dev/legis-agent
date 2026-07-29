import { useState, useEffect, useCallback } from "react";

interface Toast {
  id: number;
  type: "success" | "warning" | "error" | "info";
  title: string;
  message: string;
  autoClose?: boolean;
}

let toastIdCounter = 0;
let addToastFn: ((t: Omit<Toast, "id">) => void) | null = null;

export function showToast(
  type: Toast["type"],
  title: string,
  message: string,
  autoClose = true
) {
  if (addToastFn) {
    addToastFn({ type, title, message, autoClose });
  }
}

function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((t: Omit<Toast, "id">) => {
    const id = ++toastIdCounter;
    setToasts((prev) => [...prev, { ...t, id }]);

    if (t.autoClose !== false) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== id));
      }, 6000);
    }
  }, []);

  useEffect(() => {
    addToastFn = addToast;
    return () => {
      addToastFn = null;
    };
  }, [addToast]);

  const removeToast = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const colors = {
    success: {
      bg: "rgba(34,197,94,0.12)",
      border: "var(--color-success)",
      icon: "✓",
    },
    warning: {
      bg: "rgba(245,158,11,0.12)",
      border: "var(--color-warning)",
      icon: "⚠️",
    },
    error: {
      bg: "rgba(239,68,68,0.12)",
      border: "var(--color-error)",
      icon: "✕",
    },
    info: {
      bg: "rgba(6,182,212,0.12)",
      border: "var(--color-accent)",
      icon: "ℹ",
    },
  };

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Notifications"
      style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        zIndex: 2000,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        maxWidth: 380,
      }}
    >
      {toasts.map((toast) => {
        const c = colors[toast.type];
        return (
          <div
            key={toast.id}
            style={{
              backgroundColor: c.bg,
              border: `1px solid ${c.border}`,
              borderRadius: "var(--radius)",
              padding: "12px 16px",
              boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
              animation: "slideIn 0.2s ease",
              display: "flex",
              gap: 10,
              alignItems: "flex-start",
            }}
          >
            <span style={{ fontSize: 16, flexShrink: 0 }} aria-hidden="true">{c.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 13,
                  marginBottom: 2,
                  color: c.border,
                }}
              >
                {toast.title}
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--color-text-secondary)",
                  lineHeight: 1.4,
                }}
              >
                {toast.message}
              </div>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              aria-label="Close notification"
              style={{
                background: "none",
                border: "none",
                color: "var(--color-text-secondary)",
                cursor: "pointer",
                fontSize: 14,
                padding: 0,
                flexShrink: 0,
              }}
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default ToastContainer;
