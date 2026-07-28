import { useState } from "react";
import { showToast } from "./Toast";

const ROLE_OPTIONS = [
  { value: "admin", label: "Admin — full access" },
  { value: "notaire", label: "Notaire — read, write, finalize, delete" },
  { value: "assistant", label: "Assistant — read, write, draft" },
  { value: "stagiaire", label: "Stagiaire — read only" },
];

const inputStyle: React.CSSProperties = {
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

interface UserCreateFormProps {
  onCreated: () => void;
  onCancel: () => void;
}

function UserCreateForm({ onCreated, onCancel }: UserCreateFormProps) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("stagiaire");
  const [office, setOffice] = useState("main");
  const [displayName, setDisplayName] = useState("");

  const handleSubmit = async () => {
    if (!username || !email || !password) {
      showToast("warning", "Missing fields", "Username, email and password are required.");
      return;
    }

    try {
      const res = await fetch("http://localhost:8000/api/v1/rbac/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password, role, office, display_name: displayName }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create user");
      }

      showToast("info", "User created", `User "${username}" created successfully.`);
      onCreated();
    } catch (err) {
      console.error("User creation failed:", err);
      showToast("error", "Creation failed", "Unknown error");
    }
  };

  return (
    <div
      style={{
        padding: 20,
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--color-border)",
        backgroundColor: "var(--color-surface)",
        marginBottom: 20,
      }}
    >
      <h3 style={{ fontSize: 16, marginBottom: 16 }}>Create New User</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Username *</label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} style={inputStyle} placeholder="jdoe" />
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Email *</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} style={inputStyle} placeholder="john@notary.fr" />
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Password *</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={inputStyle} placeholder="min 8 chars" />
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value)} style={inputStyle}>
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Office</label>
          <input type="text" value={office} onChange={(e) => setOffice(e.target.value)} style={inputStyle} placeholder="main" />
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Display Name</label>
          <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} style={inputStyle} placeholder="John Doe" />
        </div>
      </div>
      <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button onClick={onCancel} className="doc-btn">Cancel</button>
        <button
          onClick={handleSubmit}
          className="doc-btn"
          style={{ backgroundColor: "var(--color-primary)", color: "white", border: "none" }}
        >
          Create User
        </button>
      </div>
    </div>
  );
}

export default UserCreateForm;
