import React, { useState, useEffect, useRef } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  Info,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Incident } from "../types";
import { Switch, SeverityBadge, ZoneBadge } from "../design/primitives";
import { useAppStore } from "../state/useAppStore";

interface IncidentFeedProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelectIncident: (inc: Incident) => void;
  onAcknowledge?: (id: string) => void;
}

export const formatIncidentName = (type: string): string => {
  switch (type) {
    case "NO_HELMET":
      return "No helmet";
    case "NO_VEST":
      return "No vest";
    case "ZONE_INTRUSION":
      return "Zone entry";
    case "DANGER_DWELL":
      return "Danger-zone dwell";
    default:
      return type.replace(/_/g, " ").toLowerCase();
  }
};

export const getSeverityBadge = (severity: string) => {
  switch (severity) {
    case "HIGH":
      return {
        label: "HIGH",
        icon: <AlertOctagon size={14} />,
        color: "var(--danger-strong)",
        bg: "var(--danger-subtle)",
      };
    case "MEDIUM":
      return {
        label: "MEDIUM",
        icon: <AlertTriangle size={14} />,
        color: "var(--warn-strong)",
        bg: "var(--warn-subtle)",
      };
    default:
      return {
        label: "LOW",
        icon: <Info size={14} />,
        color: "var(--info-strong)",
        bg: "var(--info-subtle)",
      };
  }
};

function formatRelativeTime(isoString: string): string {
  try {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return `${Math.max(1, diffSec)}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin} min ago`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    const diffDay = Math.floor(diffHour / 24);
    return `${diffDay}d ago`;
  } catch {
    return isoString;
  }
}

function formatAbsoluteTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return `${d.toLocaleString()} (${tz})`;
  } catch {
    return isoString;
  }
}

export const IncidentFeed: React.FC<IncidentFeedProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  onAcknowledge,
}) => {
  const { soundEnabled, setSoundEnabled } = useAppStore();
  const [unackOnly, setUnackOnly] = useState<boolean>(false);
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [focusedIndex, setFocusedIndex] = useState<number>(0);
  const feedListRef = useRef<HTMLDivElement>(null);

  // Filtered incidents
  const filtered = incidents.filter((inc) => {
    if (unackOnly && inc.status === "acknowledged") return false;
    if (severityFilter !== "ALL" && inc.severity !== severityFilter) return false;
    return true;
  });

  const openCount = incidents.filter((i) => i.status === "open").length;
  const ackedCount = incidents.filter((i) => i.status === "acknowledged").length;

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)) {
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedIndex((prev) => Math.min(prev + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && filtered[focusedIndex]) {
        e.preventDefault();
        onSelectIncident(filtered[focusedIndex]);
      } else if (e.key.toLowerCase() === "a" && filtered[focusedIndex] && onAcknowledge) {
        e.preventDefault();
        onAcknowledge(filtered[focusedIndex].incident_id);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filtered, focusedIndex, onSelectIncident, onAcknowledge]);

  return (
    <aside
      aria-label="Incidents"
      style={{
        backgroundColor: "var(--surface)",
        borderRadius: "6px",
        border: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header Line */}
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
          <h2 style={{ fontSize: "14px", fontWeight: 600, color: "var(--text)", margin: 0 }}>
            Incidents
          </h2>
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            {openCount} open, {ackedCount} acknowledged
          </span>
        </div>

        <button
          onClick={() => setSoundEnabled(!soundEnabled)}
          title={soundEnabled ? "Alert sound on — click to mute" : "Alert sound off — click to enable"}
          aria-label={soundEnabled ? "Alert sound on" : "Alert sound off"}
          style={{
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            color: soundEnabled ? "var(--text)" : "var(--text-muted)",
            padding: "3px 8px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "5px",
            fontSize: "11px",
          }}
        >
          {soundEnabled ? <Volume2 size={13} /> : <VolumeX size={13} />}
          <span>{soundEnabled ? "Sound on" : "Alert sound off"}</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div
        style={{
          padding: "8px 14px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid var(--border)",
          backgroundColor: "var(--surface)",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", gap: "4px" }}>
          {["ALL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              style={{
                padding: "2px 6px",
                borderRadius: "3px",
                border: "1px solid var(--border)",
                backgroundColor: severityFilter === sev ? "var(--text)" : "transparent",
                color: severityFilter === sev ? "var(--surface)" : "var(--text-muted)",
                fontSize: "11px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              {sev === "ALL" ? "All" : sev}
            </button>
          ))}
        </div>

        <Switch
          id="unack-switch"
          checked={unackOnly}
          onCheckedChange={setUnackOnly}
          label="Unacknowledged only"
        />
      </div>

      {/* Table Column Headers */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "68px 1fr 85px 50px 75px",
          gap: "6px",
          padding: "6px 14px",
          fontSize: "11px",
          fontWeight: 600,
          color: "var(--text-muted)",
          borderBottom: "1px solid var(--border)",
          backgroundColor: "var(--surface)",
        }}
      >
        <span>Severity</span>
        <span>Type</span>
        <span>Zone</span>
        <span style={{ textAlign: "right" }}>Duration</span>
        <span style={{ textAlign: "right" }}>Time</span>
      </div>

      {/* Incident List Rows */}
      <div
        ref={feedListRef}
        role="list"
        aria-live="polite"
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {filtered.length === 0 ? (
          <div
            style={{
              padding: "32px 16px",
              textAlign: "center",
              color: "var(--text-muted)",
              fontSize: "12px",
            }}
          >
            No incidents in the last 24 hours.
          </div>
        ) : (
          filtered.map((inc, idx) => {
            const isSelected = selectedIncidentId === inc.incident_id || focusedIndex === idx;
            const isAcked = inc.status === "acknowledged";

            return (
              <div
                key={inc.incident_id}
                role="listitem"
                tabIndex={0}
                onClick={() => onSelectIncident(inc)}
                onFocus={() => setFocusedIndex(idx)}
                style={{
                  display: "grid",
                  gridTemplateColumns: "68px 1fr 85px 50px 75px",
                  gap: "6px",
                  padding: "8px 14px",
                  alignItems: "center",
                  borderBottom: "1px solid var(--border)",
                  backgroundColor: isSelected ? "var(--surface-raised, rgba(255,255,255,0.05))" : "transparent",
                  cursor: "pointer",
                  fontSize: "12px",
                  opacity: isAcked ? 0.6 : 1,
                  transition: "background 0.15s ease",
                  userSelect: "none",
                }}
              >
                <div>
                  <SeverityBadge severity={inc.severity} />
                </div>
                <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  <span style={{ color: "var(--text)", fontWeight: 500 }}>
                    {formatIncidentName(inc.type)}
                  </span>
                </div>
                <div>
                  {inc.zone ? <ZoneBadge type={inc.zone} name={inc.zone} /> : <span style={{ color: "var(--text-muted)" }}>—</span>}
                </div>
                <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-muted)" }}>
                  {inc.duration_s.toFixed(1)}s
                </div>
                <div
                  style={{ textAlign: "right", fontSize: "11px", color: "var(--text-muted)" }}
                  title={formatAbsoluteTime(inc.timestamp)}
                >
                  {formatRelativeTime(inc.timestamp)}
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
