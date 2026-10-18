import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Video,
  AlertTriangle,
  Map,
  BarChart3,
  Cpu,
  Palette,
  Maximize2,
  Moon,
  Sun,
  Search,
  X,
} from "lucide-react";
import { useAppStore } from "../state/useAppStore";
import { Kbd } from "../design/primitives";

export const CommandPalette: React.FC = () => {
  const { commandPaletteOpen, setCommandPaletteOpen, theme, toggleTheme, togglePresentMode } =
    useAppStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
      if (e.key === "Escape" && commandPaletteOpen) {
        setCommandPaletteOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [commandPaletteOpen, setCommandPaletteOpen]);

  if (!commandPaletteOpen) return null;

  const actions = [
    { id: "nav-live", title: "Jump to Live View", icon: <Video size={16} />, shortcut: "G L", action: () => navigate("/") },
    { id: "nav-incidents", title: "Jump to Incidents Table", icon: <AlertTriangle size={16} />, shortcut: "G I", action: () => navigate("/incidents") },
    { id: "nav-zones", title: "Jump to Zone Editor", icon: <Map size={16} />, shortcut: "G Z", action: () => navigate("/zones") },
    { id: "nav-reports", title: "Jump to Reports & Trends", icon: <BarChart3 size={16} />, shortcut: "G R", action: () => navigate("/reports") },
    { id: "nav-system", title: "Jump to System & Edge Telemetry", icon: <Cpu size={16} />, shortcut: "G S", action: () => navigate("/system") },
    { id: "nav-design", title: "Jump to Design Tokens Gallery", icon: <Palette size={16} />, shortcut: "G D", action: () => navigate("/design") },
    { id: "act-present", title: "Toggle Present Mode", icon: <Maximize2 size={16} />, shortcut: "P", action: () => togglePresentMode() },
    { id: "act-theme", title: `Switch to ${theme === "light" ? "Dark (Control Room)" : "Light"} Theme`, icon: theme === "light" ? <Moon size={16} /> : <Sun size={16} />, action: () => toggleTheme() },
    { id: "sc-calm", title: "Dev Scenario: Calm Shift", icon: <Video size={16} />, action: () => { window.location.search = "?scenario=calm"; } },
    { id: "sc-busy", title: "Dev Scenario: Busy Shift", icon: <AlertTriangle size={16} />, action: () => { window.location.search = "?scenario=busy_shift"; } },
    { id: "sc-cam-lost", title: "Dev Scenario: Camera Lost", icon: <Video size={16} />, action: () => { window.location.search = "?scenario=camera_lost"; } },
    { id: "sc-mqtt-down", title: "Dev Scenario: MQTT Down", icon: <Cpu size={16} />, action: () => { window.location.search = "?scenario=mqtt_down"; } },
    { id: "sc-many", title: "Dev Scenario: Many Incidents (300+)", icon: <AlertTriangle size={16} />, action: () => { window.location.search = "?scenario=many_incidents"; } },
  ];

  const filtered = actions.filter((a) =>
    a.title.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(16, 22, 27, 0.65)",
        backdropFilter: "blur(4px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "12vh",
      }}
      onClick={() => setCommandPaletteOpen(false)}
    >
      <div
        style={{
          width: "90vw",
          maxWidth: "540px",
          backgroundColor: "var(--surface-raised)",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-dialog)",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "12px 16px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <Search size={18} style={{ color: "var(--text-muted)" }} />
          <input
            autoFocus
            type="text"
            aria-label="Type a command or jump to screen..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text)",
              fontSize: "15px",
              fontFamily: "var(--font-body)",
            }}
          />
          <button
            onClick={() => setCommandPaletteOpen(false)}
            style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Action list */}
        <div style={{ maxHeight: "340px", overflowY: "auto", padding: "6px" }}>
          {filtered.length === 0 ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)", fontSize: "14px" }}>
              No commands found.
            </div>
          ) : (
            filtered.map((item) => (
              <div
                key={item.id}
                onClick={() => {
                  item.action();
                  setCommandPaletteOpen(false);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  cursor: "pointer",
                  color: "var(--text)",
                  transition: "background var(--motion-fast)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--surface)")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ color: "var(--info)" }}>{item.icon}</span>
                  <span style={{ fontSize: "14px" }}>{item.title}</span>
                </div>
                {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
