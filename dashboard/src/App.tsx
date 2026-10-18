import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { HealthState, ZonesConfig, StatsData } from "./types";
import { Incident } from "./api/schema";
import { api } from "./api/client";
import { wsManager, WebSocketConnectionState } from "./api/websocket";
import { useAppStore } from "./state/useAppStore";
import { HealthBar } from "./components/HealthBar";
import { NavRail } from "./components/NavRail";
import { CommandPalette } from "./components/CommandPalette";
import { IncidentFeed } from "./components/IncidentFeed";
import { VideoPlayerWithZones } from "./components/VideoPlayerWithZones";
import { TodayByZoneAndHourly } from "./components/TodayByZoneAndHourly";
import { IncidentsTable } from "./components/IncidentsTable";
import { ZoneEditor } from "./components/ZoneEditor";
import { ReportsView } from "./components/ReportsView";
import { SystemView } from "./components/SystemView";
import { IncidentDetailDrawer } from "./components/IncidentDetailDrawer";
import { DesignGallery } from "./design/DesignGallery";

const INITIAL_HEALTH: HealthState = {
  status: "degraded",
  mode: "LIVE",
  uptime_s: 0,
  camera: "down",
  mqtt: "down",
};

const DEFAULT_ZONES_CONFIG: ZonesConfig = {
  frame: { width: 1920, height: 1080 },
  zones: [
    {
      id: "walkway",
      type: "safe",
      required_ppe: ["helmet"],
      polygon: [
        [150, 600],
        [950, 600],
        [950, 1020],
        [150, 1020],
      ],
    },
    {
      id: "press-area",
      type: "restricted",
      required_ppe: ["helmet", "vest"],
      polygon: [
        [1000, 450],
        [1550, 450],
        [1550, 950],
        [1000, 950],
      ],
    },
    {
      id: "crane-drop",
      type: "danger",
      required_ppe: ["helmet", "vest"],
      polygon: [
        [1400, 150],
        [1880, 150],
        [1880, 650],
        [1400, 650],
      ],
    },
  ],
};

const EMPTY_STATS: StatsData = {
  window: "24h",
  total_incidents: 0,
  by_type: {},
  by_zone: {},
  by_severity: {},
  by_hour: [],
  compliance_percentage: 100,
};

export const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    theme,
    presentMode,
    togglePresentMode,
    selectedIncidentId,
    setSelectedIncidentId,
    incrementUnreadCount,
  } = useAppStore();

  const [health, setHealth] = useState<HealthState>(INITIAL_HEALTH);
  const [zonesConfig, setZonesConfig] = useState<ZonesConfig>(DEFAULT_ZONES_CONFIG);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [activeZoneViolations, setActiveZoneViolations] = useState<string[]>([]);
  const [stats, setStats] = useState<StatsData>(EMPTY_STATS);
  const [connectionState, setConnectionState] = useState<WebSocketConnectionState>("disconnected");
  const [backendDown, setBackendDown] = useState<boolean>(false);
  const [retryCountdown, setRetryCountdown] = useState<number>(5);

  // Sync theme attribute
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Initial and recurring data loading
  const refreshData = useCallback(async () => {
    try {
      const h = await api.getHealth();
      setHealth(h as any);
      setBackendDown(false);

      const [z, incs, s] = await Promise.all([
        api.getZones().catch(() => DEFAULT_ZONES_CONFIG),
        api.listIncidents({ limit: 100 }).catch(() => ({ items: [] })),
        api.getStats().catch(() => EMPTY_STATS),
      ]);
      if (z && z.zones && z.zones.length > 0) setZonesConfig(z);
      if (incs && incs.items) setIncidents(incs.items);
      if (s) setStats(s as any);
    } catch {
      setBackendDown(true);
      setHealth((prev) => ({
        ...prev,
        status: "down",
        fps: null,
        latency_ms: null,
        engine_precision: null,
        gpu_util: null,
        gpu_power_w: null,
      }));
    }
  }, []);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // Auto-retry when backend is down
  useEffect(() => {
    if (!backendDown) {
      setRetryCountdown(5);
      return;
    }

    const timer = setInterval(() => {
      setRetryCountdown((prev) => {
        if (prev <= 1) {
          refreshData();
          return 5;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [backendDown, refreshData]);

  // WebSocket Live listener & Reconnect Tracking
  useEffect(() => {
    const unsubConn = wsManager.onConnectionChange(setConnectionState);
    const unsubMsg = wsManager.subscribe((msg) => {
      if (msg.type === "incident" && msg.data) {
        const newInc = msg.data as Incident;
        setIncidents((prev) => [newInc, ...prev.filter((i) => i.incident_id !== newInc.incident_id)]);
        incrementUnreadCount();

        if (newInc.zone) {
          setActiveZoneViolations((prev) => Array.from(new Set([...prev, newInc.zone!])));
          setTimeout(() => {
            setActiveZoneViolations((prev) => prev.filter((z) => z !== newInc.zone));
          }, 4000);
        }
      } else if (msg.type === "health" && msg.data) {
        setHealth((prev) => ({ ...prev, ...msg.data }));
      }
    });

    return () => {
      unsubConn();
      unsubMsg();
    };
  }, [incrementUnreadCount]);

  // Sequential keyboard shortcuts: G L, G I, G Z, G R, G S, G D and P
  useEffect(() => {
    let pendingG = false;
    let gTimeout: any = null;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)) {
        return;
      }

      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        togglePresentMode();
        return;
      }

      if (e.key.toLowerCase() === "g") {
        pendingG = true;
        clearTimeout(gTimeout);
        gTimeout = setTimeout(() => {
          pendingG = false;
        }, 1000);
        return;
      }

      if (pendingG) {
        pendingG = false;
        clearTimeout(gTimeout);
        const key = e.key.toLowerCase();
        if (key === "l") navigate("/");
        else if (key === "i") navigate("/incidents");
        else if (key === "z") navigate("/zones");
        else if (key === "r") navigate("/reports");
        else if (key === "s") navigate("/system");
        else if (key === "d" && import.meta.env.DEV) navigate("/design");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      clearTimeout(gTimeout);
    };
  }, [navigate, togglePresentMode]);

  // Handle URL route /incidents/:id to open detail drawer automatically
  useEffect(() => {
    const match = location.pathname.match(/^\/incidents\/([^/]+)$/);
    if (match && match[1]) {
      setSelectedIncidentId(match[1]);
    }
  }, [location.pathname, setSelectedIncidentId]);

  // Save Zone Configuration
  const handleSaveZoneConfig = async (newConfig: ZonesConfig): Promise<boolean> => {
    try {
      const updated = await api.updateZones(newConfig);
      setZonesConfig(updated);
      return true;
    } catch {
      setZonesConfig(newConfig);
      return true;
    }
  };

  // Acknowledge Incident
  const handleAcknowledge = async (incidentId: string, comment?: string) => {
    await api.ackIncident(incidentId, "safety-officer", comment);
    setIncidents((prev) =>
      prev.map((i) =>
        i.incident_id === incidentId
          ? {
              ...i,
              status: "acknowledged",
              acked_at: new Date().toISOString(),
              acked_by: "safety-officer",
              notes: comment
                ? [...i.notes, { author: "safety-officer", note: comment, created_at: new Date().toISOString() }]
                : i.notes,
            }
          : i
      )
    );
  };

  // Bulk Acknowledge
  const handleBulkAck = async (ids: string[]) => {
    await api.bulkAck(ids);
    setIncidents((prev) =>
      prev.map((i) =>
        ids.includes(i.incident_id)
          ? {
              ...i,
              status: "acknowledged",
              acked_at: new Date().toISOString(),
              acked_by: "safety-officer",
            }
          : i
      )
    );
  };

  // Add Note
  const handleAddNote = async (incidentId: string, noteText: string) => {
    await api.addNote(incidentId, noteText);
    setIncidents((prev) =>
      prev.map((i) =>
        i.incident_id === incidentId
          ? {
              ...i,
              notes: [...i.notes, { author: "safety-officer", note: noteText, created_at: new Date().toISOString() }],
            }
          : i
      )
    );
  };

  // Selected incident object for drawer
  const selectedIncident = useMemo(() => {
    if (!selectedIncidentId) return null;
    return incidents.find((i) => i.incident_id === selectedIncidentId) || null;
  }, [selectedIncidentId, incidents]);

  // Previous and next incident navigation in drawer
  const selectedIndex = incidents.findIndex((i) => i.incident_id === selectedIncidentId);
  const hasPrev = selectedIndex > 0;
  const hasNext = selectedIndex !== -1 && selectedIndex < incidents.length - 1;
  const handlePrev = () => {
    if (hasPrev) setSelectedIncidentId(incidents[selectedIndex - 1].incident_id);
  };
  const handleNext = () => {
    if (hasNext) setSelectedIncidentId(incidents[selectedIndex + 1].incident_id);
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", backgroundColor: "var(--bg)" }}>
      {/* Skip to Content for WCAG 2.2 AA Keyboard Accessibility */}
      <a
        href="#main-content"
        className="skip-link"
        style={{
          position: "absolute",
          left: "-9999px",
          top: "auto",
          width: "1px",
          height: "1px",
          overflow: "hidden",
          zIndex: 99999,
        }}
        onFocus={(e) => {
          e.currentTarget.style.position = "fixed";
          e.currentTarget.style.left = "16px";
          e.currentTarget.style.top = "16px";
          e.currentTarget.style.width = "auto";
          e.currentTarget.style.height = "auto";
          e.currentTarget.style.padding = "8px 16px";
          e.currentTarget.style.backgroundColor = "var(--info)";
          e.currentTarget.style.color = "#FFFFFF";
          e.currentTarget.style.borderRadius = "var(--radius-sm)";
          e.currentTarget.style.fontWeight = "600";
        }}
        onBlur={(e) => {
          e.currentTarget.style.position = "absolute";
          e.currentTarget.style.left = "-9999px";
          e.currentTarget.style.width = "1px";
          e.currentTarget.style.height = "1px";
        }}
      >
        Skip to main content
      </a>

      {/* Top Universal Health Bar */}
      <HealthBar
        health={health}
        presentMode={presentMode}
        onTogglePresent={togglePresentMode}
        connectionState={connectionState}
      />

      {/* Backend Unreachable Banner */}
      {backendDown && (
        <div
          role="alert"
          style={{
            backgroundColor: "rgba(232, 89, 12, 0.12)",
            borderBottom: "1px solid var(--danger)",
            color: "var(--danger)",
            padding: "8px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "12px",
            fontWeight: 500,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <AlertTriangle size={15} />
            <span>
              Backend unreachable at <code>http://localhost:8000</code>. Retrying in {retryCountdown} s. Start with: <code>sentinel run</code>
            </span>
          </div>
          <button
            onClick={() => {
              setRetryCountdown(5);
              refreshData();
            }}
            style={{
              background: "var(--danger)",
              color: "#ffffff",
              border: "none",
              borderRadius: "4px",
              padding: "3px 10px",
              fontSize: "11px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Retry now
          </button>
        </div>
      )}

      {/* Mode Banners */}
      {health.mode === "SIMULATED" && (
        <div
          style={{
            backgroundColor: "rgba(242, 169, 0, 0.14)",
            borderBottom: "1px solid var(--warn)",
            color: "var(--text)",
            padding: "6px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          <AlertTriangle size={14} style={{ color: "var(--warn)" }} />
          <span>Simulated data. Not a live camera.</span>
        </div>
      )}

      {health.mode === "REPLAY" && (
        <div
          style={{
            backgroundColor: "rgba(31, 111, 208, 0.12)",
            borderBottom: "1px solid var(--info)",
            color: "var(--text)",
            padding: "6px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          <span>Replay: {health.replay_file || "recorded_stream.mp4"}</span>
        </div>
      )}

      {/* Global Command Palette */}
      <CommandPalette />

      {/* Main Body with Left Rail and Content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <NavRail />

        <main id="main-content" tabIndex={-1} style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
          <Routes>
            {/* Live View (Default) */}
            <Route
              path="/"
              element={
                <div style={{ padding: presentMode ? "12px" : "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: presentMode ? "2.2fr 1fr" : "1.8fr 1fr",
                      gap: "16px",
                      alignItems: "start",
                    }}
                  >
                    <VideoPlayerWithZones
                      zones={zonesConfig.zones}
                      activeZoneViolations={activeZoneViolations}
                      frameWidth={zonesConfig.frame.width}
                      frameHeight={zonesConfig.frame.height}
                      fps={health.fps != null ? Math.round(health.fps) : null}
                      blurredSource={health.privacy?.blurred_source ?? false}
                    />

                    <div style={{ height: "100%" }}>
                      <IncidentFeed
                        incidents={incidents}
                        selectedIncidentId={selectedIncidentId}
                        onSelectIncident={(inc) => setSelectedIncidentId(inc.incident_id)}
                        onAcknowledge={handleAcknowledge}
                      />
                    </div>
                  </div>

                  {!presentMode && <TodayByZoneAndHourly stats={stats} />}
                </div>
              }
            />

            {/* Incidents Table View */}
            <Route
              path="/incidents"
              element={
                <IncidentsTable
                  incidents={incidents}
                  onSelectIncident={(inc) => setSelectedIncidentId(inc.incident_id)}
                  onBulkAck={handleBulkAck}
                  onRefresh={refreshData}
                />
              }
            />
            <Route
              path="/incidents/:id"
              element={
                <IncidentsTable
                  incidents={incidents}
                  onSelectIncident={(inc) => setSelectedIncidentId(inc.incident_id)}
                  onBulkAck={handleBulkAck}
                  onRefresh={refreshData}
                />
              }
            />

            {/* Zone Editor View */}
            <Route
              path="/zones"
              element={
                <ZoneEditor
                  initialConfig={zonesConfig}
                  onSaveConfig={handleSaveZoneConfig}
                />
              }
            />

            {/* Reports & Compliance Analytics */}
            <Route
              path="/reports"
              element={
                <ReportsView
                  stats={stats}
                  onExportCsv={() => window.open("/api/incidents/export.csv", "_blank")}
                />
              }
            />

            {/* System Telemetry & Edge Intelligence */}
            <Route path="/system" element={<SystemView health={health} />} />

            {/* Design Tokens & Primitives Gallery (Dev Only) */}
            {import.meta.env.DEV && <Route path="/design" element={<DesignGallery />} />}
          </Routes>
        </main>
      </div>

      {/* Incident Detail Drawer */}
      <IncidentDetailDrawer
        incident={selectedIncident}
        onClose={() => {
          setSelectedIncidentId(null);
          if (location.pathname.startsWith("/incidents/")) {
            navigate("/incidents");
          }
        }}
        onAcknowledge={handleAcknowledge}
        onAddNote={handleAddNote}
        onPrev={handlePrev}
        onNext={handleNext}
        hasPrev={hasPrev}
        hasNext={hasNext}
      />
    </div>
  );
};

export default App;
