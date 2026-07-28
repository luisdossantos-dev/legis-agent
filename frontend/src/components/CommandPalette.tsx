import { useState, useEffect, useRef, useMemo } from "react";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (view: string) => void;
  onOpenSettings: () => void;
  onRefresh: () => void;
}

function CommandPalette({ isOpen, onClose, onNavigate, onOpenSettings, onRefresh }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const toggleTheme = () => {
    const current = localStorage.getItem("legis-theme") || "dark";
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem("legis-theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  const commands = useMemo(() => [
    { id: "upload", label: "Upload Document", icon: "📄", action: () => { onNavigate("upload"); onClose(); } },
    { id: "email", label: "Draft Email", icon: "📧", action: () => { onNavigate("email"); onClose(); } },
    { id: "classify", label: "Classify Email", icon: "📬", action: () => { onNavigate("classify"); onClose(); } },
    { id: "action", label: "Detect Actions", icon: "⚡", action: () => { onNavigate("action"); onClose(); } },
    { id: "review", label: "Review Clauses", icon: "🔍", action: () => { onNavigate("review"); onClose(); } },
    { id: "dashboard", label: "Dashboard", icon: "📊", action: () => { onNavigate("dashboard"); onClose(); } },
    { id: "users", label: "Manage Users", icon: "🔐", action: () => { onNavigate("users"); onClose(); } },
    { id: "settings", label: "Open Settings", icon: "⚙️", shortcut: "Ctrl+,", action: () => { onOpenSettings(); onClose(); } },
    { id: "theme", label: "Toggle Theme", icon: "🌓", action: () => { toggleTheme(); onClose(); } },
    { id: "refresh", label: "Refresh Documents", icon: "↻", action: () => { onRefresh(); onClose(); } },
  ], [onNavigate, onClose, onOpenSettings, onRefresh]);

  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter(c => c.label.toLowerCase().includes(q) || c.id.includes(q));
  }, [query, commands]);

  // Reset state when opened
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current || filtered.length === 0) return;
    const items = listRef.current.querySelectorAll(".command-palette-item");
    if (items[selectedIndex]) {
      items[selectedIndex].scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex, filtered.length]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex(i => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      e.preventDefault();
      filtered[selectedIndex].action();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="command-palette-overlay" onClick={onClose} onKeyDown={handleKeyDown}>
      <div
        className="command-palette"
        role="dialog"
        aria-label="Command palette"
        onClick={e => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          className="command-palette-input"
          type="text"
          placeholder="Type a command..."
          value={query}
          onChange={e => { setQuery(e.target.value); setSelectedIndex(0); }}
          onKeyDown={handleKeyDown}
          aria-label="Search commands"
        />
        <div className="command-palette-list" ref={listRef} role="listbox">
          {filtered.map((cmd, i) => (
            <button
              key={cmd.id}
              className={`command-palette-item${i === selectedIndex ? " selected" : ""}`}
              onClick={() => cmd.action()}
              onMouseEnter={() => setSelectedIndex(i)}
              role="option"
              aria-selected={i === selectedIndex}
            >
              <span className="command-palette-item-icon">{cmd.icon}</span>
              <span className="command-palette-item-label">{cmd.label}</span>
              {cmd.shortcut && (
                <span className="command-palette-item-shortcut">{cmd.shortcut}</span>
              )}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="command-palette-empty">No commands found</div>
          )}
        </div>
        <div className="command-palette-footer">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
