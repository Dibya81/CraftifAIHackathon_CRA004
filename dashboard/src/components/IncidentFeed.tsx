import React from "react";
import { Incident } from "../types";

interface IncidentFeedProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelectIncident: (inc: Incident) => void;
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
        icon: "⚠️",
        color: "var(--hazard-orange)",
        bg: "var(--hazard-orange-light)",
      };
    case "MEDIUM":
      return {
        label: "MEDIUM",
        icon: "⚡",
        color: "var(--caution-amber)",
        bg: "var(--caution-amber-light)",
      };
    default:
      return {
        label: "LOW",
        icon: "ℹ️",
        color: "var(--steel-700)",
        bg: "var(--concrete-100)",
      };
  }
};

export const IncidentFeed: React.FC<IncidentFeedProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
}) => {
  return (
    <aside
      aria-label="Incident feed"
      style={{
        backgroundColor: "var(--concrete-50)",
        borderRadius: "var(--radius-md)",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <h2 style={{ fontSize: "18px", color: "var(--steel-900)" }}>Incidents</h2>
        <span style={{ fontSize: "12px", color: "var(--steel-700)", fontWeight: 600 }}>
          {incidents.length} recorded
        </span>
      </div>

      {/* ARIA Live Region for Screen Readers */}
      <div
        role="list"
        aria-live="polite"
        aria-atomic="false"
        style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}
      >
        {incidents.length === 0 ? (
          <div
            style={{
              padding: "32px 16px",
              textAlign: "center",
              color: "var(--steel-700)",
              fontSize: "14px",
            }}
          >
            No incidents in the last hour. Cameras are healthy.
          </div>
        ) : (
          incidents.map((inc) => {
            const badge = getSeverityBadge(inc.severity);
            const isSelected = selectedIncidentId === inc.incident_id;
            const isAcked = !!inc.acknowledged;

            return (
              <div
                key={inc.incident_id}
                role="listitem"
                tabIndex={0}
                onClick={() => onSelectIncident(inc)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectIncident(inc);
                  }
                }}
                className="animate-slide-in"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 12px",
                  backgroundColor: isSelected ? "var(--signal-blue-light)" : "var(--white)",
                  border: isSelected ? "1px solid var(--signal-blue)" : "1px solid rgba(0,0,0,0.06)",
                  borderLeft: `4px solid ${badge.color}`,
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                  opacity: isAcked ? 0.7 : 1,
                  transition: "background-color 150ms ease",
                }}
              >
                {/* Left Info */}
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ fontSize: "14px" }}>{badge.icon}</span>
                    <span style={{ fontWeight: isAcked ? 500 : 700, fontSize: "14px", color: "var(--steel-900)" }}>
                      {formatIncidentName(inc.type)}
                    </span>
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        padding: "1px 6px",
                        borderRadius: "2px",
                        backgroundColor: badge.bg,
                        color: badge.color,
                        letterSpacing: "0.5px",
                      }}
                    >
                      {badge.label}
                    </span>
                  </div>

                  <div style={{ fontSize: "12px", color: "var(--steel-700)", display: "flex", gap: "8px" }}>
                    <span>{inc.zone || "unassigned"}</span>
                    <span>&bull;</span>
                    <span>{inc.duration_s.toFixed(1)} s</span>
                    {isAcked && <span style={{ color: "var(--clear-green)", fontWeight: 600 }}>&bull; Acknowledged</span>}
                  </div>
                </div>

                {/* Right: Timestamp and optional thumbnail indicator */}
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "12px", color: "var(--steel-700)", fontFamily: "monospace" }}>
                    {inc.timestamp.slice(11, 19)}
                  </span>
                  {inc.evidence_clip && (
                    <span
                      title="Evidence clip available"
                      style={{
                        fontSize: "12px",
                        padding: "2px 5px",
                        backgroundColor: "var(--concrete-100)",
                        borderRadius: "2px",
                      }}
                    >
                      🎥 Clip
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
