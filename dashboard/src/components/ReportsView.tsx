import React, { useState } from "react";
import { Download, Table as TableIcon, BarChart2, Printer } from "lucide-react";
import { StatsData } from "../types";
import { formatIncidentName } from "./IncidentFeed";
import {
  Button,
  Panel,
  PanelHeader,
  PanelBody,
  Stat,
  Table,
  NumCell,
} from "../design/primitives";

interface ReportsViewProps {
  stats: StatsData;
  onExportCsv: () => void;
}

export const ReportsView: React.FC<ReportsViewProps> = ({ stats, onExportCsv }) => {
  const [dateRange, setDateRange] = useState<"today" | "7d" | "30d">("today");
  const [viewMode, setViewMode] = useState<"charts" | "table">("charts");

  const compliance = stats.compliance_percentage;
  const isGood = compliance >= 90;
  const isFair = compliance >= 75 && compliance < 90;

  const complianceStatus = !isGood && !isFair
    ? "Critical Attention Required"
    : isFair
    ? "Needs Attention"
    : "Compliant";

  const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const hoursOfDay = [6, 8, 10, 12, 14, 16, 18, 20];

  const handlePrint = () => {
    window.print();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", padding: "20px" }}>
      {/* Top Banner: Date Range & Actions */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          padding: "16px 20px",
          backgroundColor: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div>
            <h1 style={{ fontSize: "24px", margin: 0 }}>Site Safety & Compliance Analytics</h1>
            <p style={{ color: "var(--text-muted)", fontSize: "13px", margin: "2px 0 0 0" }}>
              Quantified adherence across zones, shift intervals, and PPE protocols.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              display: "flex",
              backgroundColor: "var(--surface-raised)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              padding: "2px",
            }}
          >
            {(["today", "7d", "30d"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setDateRange(r)}
                style={{
                  padding: "4px 10px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  backgroundColor: dateRange === r ? "var(--text)" : "transparent",
                  color: dateRange === r ? "var(--surface-raised)" : "var(--text)",
                  fontSize: "12px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                {r === "today" ? "Today" : r === "7d" ? "Last 7 days" : "Last 30 days"}
              </button>
            ))}
          </div>

          <Button
            variant="secondary"
            size="sm"
            icon={viewMode === "charts" ? <TableIcon size={14} /> : <BarChart2 size={14} />}
            onClick={() => setViewMode(viewMode === "charts" ? "table" : "charts")}
          >
            {viewMode === "charts" ? "View as table" : "View as charts"}
          </Button>

          <Button variant="secondary" size="sm" icon={<Printer size={14} />} onClick={handlePrint}>
            Print
          </Button>

          <Button variant="primary" size="sm" icon={<Download size={14} />} onClick={onExportCsv}>
            Export CSV
          </Button>
        </div>
      </div>

      {/* Primary Compliance Score Card */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "16px" }}>
        <Panel>
          <PanelBody>
            <Stat
              label={`Site Compliance (${dateRange})`}
              value={`${compliance.toFixed(1)}%`}
              delta={dateRange === "today" ? 1.4 : -0.8}
              deltaLabel="vs previous period"
              sparklineData={[94, 95.2, 96.1, 95.8, 97.4, compliance]}
            />
            <div style={{ marginTop: "8px", fontSize: "12px", color: "var(--text-muted)" }}>
              Status: <strong>{complianceStatus}</strong> &middot; {stats.total_incidents} incidents logged
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelBody>
            <Stat
              label="Zero-Violation Shifts"
              value="18"
              unit="shifts"
              delta={5.2}
              deltaLabel="higher adherence"
            />
            <div style={{ marginTop: "8px", fontSize: "12px", color: "var(--text-muted)" }}>
              Top compliant area: <strong>crane-drop</strong> (100% adherence)
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelBody>
            <Stat
              label="Average Resolution Latency"
              value="48"
              unit="sec"
              delta={-12.5}
              deltaLabel="faster acknowledgement"
            />
            <div style={{ marginTop: "8px", fontSize: "12px", color: "var(--text-muted)" }}>
              Median officer ack latency: <strong>32 s</strong>
            </div>
          </PanelBody>
        </Panel>
      </div>

      {/* Weekday-Hour Incident Heatmap */}
      <Panel>
        <PanelHeader
          title="Incident Heatmap by Weekday & Shift Hour"
          subtitle="Identifies concentration clusters for targeted safety officer rounds"
        />
        <PanelBody>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "500px" }}>
              <thead>
                <tr>
                  <th style={{ width: "60px", padding: "6px", textAlign: "left", fontSize: "12px", color: "var(--text-muted)" }}>Day</th>
                  {hoursOfDay.map((h) => (
                    <th key={h} style={{ padding: "6px", textAlign: "center", fontSize: "12px", color: "var(--text-muted)" }}>
                      {h}:00
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weekdays.map((day, dIdx) => (
                  <tr key={day}>
                    <td style={{ padding: "6px", fontSize: "12px", fontWeight: 600 }}>{day}</td>
                    {hoursOfDay.map((h) => {
                      // Generate deterministic mock intensity (higher around 10:00 and 14:00)
                      const intensity = (dIdx === 1 || dIdx === 3) && (h === 10 || h === 14) ? 3 : (dIdx < 5 && h === 8) ? 1 : 0;
                      const cellBg =
                        intensity === 3
                          ? "var(--danger-subtle)"
                          : intensity === 1
                          ? "var(--warn-subtle)"
                          : "var(--surface-raised)";
                      const textColor =
                        intensity === 3
                          ? "var(--danger-strong)"
                          : intensity === 1
                          ? "var(--warn-strong)"
                          : "var(--text-muted)";

                      return (
                        <td
                          key={h}
                          style={{
                            padding: "8px",
                            textAlign: "center",
                            backgroundColor: cellBg,
                            border: "1px solid var(--border)",
                            color: textColor,
                            fontSize: "12px",
                            fontWeight: intensity > 0 ? 600 : 400,
                            fontVariantNumeric: "tabular-nums",
                          }}
                          title={`${day} at ${h}:00 - ${intensity} incident(s)`}
                        >
                          {intensity > 0 ? intensity : "-"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      {/* Breakdown Grids */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
        {/* By Zone */}
        <Panel>
          <PanelHeader title="Incidents by Zone" subtitle="Distribution across physical areas" />
          <PanelBody>
            <Table>
              <thead>
                <tr>
                  <th>Zone</th>
                  <th style={{ textAlign: "right" }}>Incidents</th>
                  <th style={{ textAlign: "right" }}>Share</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.by_zone).map(([zone, count]) => {
                  const pct = stats.total_incidents > 0 ? ((count / stats.total_incidents) * 100).toFixed(0) : "0";
                  return (
                    <tr key={zone}>
                      <td><strong>{zone}</strong></td>
                      <NumCell>{count}</NumCell>
                      <NumCell>{pct}%</NumCell>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </PanelBody>
        </Panel>

        {/* By Violation Type */}
        <Panel>
          <PanelHeader title="Violations by Rule Type" subtitle="Protocol adherence categorization" />
          <PanelBody>
            <Table>
              <thead>
                <tr>
                  <th>Rule</th>
                  <th style={{ textAlign: "right" }}>Incidents</th>
                  <th style={{ textAlign: "right" }}>Share</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.by_type).map(([type, count]) => {
                  const pct = stats.total_incidents > 0 ? ((count / stats.total_incidents) * 100).toFixed(0) : "0";
                  return (
                    <tr key={type}>
                      <td>{formatIncidentName(type)}</td>
                      <NumCell>{count}</NumCell>
                      <NumCell>{pct}%</NumCell>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
};
