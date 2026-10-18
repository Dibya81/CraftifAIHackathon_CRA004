import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Video,
  AlertTriangle,
  Map,
  BarChart3,
  Cpu,
  Palette,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useAppStore } from "../state/useAppStore";

export const NavRail: React.FC = () => {
  const location = useLocation();
  const { navCollapsed, toggleNavCollapsed, unreadCount, presentMode } = useAppStore();

  // In Present mode, hide navigation rail
  if (presentMode) return null;

  const baseNavItems = [
    { path: "/", label: "Live", icon: <Video size={17} strokeWidth={1.75} /> },
    { path: "/incidents", label: "Incidents", icon: <AlertTriangle size={17} strokeWidth={1.75} />, badge: unreadCount > 0 ? unreadCount : undefined },
    { path: "/zones", label: "Zones", icon: <Map size={17} strokeWidth={1.75} /> },
    { path: "/reports", label: "Reports", icon: <BarChart3 size={17} strokeWidth={1.75} /> },
    { path: "/system", label: "System", icon: <Cpu size={17} strokeWidth={1.75} /> },
  ];

  const navItems = import.meta.env.DEV
    ? [...baseNavItems, { path: "/design", label: "Design", icon: <Palette size={17} strokeWidth={1.75} /> }]
    : baseNavItems;

  return (
    <nav
      aria-label="Sidebar Navigation"
      style={{
        width: navCollapsed ? "56px" : "180px",
        backgroundColor: "var(--surface)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        transition: "width var(--motion-normal)",
        userSelect: "none",
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", padding: "8px 6px", gap: "2px" }}>
        {navItems.map((item) => {
          const isActive = location.pathname === item.path || (item.path !== "/" && location.pathname.startsWith(item.path));
          return (
            <Link
              key={item.path}
              to={item.path}
              title={item.label}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: navCollapsed ? "center" : "space-between",
                padding: "8px 10px",
                borderRadius: "4px",
                backgroundColor: isActive ? "var(--surface-raised)" : "transparent",
                color: isActive ? "var(--text)" : "var(--text-muted)",
                fontWeight: isActive ? 600 : 500,
                borderLeft: isActive ? "3px solid var(--info)" : "3px solid transparent",
                transition: "all var(--motion-fast)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span aria-hidden="true" style={{ color: isActive ? "var(--info)" : "currentColor", display: "flex" }}>
                  {item.icon}
                </span>
                {!navCollapsed && <span style={{ fontSize: "13px" }}>{item.label}</span>}
              </div>

              {!navCollapsed && item.badge && (
                <span
                  style={{
                    padding: "1px 6px",
                    backgroundColor: "var(--danger)",
                    color: "#FFFFFF",
                    borderRadius: "10px",
                    fontSize: "10px",
                    fontWeight: 700,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      {/* Collapse toggle at bottom */}
      <div style={{ padding: "8px", borderTop: "1px solid var(--border)" }}>
        <button
          onClick={toggleNavCollapsed}
          title={navCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          style={{
            width: "100%",
            padding: "6px",
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            color: "var(--text-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          {navCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>
    </nav>
  );
};
