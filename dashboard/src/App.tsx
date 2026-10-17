import React, { useState, useEffect, useCallback } from "react";
import { Incident, HealthState, ZonesConfig, StatsData } from "./types";
import { HealthBar } from "./components/HealthBar";
import { IncidentFeed } from "./components/IncidentFeed";
import { VideoPlayerWithZones } from "./components/VideoPlayerWithZones";
import { TodayByZoneAndHourly } from "./components/TodayByZoneAndHourly";
import { ZoneEditor } from "./components/ZoneEditor";
import { ReportsView } from "./components/ReportsView";
import { SystemView } from "./components/SystemView";
import { IncidentDetailModal } from "./components/IncidentDetailModal";

const DEFAULT_HEALTH: HealthState = {
  status: "ok",
  uptime_s: 1420,
  camera: "up",
  mqtt: "up",
  engine_precision: "INT8",
  fps: 31.4,
  latency_ms: 31.8,
  gpu_util: 68,
  gpu_power_w: 12.4,
};

const DEFAULT_ZONES_CONFIG: ZonesConfig = {
  frame: { width: 1920, height: 1080 },
  zones: [
    {
      id: "walkway",
      type: "safe",
      required_ppe: [],
      polygon: [
        [0, 800],
        [1920, 800],
        [1920, 1080],
        [0, 1080],
      ],
    },
    {
      id: "press-area",
      type: "restricted",
      required_ppe: ["helmet", "vest"],
      polygon: [
        [100, 200],
        [900, 200],
        [900, 750],
        [100, 750],
      ],
    },
    {
      id: "crane-drop",
      type: "danger",
      required_ppe: ["helmet", "vest"],
      polygon: [
        [1100, 150],
        [1850, 150],
        [1850, 750],
        [1100, 750],
      ],
    },
  ],
};

const DEFAULT_STATS: StatsData = {
  window: "24h",
  total_incidents: 4,
  by_type: {
    NO_HELMET: 2,
    ZONE_INTRUSION: 1,
    DANGER_DWELL: 1,
  },
  by_zone: {
    "press-area": 2,
    "crane-drop": 2,
  },
  by_severity: {
    HIGH: 3,
    MEDIUM: 1,
  },
  by_hour: [
    { hour: "08:00", count: 0 },
    { hour: "09:00", count: 1 },
    { hour: "10:00", count: 2 },
    { hour: "11:00", count: 0 },
    { hour: "12:00", count: 0 },
    { hour: "13:00", count: 1 },
    { hour: "14:00", count: 0 },
    { hour: "15:00", count: 0 },
  ],
  compliance_percentage: 94.2,
};

export const App: React.FC = () => {
  const [activeScreen, setActiveScreen] = useState<string>("live");
  const [presentMode, setPresentMode] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthState>(DEFAULT_HEALTH);
  const [zonesConfig, setZonesConfig] = useState<ZonesConfig>(DEFAULT_ZONES_CONFIG);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [activeZoneViolations, setActiveZoneViolations] = useState<string[]>([]);
  const [stats, setStats] = useState<StatsData>(DEFAULT_STATS);

  // Fetch initial data from REST API
  const refreshData = useCallback(async () => {
    try {
      const [resHealth, resZones, resIncidents, resStats] = await Promise.all([
        fetch("/api/health").catch(() => null),
        fetch("/api/zones").catch(() => null),
        fetch("/api/incidents?limit=50").catch(() => null),
        fetch("/api/stats").catch(() => null),
      ]);

      if (resHealth?.ok) {
        const data = await resHealth.json();
        setHealth((prev) => ({ ...prev, ...data }));
      }
      if (resZones?.ok) {
        const data = await resZones.json();
        if (data.zones && data.zones.length > 0) {
          setZonesConfig(data);
        }
      }
      if (resIncidents?.ok) {
        const data = await resIncidents.json();
        if (Array.isArray(data.items)) {
          setIncidents(data.items);
        }
      }
      if (resStats?.ok) {
        const data = await resStats.json();
        setStats(data);
      }
    } catch {
      // Fallback to default state when offline
    }
  }, []);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // WebSocket Live Connection
  useEffect(() => {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = window.location.port === "5173" ? "127.0.0.1:8000" : window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/ws/live`;

    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "incident" && msg.data) {
            const inc: Incident = msg.data;
            setIncidents((prev) => [inc, ...prev.filter((i) => i.incident_id !== inc.incident_id)]);

            // Trigger active zone outline color change
            if (inc.zone) {
              setActiveZoneViolations((prev) => Array.from(new Set([...prev, inc.zone!])));
              setTimeout(() => {
                setActiveZoneViolations((prev) => prev.filter((z) => z !== inc.zone));
              }, 5000);
            }
          } else if (msg.type === "health" && msg.data) {
            setHealth((prev) => ({ ...prev, ...msg.data }));
          }
        } catch {
          // ignore invalid json
        }
      };

      ws.onclose = () => {
        reconnectTimeout = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  // Save Zone Configuration
  const handleSaveZoneConfig = async (newConfig: ZonesConfig): Promise<boolean> => {
    try {
      const res = await fetch("/api/zones", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newConfig),
      });
      if (res.ok) {
        setZonesConfig(newConfig);
        return true;
      }
    } catch {
      // offline fallback
      setZonesConfig(newConfig);
      return true;
    }
    return false;
  };

  // Acknowledge Incident
  const handleAcknowledge = async (incidentId: string, comment?: string): Promise<boolean> => {
    try {
      await fetch(`/api/incidents/${incidentId}/ack`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: comment || undefined }),
      });
    } catch {
      // offline fallback
    }

    setIncidents((prev) =>
      prev.map((i) =>
        i.incident_id === incidentId
          ? {
              ...i,
              acknowledged: true,
              ack_meta: {
                acked_at: new Date().toISOString(),
                user: "Safety Officer",
                comment,
              },
            }
          : i
      )
    );
    if (selectedIncident?.incident_id === incidentId) {
      setSelectedIncident((prev) =>
        prev
          ? {
              ...prev,
              acknowledged: true,
              ack_meta: {
                acked_at: new Date().toISOString(),
                user: "Safety Officer",
                comment,
              },
            }
          : null
      );
    }
    return true;
  };

  // Add Note to Incident
  const handleAddNote = async (incidentId: string, noteText: string): Promise<boolean> => {
    try {
      await fetch(`/api/incidents/${incidentId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: noteText }),
      });
    } catch {
      // offline fallback
    }

    const newNoteObj = {
      note: noteText,
      author: "Safety Officer",
      created_at: new Date().toISOString(),
    };

    setIncidents((prev) =>
      prev.map((i) =>
        i.incident_id === incidentId
          ? {
              ...i,
              notes: [...(i.notes || []), newNoteObj],
            }
          : i
      )
    );
    if (selectedIncident?.incident_id === incidentId) {
      setSelectedIncident((prev) =>
        prev
          ? {
              ...prev,
              notes: [...(prev.notes || []), newNoteObj],
            }
          : null
      );
    }
    return true;
  };

  // Export CSV Action
  const handleExportCsv = () => {
    window.open("/api/incidents/export.csv", "_blank");
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top Universal Health Bar & Navigation */}
      <HealthBar
        health={health}
        activeScreen={activeScreen}
        onSelectScreen={setActiveScreen}
        presentMode={presentMode}
        onTogglePresent={() => setPresentMode(!presentMode)}
      />

      {/* Main Container */}
      <main
        style={{
          flex: 1,
          padding: presentMode ? "16px 24px" : "24px 32px",
          maxWidth: "1600px",
          margin: "0 auto",
          width: "100%",
        }}
      >
        {activeScreen === "live" && (
          <div>
            {/* Live View Grid: Left (Video) & Right (Incident Feed) */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: presentMode ? "2.2fr 1fr" : "1.8fr 1fr",
                gap: "24px",
                alignItems: "start",
              }}
            >
              {/* Left Column: Live annotated video */}
              <div>
                <VideoPlayerWithZones
                  zones={zonesConfig.zones}
                  activeZoneViolations={activeZoneViolations}
                  frameWidth={zonesConfig.frame.width}
                  frameHeight={zonesConfig.frame.height}
                  fps={Math.round(health.fps)}
                />
              </div>

              {/* Right Column: Live Incident Feed */}
              <div style={{ height: "100%" }}>
                <IncidentFeed
                  incidents={incidents}
                  selectedIncidentId={selectedIncident?.incident_id || null}
                  onSelectIncident={(inc) => setSelectedIncident(inc)}
                />
              </div>
            </div>

            {/* Bottom Panels: Today by zone & Violations per hour (Hidden in Present Mode for Focus) */}
            {!presentMode && <TodayByZoneAndHourly stats={stats} />}
          </div>
        )}

        {activeScreen === "zones" && (
          <ZoneEditor
            initialConfig={zonesConfig}
            onSaveConfig={handleSaveZoneConfig}
          />
        )}

        {activeScreen === "reports" && (
          <ReportsView
            stats={stats}
            onExportCsv={handleExportCsv}
          />
        )}

        {activeScreen === "system" && (
          <SystemView health={health} />
        )}
      </main>

      {/* Incident Detail Modal */}
      {selectedIncident && (
        <IncidentDetailModal
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
          onAcknowledge={handleAcknowledge}
          onAddNote={handleAddNote}
        />
      )}
    </div>
  );
};
export default App;
