import React from "react";
import { StatsData } from "../types";
import { formatIncidentName } from "./IncidentFeed";

interface ReportsViewProps {
  stats: StatsData;
  onExportCsv: () => void;
}

export const ReportsView: React.FC<ReportsViewProps> = ({ stats, onExportCsv }) => {
  const compliance = stats.compliance_percentage;
  const isGood = compliance >= 90;
  const isFair = compliance >= 75 && compliance < 90;

  let complianceColor = "var(--clear-green)";
  let complianceStatus = "Compliant";
  if (!isGood && !isFair) {
    complianceColor = "var(--hazard-orange)";
    complianceStatus = "Critical Attention Required";
  } else if (isFair) {
    complianceColor = "var(--caution-amber)";
    complianceStatus = "Needs Attention";
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Top Banner: Compliance Summary & Export Action */}
      <div
        style={{
          backgroundColor: "var(--white)",
          padding: "24px",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-sm)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
          <div>
            <div style={{ fontSize: "12px", textTransform: "uppercase", color: "var(--steel-700)", fontWeight: 600 }}>
              Overall Site Compliance (Last {stats.window})
            </div>
            <div
              style={{
                fontFamily: "var(--font-heading)",
                fontSize: "48px",
                color: complianceColor,
                lineHeight: 1.1,
                marginTop: "4px",
              }}
            >
              {compliance.toFixed(1)}%
            </div>
          </div>

          <div style={{ borderLeft: "2px solid var(--concrete-100)", paddingLeft: "24px" }}>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--steel-900)" }}>{complianceStatus}</div>
            <div style={{ fontSize: "13px", color: "var(--steel-700)" }}>
              {stats.total_incidents} incident{stats.total_incidents === 1 ? "" : "s"} recorded across all monitored zones
            </div>
          </div>
        </div>

        <button
          onClick={onExportCsv}
          style={{
            backgroundColor: "var(--signal-blue)",
            color: "var(--white)",
            border: "none",
            padding: "10px 20px",
            borderRadius: "var(--radius-sm)",
            fontWeight: 600,
            fontSize: "14px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span>📥</span>
          <span>Export CSV</span>
        </button>
      </div>

      {/* Breakdown Grids */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
        {/* Breakdown by Zone */}
        <div
          style={{
            backgroundColor: "var(--white)",
            padding: "20px",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <h3 style={{ fontSize: "18px", marginBottom: "16px" }}>Incidents by zone</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--concrete-100)", textAlign: "left", color: "var(--steel-700)" }}>
                <th style={{ padding: "8px 0" }}>Zone Name</th>
                <th style={{ padding: "8px 0", textAlign: "right" }}>Count</th>
                <th style={{ padding: "8px 0", textAlign: "right" }}>Share</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(stats.by_zone).length === 0 ? (
                <tr>
                  <td colSpan={3} style={{ padding: "16px 0", textAlign: "center", color: "var(--steel-700)" }}>
                    No zone incidents recorded
                  </td>
                </tr>
              ) : (
                Object.entries(stats.by_zone).map(([zone, count]) => {
                  const share = stats.total_incidents > 0 ? (count / stats.total_incidents) * 100 : 0;
                  return (
                    <tr key={zone} style={{ borderBottom: "1px solid var(--concrete-50)" }}>
                      <td style={{ padding: "10px 0", fontWeight: 600 }}>{zone}</td>
                      <td style={{ padding: "10px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {count}
                      </td>
                      <td style={{ padding: "10px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {share.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Breakdown by Type */}
        <div
          style={{
            backgroundColor: "var(--white)",
            padding: "20px",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <h3 style={{ fontSize: "18px", marginBottom: "16px" }}>Incidents by violation type</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--concrete-100)", textAlign: "left", color: "var(--steel-700)" }}>
                <th style={{ padding: "8px 0" }}>Violation Type</th>
                <th style={{ padding: "8px 0", textAlign: "right" }}>Count</th>
                <th style={{ padding: "8px 0", textAlign: "right" }}>Share</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(stats.by_type).length === 0 ? (
                <tr>
                  <td colSpan={3} style={{ padding: "16px 0", textAlign: "center", color: "var(--steel-700)" }}>
                    No violation types recorded
                  </td>
                </tr>
              ) : (
                Object.entries(stats.by_type).map(([type, count]) => {
                  const share = stats.total_incidents > 0 ? (count / stats.total_incidents) * 100 : 0;
                  return (
                    <tr key={type} style={{ borderBottom: "1px solid var(--concrete-50)" }}>
                      <td style={{ padding: "10px 0", fontWeight: 600 }}>{formatIncidentName(type)}</td>
                      <td style={{ padding: "10px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {count}
                      </td>
                      <td style={{ padding: "10px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {share.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Hourly Trend Chart */}
      <div
        style={{
          backgroundColor: "var(--white)",
          padding: "20px",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <h3 style={{ fontSize: "18px", marginBottom: "16px" }}>Hourly incident distribution</h3>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: "8px",
            height: "140px",
            paddingTop: "20px",
            borderBottom: "1px solid var(--concrete-100)",
          }}
        >
          {stats.by_hour.map((h) => {
            const maxVal = Math.max(1, ...stats.by_hour.map((x) => x.count));
            const barHeight = Math.max(4, (h.count / maxVal) * 100);
            return (
              <div
                key={h.hour}
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "6px",
                  height: "100%",
                  justifyContent: "flex-end",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--steel-700)" }}>{h.count}</div>
                <div
                  style={{
                    width: "100%",
                    maxWidth: "32px",
                    height: `${barHeight}%`,
                    backgroundColor: h.count > 0 ? "var(--hazard-orange)" : "var(--concrete-100)",
                    borderRadius: "2px 2px 0 0",
                    transition: "height 150ms ease",
                  }}
                />
                <div style={{ fontSize: "11px", color: "var(--steel-700)" }}>{h.hour}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
