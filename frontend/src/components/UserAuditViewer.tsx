import { useMemo } from "react";

interface AuditEntry {
  id: string;
  timestamp: string;
  user_id: string;
  username: string;
  role: string;
  office: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details: string;
  ip_address: string;
}

const actionIcons: Record<string, string> = {
  login: "🔑", logout: "🚪", create: "➕", update: "✏️",
  delete: "🗑️", read: "👁️", export: "📦", forget: "🧹",
  analysis: "📊", draft: "✍️", finalize: "✅", chat: "💬",
};

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function getDateDaysAgo(days: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d;
}

interface FilterState {
  username: string;
  action: string;
  dateRange: number; // 0 = all, 1 = 24h, 7 = 7d, 30 = 30d
}

interface UserAuditViewerProps {
  entries: AuditEntry[];
  onRefresh: () => void;
  filter: FilterState;
  onFilterChange: (filter: FilterState) => void;
}

const ACTION_OPTIONS = [
  { value: "", label: "All actions" },
  { value: "analysis", label: "📊 Analysis" },
  { value: "chat", label: "💬 Chat" },
  { value: "draft", label: "✍️ Draft" },
  { value: "create", label: "➕ Create" },
  { value: "read", label: "👁️ Read" },
  { value: "update", label: "✏️ Update" },
  { value: "delete", label: "🗑️ Delete" },
  { value: "login", label: "🔑 Login" },
  { value: "logout", label: "🚪 Logout" },
  { value: "export", label: "📦 Export" },
  { value: "forget", label: "🧹 Forget" },
];

function UserAuditViewer({ entries, onRefresh, filter, onFilterChange }: UserAuditViewerProps) {
  // Extract unique usernames from entries
  const usernames = useMemo(() => {
    const set = new Set(entries.map((e) => e.username));
    return Array.from(set).sort();
  }, [entries]);

  // Filter entries client-side for instant feedback
  const filtered = useMemo(() => {
    let result = entries;

    if (filter.username) {
      result = result.filter((e) => e.username === filter.username);
    }
    if (filter.action) {
      result = result.filter((e) => e.action === filter.action);
    }
    if (filter.dateRange > 0) {
      const cutoff = getDateDaysAgo(filter.dateRange);
      result = result.filter((e) => new Date(e.timestamp) >= cutoff);
    }

    return result;
  }, [entries, filter]);

  return (
    <div role="tabpanel" id="panel-audit" aria-labelledby="tab-audit">
      {/* ── Filters ─────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: 16,
          flexWrap: "wrap",
          alignItems: "flex-end",
        }}
      >
        <div style={{ flex: 1, minWidth: 140 }}>
          <label
            style={{
              display: "block",
              fontSize: 11,
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              marginBottom: 4,
            }}
          >
            User
          </label>
          <select
            value={filter.username}
            onChange={(e) => onFilterChange({ ...filter, username: e.target.value })}
            aria-label="Filter by user"
            style={{
              width: "100%",
              padding: "6px 10px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-bg)",
              color: "var(--color-text)",
              fontSize: 12,
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="">All users</option>
            {usernames.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1, minWidth: 140 }}>
          <label
            style={{
              display: "block",
              fontSize: 11,
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              marginBottom: 4,
            }}
          >
            Action
          </label>
          <select
            value={filter.action}
            onChange={(e) => onFilterChange({ ...filter, action: e.target.value })}
            aria-label="Filter by action"
            style={{
              width: "100%",
              padding: "6px 10px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-bg)",
              color: "var(--color-text)",
              fontSize: 12,
              outline: "none",
              cursor: "pointer",
            }}
          >
            {ACTION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1, minWidth: 120 }}>
          <label
            style={{
              display: "block",
              fontSize: 11,
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              marginBottom: 4,
            }}
          >
            Date range
          </label>
          <select
            value={filter.dateRange}
            onChange={(e) => onFilterChange({ ...filter, dateRange: Number(e.target.value) })}
            aria-label="Filter by date range"
            style={{
              width: "100%",
              padding: "6px 10px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-bg)",
              color: "var(--color-text)",
              fontSize: 12,
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value={0}>All time</option>
            <option value={1}>Last 24 hours</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
          </select>
        </div>

        <button onClick={onRefresh} className="doc-btn" style={{ padding: "6px 14px", fontSize: 12 }}>
          ↻ Refresh
        </button>
      </div>

      <div
        style={{
          fontSize: 12,
          color: "var(--color-text-secondary)",
          marginBottom: 12,
        }}
      >
        Showing {filtered.length} of {entries.length} entries
      </div>

      {filtered.length === 0 ? (
        <div
          style={{
            padding: 24,
            textAlign: "center",
            color: "var(--color-text-secondary)",
            fontSize: 13,
          }}
        >
          {entries.length === 0
            ? "No audit entries yet. Activity will appear here as users interact with the system."
            : "No entries match the current filters."}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {filtered.map((entry) => (
            <div
              key={entry.id}
              style={{
                padding: "10px 14px",
                borderRadius: "var(--radius)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface)",
                fontSize: 13,
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span style={{ fontSize: 18 }}>{actionIcons[entry.action] || "❓"}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div>
                  <strong>{entry.username}</strong>
                  <span style={{ color: "var(--color-text-secondary)" }}>
                    {" "}· {entry.action}{" "}
                    {entry.resource_type && (
                      <>· {entry.resource_type}/{entry.resource_id.slice(0, 8)}</>
                    )}
                  </span>
                </div>
                {entry.details && (
                  <div style={{ color: "var(--color-text-secondary)", fontSize: 12, marginTop: 2 }}>
                    {entry.details}
                  </div>
                )}
              </div>
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)", textAlign: "right", flexShrink: 0 }}>
                <div>{formatTimestamp(entry.timestamp)}</div>
                <div style={{ fontSize: 10 }}>{entry.office}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export type { FilterState };
export { ACTION_OPTIONS };
export default UserAuditViewer;
