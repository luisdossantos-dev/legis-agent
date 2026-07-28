import { t } from "../i18n";

interface SidebarNavProps {
  currentView: string;
  onNavigate: (view: string) => void;
}

const NAV_ITEMS = [
  { view: "email", icon: "📧", labelKey: "header.email" },
  { view: "classify", icon: "📬", labelKey: "header.classify" },
  { view: "action", icon: "⚡", labelKey: "header.actions" },
  { view: "review", icon: "🔍", labelKey: "header.review" },
  { view: "dashboard", icon: "📊", labelKey: "header.dashboard" },
  { view: "users", icon: "🔐", labelKey: "header.users" },
];

function SidebarNav({ currentView, onNavigate }: SidebarNavProps) {
  return (
    <nav className="sidebar-nav" aria-label="Main navigation">
      {NAV_ITEMS.map((item) => {
        const isActive = currentView === item.view;
        return (
          <button
            key={item.view}
            className={`sidebar-nav-item${isActive ? " active" : ""}`}
            onClick={() => onNavigate(item.view)}
            aria-current={isActive ? "page" : undefined}
          >
            <span className="sidebar-nav-icon">{item.icon}</span>
            <span className="sidebar-nav-label">{t(item.labelKey)}</span>
          </button>
        );
      })}
    </nav>
  );
}

export default SidebarNav;
