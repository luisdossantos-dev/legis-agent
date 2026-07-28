import { useState, useEffect, useCallback } from "react";
import { showToast } from "./Toast";
import UserCreateForm from "./UserCreateForm";
import UserAuditViewer, { type FilterState } from "./UserAuditViewer";

// ── Types ──────────────────────────────────────────────────────

interface User {
  id: string;
  username: string;
  email: string;
  role: "notaire" | "assistant" | "stagiaire" | "admin";
  office: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
}

const ROLE_LABELS: Record<string, { label: string; color: string }> = {
  admin: { label: "Admin", color: "var(--color-error)" },
  notaire: { label: "Notaire", color: "var(--color-primary)" },
  assistant: { label: "Assistant", color: "var(--color-accent)" },
  stagiaire: { label: "Stagiaire", color: "var(--color-warning)" },
};

const API = "http://localhost:8000/api/v1/rbac";

// ── Component ───────────────────────────────────────────────────

function UserManager() {
  const [users, setUsers] = useState<User[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"users" | "audit" | "gdpr">("users");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [auditFilter, setAuditFilter] = useState<FilterState>({ username: "", action: "", dateRange: 0 });

  const fetchUsers = useCallback(async () => {
    try {
      const res = await fetch(`${API}/users`);
      if (res.ok) setUsers(await res.json());
    } catch {
      // Users endpoint may not be available if backend is offline
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAudit = useCallback(async () => {
    try {
      const res = await fetch(`${API}/audit?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setAuditLog(data.entries || []);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchUsers();
    fetchAudit();
  }, [fetchUsers, fetchAudit]);

  const handleDeleteUser = async (user: User) => {
    if (!confirm(`Are you sure you want to anonymize "${user.username}"? This cannot be undone (GDPR right to erasure).`)) {
      return;
    }
    try {
      const res = await fetch(`${API}/users/${user.id}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to delete user");
      }
      showToast("info", "User anonymized", `"${user.username}" has been anonymized (GDPR Article 17).`);
      fetchUsers();
      fetchAudit();
    } catch (err) {
      console.error("User delete failed:", err);
      showToast("error", "Delete failed", "Unknown error");
    }
  };

  const handleExport = async (user: User) => {
    setExportingId(user.id);
    try {
      const res = await fetch(`${API}/export/${user.id}`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Export failed");
      }
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `gdpr-export-${user.username}-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("info", "Export downloaded", `GDPR data export for "${user.username}" saved.`);
      fetchAudit();
    } catch (err) {
      console.error("Export failed:", err);
      showToast("error", "Export failed", "Unknown error");
    } finally {
      setExportingId(null);
    }
  };

  const handleCreated = () => {
    setShowCreateForm(false);
    fetchUsers();
    fetchAudit();
  };

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <h2 style={{ fontSize: 22, marginBottom: 8 }}>🔐 User Management & GDPR</h2>
      <p style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 20 }}>
        Role-based access control, audit trails, and GDPR compliance tools.
      </p>

      {/* ── Tab bar ─────────────────────────────── */}
      <div role="tablist" aria-label="User management sections" style={{ display: "flex", gap: 8, marginBottom: 20, borderBottom: "1px solid var(--color-border)", paddingBottom: 8 }}>
        {[
          { id: "users" as const, label: "👥 Users", desc: "Manage users & roles" },
          { id: "audit" as const, label: "📋 Audit Trail", desc: "Interaction history" },
          { id: "gdpr" as const, label: "🛡️ GDPR", desc: "Compliance status" },
        ].map((tab) => (
          <button
            key={tab.id} id={`tab-${tab.id}`} role="tab"
            aria-selected={activeTab === tab.id} aria-controls={`panel-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "10px 18px",
              borderRadius: "var(--radius)",
              border: activeTab === tab.id ? "1px solid var(--color-primary)" : "1px solid transparent",
              backgroundColor: activeTab === tab.id ? "rgba(99,102,241,0.1)" : "transparent",
              color: activeTab === tab.id ? "var(--color-primary)" : "var(--color-text-secondary)",
              cursor: "pointer", fontSize: 13,
              fontWeight: activeTab === tab.id ? 600 : 400,
              textAlign: "left",
            }}
          >
            <div>{tab.label}</div>
            <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{tab.desc}</div>
          </button>
        ))}
      </div>

      {/* ═══════════════════════════════════════════ */}
      {/* TAB: Users                                 */}
      {/* ═══════════════════════════════════════════ */}
      {activeTab === "users" && (
        <div role="tabpanel" id="panel-users" aria-labelledby="tab-users">
          <div style={{ marginBottom: 16, display: "flex", justifyContent: "flex-end" }}>
            <button onClick={() => setShowCreateForm(!showCreateForm)} className="doc-btn" style={{ fontWeight: 600, padding: "8px 20px" }}>
              {showCreateForm ? "✕ Cancel" : "➕ New User"}
            </button>
          </div>

          {showCreateForm && (
            <UserCreateForm onCreated={handleCreated} onCancel={() => setShowCreateForm(false)} />
          )}

          {loading ? (
            <div className="loading" style={{ padding: 24, textAlign: "center" }} role="status" aria-live="polite">Loading users...</div>
          ) : users.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-secondary)", fontSize: 13 }}>
              No users configured. The system is running in open access mode.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {users.map((user) => {
                const roleInfo = ROLE_LABELS[user.role] || ROLE_LABELS.stagiaire;
                return (
                  <div key={user.id} style={{ padding: "14px 18px", borderRadius: "var(--radius)", border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)", display: "flex", alignItems: "center", justifyContent: "space-between", opacity: user.is_active ? 1 : 0.5 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      <div style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: roleInfo.color + "20", color: roleInfo.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700 }}>
                        {user.display_name?.[0]?.toUpperCase() || user.username[0].toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14 }}>
                          {user.display_name || user.username}
                          {!user.is_active && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--color-error)" }}>INACTIVE</span>}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
                          @{user.username} · {user.email} · {user.office}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span style={{ padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600, backgroundColor: roleInfo.color + "20", color: roleInfo.color }}>
                        {roleInfo.label}
                      </span>
                      <button onClick={() => handleExport(user)} disabled={exportingId === user.id} className="doc-btn" title="GDPR data export" aria-label={`Export GDPR data for ${user.display_name || user.username}`}>
                        {exportingId === user.id ? "⏳" : "📦"}
                      </button>
                      <button onClick={() => handleDeleteUser(user)} className="doc-btn" title="Anonymize (right to erasure)" aria-label={`Anonymize data for ${user.display_name || user.username}`} style={{ color: "var(--color-error)" }}>
                        🧹
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════ */}
      {/* TAB: Audit Trail                            */}
      {/* ═══════════════════════════════════════════ */}
      {activeTab === "audit" && (
        <UserAuditViewer
          entries={auditLog}
          onRefresh={fetchAudit}
          filter={auditFilter}
          onFilterChange={setAuditFilter}
        />
      )}

      {/* ═══════════════════════════════════════════ */}
      {/* TAB: GDPR Status                            */}
      {/* ═══════════════════════════════════════════ */}
      {activeTab === "gdpr" && (
        <div role="tabpanel" id="panel-gdpr" aria-labelledby="tab-gdpr">
          <div style={{ padding: 20, borderRadius: "var(--radius-lg)", border: "1px solid var(--color-success)", backgroundColor: "rgba(34,197,94,0.05)", marginBottom: 20 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-success)", marginBottom: 8 }}>🛡️ GDPR Compliance Status</div>
            <div style={{ fontSize: 13, color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
              <div>✅ Audit trail: <strong>Active</strong> — every interaction is logged with user_id, role, office, timestamp</div>
              <div>✅ Right to erasure: <strong>Implemented</strong> — user data can be anonymized (GDPR Article 17)</div>
              <div>✅ Data portability: <strong>Implemented</strong> — full user data export available (GDPR Article 20)</div>
              <div>✅ Sensitive data routing: <strong>Monitored</strong> — PII detection warns when data goes to external APIs</div>
              <div>📁 Audit file: <code style={{ fontSize: 11 }}>logs/audit/audit_trail.jsonl</code></div>
            </div>
          </div>

          <div style={{ padding: 20, borderRadius: "var(--radius-lg)", border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)" }}>
            <h3 style={{ fontSize: 16, marginBottom: 12 }}>Role Permission Matrix</h3>
            <div style={{ fontSize: 13, lineHeight: 1.8 }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                    <th style={{ textAlign: "left", padding: "8px 12px" }}>Permission</th>
                    <th style={{ textAlign: "center", padding: "8px" }}>Admin</th>
                    <th style={{ textAlign: "center", padding: "8px" }}>Notaire</th>
                    <th style={{ textAlign: "center", padding: "8px" }}>Assistant</th>
                    <th style={{ textAlign: "center", padding: "8px" }}>Stagiaire</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Read", "✅", "✅", "✅", "✅"],
                    ["Write", "✅", "✅", "✅", "❌"],
                    ["Draft", "✅", "✅", "✅", "❌"],
                    ["Finalize", "✅", "✅", "❌", "❌"],
                    ["Delete", "✅", "✅", "❌", "❌"],
                    ["Admin", "✅", "❌", "❌", "❌"],
                  ].map(([perm, ...roles]) => (
                    <tr key={perm} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <td style={{ padding: "6px 12px", fontWeight: 600 }}>{perm}</td>
                      {roles.map((v, i) => (
                        <td key={i} style={{ textAlign: "center", padding: "6px", fontSize: 16 }}>{v}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserManager;
