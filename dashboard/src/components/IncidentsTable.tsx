import React, { useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Download,
  CheckSquare,
  Search,
  RefreshCw,
} from "lucide-react";
import { Incident } from "../api/schema";
import {
  Button,
  SeverityBadge,
  ZoneBadge,
  StatusBadge,
  Table,
  NumCell,
  EmptyState,
} from "../design/primitives";
import { formatIncidentName } from "./IncidentFeed";

interface IncidentsTableProps {
  incidents: Incident[];
  onSelectIncident: (incident: Incident) => void;
  onBulkAck: (ids: string[]) => Promise<void>;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const IncidentsTable: React.FC<IncidentsTableProps> = ({
  incidents,
  onSelectIncident,
  onBulkAck,
  onRefresh,
  isLoading = false,
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBulkAcking, setIsBulkAcking] = useState(false);

  // Read filter params from URL
  const query = searchParams.get("q") || "";
  const severityFilter = searchParams.get("severity") || "ALL";
  const typeFilter = searchParams.get("type") || "ALL";
  const statusFilter = searchParams.get("status") || "ALL";

  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (!value || value === "ALL") {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next);
  };

  const clearFilters = () => {
    setSearchParams(new URLSearchParams());
  };

  // Filter incidents locally
  const filtered = useMemo(() => {
    return incidents.filter((inc) => {
      if (severityFilter !== "ALL" && inc.severity !== severityFilter) return false;
      if (typeFilter !== "ALL" && inc.type !== typeFilter) return false;
      if (statusFilter !== "ALL" && inc.status !== statusFilter) return false;
      if (query.trim()) {
        const q = query.toLowerCase();
        const matchesId = inc.incident_id.toLowerCase().includes(q);
        const matchesZone = inc.zone ? inc.zone.toLowerCase().includes(q) : false;
        const matchesTrack = String(inc.track_id).includes(q);
        if (!matchesId && !matchesZone && !matchesTrack) return false;
      }
      return true;
    });
  }, [incidents, severityFilter, typeFilter, statusFilter, query]);

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((i) => i.incident_id)));
    }
  };

  const toggleSelectOne = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleBulkAck = async () => {
    if (selectedIds.size === 0) return;
    setIsBulkAcking(true);
    try {
      await onBulkAck(Array.from(selectedIds));
      setSelectedIds(new Set());
    } finally {
      setIsBulkAcking(false);
    }
  };

  const handleExportCsv = () => {
    window.open("/api/incidents/export.csv", "_blank");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "20px" }}>
      {/* Title & Filter Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <h1 style={{ fontSize: "24px", margin: 0 }}>Incident Records</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "13px", margin: "2px 0 0 0" }}>
            Audit log of all detected safety infractions with proof linkages.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {selectedIds.size > 0 && (
            <Button
              variant="primary"
              size="sm"
              icon={<CheckSquare size={14} />}
              loading={isBulkAcking}
              onClick={handleBulkAck}
            >
              Acknowledge selected ({selectedIds.size})
            </Button>
          )}

          <Button
            variant="secondary"
            size="sm"
            icon={<Download size={14} />}
            onClick={handleExportCsv}
          >
            Export CSV
          </Button>

          {onRefresh && (
            <Button
              variant="ghost"
              size="sm"
              icon={<RefreshCw size={14} />}
              loading={isLoading}
              onClick={onRefresh}
            >
              Refresh
            </Button>
          )}
        </div>
      </div>

      {/* Filter Controls Row */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          alignItems: "center",
          flexWrap: "wrap",
          padding: "10px 14px",
          backgroundColor: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flex: 1, minWidth: "220px" }}>
          <Search size={14} style={{ color: "var(--text-muted)" }} />
          <input
            type="text"
            aria-label="Filter by ID, zone, or track"
            value={query}
            onChange={(e) => updateParam("q", e.target.value)}
            style={{
              width: "100%",
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text)",
              fontSize: "13px",
              fontFamily: "var(--font-body)",
            }}
          />
        </div>

        <select
          aria-label="Filter by severity"
          value={severityFilter}
          onChange={(e) => updateParam("severity", e.target.value)}
          style={{
            padding: "4px 8px",
            backgroundColor: "var(--surface-raised)",
            color: "var(--text)",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-sm)",
            fontSize: "12px",
          }}
        >
          <option value="ALL">All Severities</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>

        <select
          aria-label="Filter by violation type"
          value={typeFilter}
          onChange={(e) => updateParam("type", e.target.value)}
          style={{
            padding: "4px 8px",
            backgroundColor: "var(--surface-raised)",
            color: "var(--text)",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-sm)",
            fontSize: "12px",
          }}
        >
          <option value="ALL">All Violation Types</option>
          <option value="NO_HELMET">No helmet</option>
          <option value="NO_VEST">No vest</option>
          <option value="ZONE_INTRUSION">Zone entry</option>
          <option value="DANGER_DWELL">Danger-zone dwell</option>
        </select>

        <select
          aria-label="Filter by status"
          value={statusFilter}
          onChange={(e) => updateParam("status", e.target.value)}
          style={{
            padding: "4px 8px",
            backgroundColor: "var(--surface-raised)",
            color: "var(--text)",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-sm)",
            fontSize: "12px",
          }}
        >
          <option value="ALL">All Statuses</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
        </select>

        {(query || severityFilter !== "ALL" || typeFilter !== "ALL" || statusFilter !== "ALL") && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
      </div>

      {/* Incidents Dense Table */}
      {filtered.length === 0 ? (
        <EmptyState
          title="No incidents match these filters"
          description="Adjust your search criteria or clear active filters."
          action={
            <Button variant="secondary" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          }
        />
      ) : (
        <Table>
          <thead>
            <tr>
              <th style={{ width: "32px", textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={selectedIds.size === filtered.length && filtered.length > 0}
                  onChange={toggleSelectAll}
                  aria-label="Select all incidents"
                />
              </th>
              <th>Incident ID</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Zone</th>
              <th style={{ textAlign: "right" }}>Track ID</th>
              <th style={{ textAlign: "right" }}>Duration</th>
              <th style={{ textAlign: "right" }}>Confidence</th>
              <th>Time</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((inc) => {
              const isSelected = selectedIds.has(inc.incident_id);
              return (
                <tr
                  key={inc.incident_id}
                  onClick={() => onSelectIncident(inc)}
                  style={{
                    cursor: "pointer",
                    backgroundColor: isSelected ? "var(--surface)" : undefined,
                  }}
                >
                  <td style={{ textAlign: "center" }} onClick={(e) => toggleSelectOne(inc.incident_id, e)}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      aria-label={`Select incident ${inc.incident_id}`}
                    />
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-muted)" }}>
                    {inc.incident_id.slice(0, 8)}...
                  </td>
                  <td>
                    <strong>{formatIncidentName(inc.type)}</strong>
                  </td>
                  <td>
                    <SeverityBadge severity={inc.severity} />
                  </td>
                  <td>
                    {inc.zone ? <ZoneBadge type={inc.zone} name={inc.zone} /> : <span style={{ color: "var(--text-muted)" }}>unassigned</span>}
                  </td>
                  <NumCell>#{inc.track_id}</NumCell>
                  <NumCell>{inc.duration_s.toFixed(1)} s</NumCell>
                  <NumCell>{(inc.confidence * 100).toFixed(0)}%</NumCell>
                  <td style={{ whiteSpace: "nowrap", color: "var(--text-muted)" }}>
                    {new Date(inc.timestamp).toLocaleTimeString()}
                  </td>
                  <td>
                    <StatusBadge status={inc.status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      )}
    </div>
  );
};
