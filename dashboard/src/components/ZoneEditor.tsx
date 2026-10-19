import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Plus,
  Trash2,
  Save,
  Download,
  Upload,
  Check,
  AlertTriangle,
  CornerUpLeft,
} from "lucide-react";
import { ZoneDefinition, ZonesConfig, ZoneType } from "../types";
import {
  Button,
  ZoneBadge,
  Kbd,
} from "../design/primitives";

interface ZoneEditorProps {
  initialConfig: ZonesConfig;
  snapshotUrl?: string;
  onSaveConfig: (config: ZonesConfig) => Promise<boolean>;
  personFootprints?: Array<{ x: number; y: number; track_id: number }>;
}

// Geometric line segment intersection check
export function doSegmentsIntersect(
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
  p4: [number, number]
): boolean {
  const ccw = (A: [number, number], B: [number, number], C: [number, number]) =>
    (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0]);

  return (
    ccw(p1, p3, p4) !== ccw(p2, p3, p4) &&
    ccw(p1, p2, p3) !== ccw(p1, p2, p4)
  );
}

// Check polygon self-intersection
export function isPolygonSelfIntersecting(polygon: number[][]): boolean {
  const n = polygon.length;
  if (n < 4) return false;

  for (let i = 0; i < n; i++) {
    const a1: [number, number] = [polygon[i][0], polygon[i][1]];
    const a2: [number, number] = [polygon[(i + 1) % n][0], polygon[(i + 1) % n][1]];

    for (let j = i + 2; j < n; j++) {
      if ((i === 0 && j === n - 1) || Math.abs(i - j) <= 1) continue;
      const b1: [number, number] = [polygon[j][0], polygon[j][1]];
      const b2: [number, number] = [polygon[(j + 1) % n][0], polygon[(j + 1) % n][1]];

      if (doSegmentsIntersect(a1, a2, b1, b2)) {
        return true;
      }
    }
  }
  return false;
}

export const ZoneEditor: React.FC<ZoneEditorProps> = ({
  initialConfig,
  snapshotUrl = "/api/zones/snapshot",
  onSaveConfig,
  personFootprints = [],
}) => {
  const [config, setConfig] = useState<ZonesConfig>(initialConfig);
  const [history, setHistory] = useState<ZonesConfig[]>([initialConfig]);
  const [historyIndex, setHistoryIndex] = useState<number>(0);

  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(
    initialConfig.zones.length > 0 ? initialConfig.zones[0].id : null
  );
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [draftPolygon, setDraftPolygon] = useState<number[][]>([]);
  const [newZoneId, setNewZoneId] = useState<string>("");
  const [newZoneType, setNewZoneType] = useState<ZoneType>("restricted");
  const [newRequiredPPE, setNewRequiredPPE] = useState<string[]>(["helmet"]);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [gridSnap, setGridSnap] = useState<boolean>(true);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const pushState = useCallback((newCfg: ZonesConfig) => {
    const newHist = history.slice(0, historyIndex + 1);
    newHist.push(newCfg);
    setHistory(newHist);
    setHistoryIndex(newHist.length - 1);
    setConfig(newCfg);
  }, [history, historyIndex]);

  const handleUndo = useCallback(() => {
    if (historyIndex > 0) {
      setHistoryIndex(historyIndex - 1);
      setConfig(history[historyIndex - 1]);
    }
  }, [history, historyIndex]);

  const handleRedo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      setHistoryIndex(historyIndex + 1);
      setConfig(history[historyIndex + 1]);
    }
  }, [history, historyIndex]);

  // Keyboard shortcuts (Cmd+Z undo, Enter close draft, Esc cancel)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "z") {
        e.preventDefault();
        if (e.shiftKey) handleRedo();
        else handleUndo();
      }
      if (e.key === "Escape" && isDrawing) {
        setIsDrawing(false);
        setDraftPolygon([]);
        setValidationError(null);
      }
      if (e.key === "Enter" && isDrawing && draftPolygon.length >= 3) {
        handleCommitNewZone();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleUndo, handleRedo, isDrawing, draftPolygon]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = config.frame.width / rect.width;
    const scaleY = config.frame.height / rect.height;

    let x = (e.clientX - rect.left) * scaleX;
    let y = (e.clientY - rect.top) * scaleY;

    // 8px grid snap unless Shift is held
    if (gridSnap && !e.shiftKey) {
      x = Math.round(x / 8) * 8;
      y = Math.round(y / 8) * 8;
    } else {
      x = Math.round(x);
      y = Math.round(y);
    }

    const next = [...draftPolygon, [x, y]];
    setDraftPolygon(next);

    if (isPolygonSelfIntersecting(next)) {
      setValidationError("Polygon lines must not intersect.");
    } else {
      setValidationError(null);
    }
  };

  const handleStartNewZone = () => {
    setIsDrawing(true);
    setDraftPolygon([]);
    setNewZoneId(`zone-${config.zones.length + 1}`);
    setNewZoneType("restricted");
    setNewRequiredPPE(["helmet"]);
    setValidationError(null);
  };

  const handleCommitNewZone = () => {
    if (draftPolygon.length < 3) {
      setValidationError("Zone polygon requires at least 3 vertices.");
      return;
    }
    if (!newZoneId.trim()) {
      setValidationError("Zone name is required.");
      return;
    }
    if (config.zones.some((z) => z.id === newZoneId.trim())) {
      setValidationError(`Zone ID '${newZoneId.trim()}' already exists.`);
      return;
    }
    if (isPolygonSelfIntersecting(draftPolygon)) {
      setValidationError("Self-intersecting polygons are invalid.");
      return;
    }

    const newZone: ZoneDefinition = {
      id: newZoneId.trim(),
      type: newZoneType,
      required_ppe: newRequiredPPE,
      polygon: draftPolygon,
    };

    const nextCfg: ZonesConfig = {
      ...config,
      zones: [...config.zones, newZone],
    };

    pushState(nextCfg);
    setIsDrawing(false);
    setDraftPolygon([]);
    setSelectedZoneId(newZone.id);
    setValidationError(null);
    showToast("Zone authored. Click 'Save zones' to hot-reload engine.");
  };

  const handleSaveToBackend = async () => {
    setSaving(true);
    try {
      const ok = await onSaveConfig(config);
      if (ok) {
        showToast("Zone saved");
      } else {
        setValidationError("Failed to save zones to engine.");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSelected = () => {
    if (!selectedZoneId) return;
    const nextCfg = {
      ...config,
      zones: config.zones.filter((z) => z.id !== selectedZoneId),
    };
    pushState(nextCfg);
    setSelectedZoneId(nextCfg.zones.length > 0 ? nextCfg.zones[0].id : null);
    showToast("Zone deleted");
  };

  const handleExportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(config, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", "zones.json");
    dlAnchor.click();
  };

  const handleImportJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (parsed.zones && Array.isArray(parsed.zones)) {
          pushState(parsed);
          showToast("Zones imported");
        } else {
          setValidationError("Invalid zones.json format");
        }
      } catch {
        setValidationError("Could not parse JSON file");
      }
    };
    reader.readAsText(file);
  };

  const activeZone = config.zones.find((z) => z.id === selectedZoneId);

  return (
    <div style={{ display: "flex", height: "calc(100vh - 48px)", overflow: "hidden" }}>
      {/* Hidden file input for import */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleImportJson}
        accept=".json"
        style={{ display: "none" }}
      />

      {/* Main Canvas Area */}
      <div
        style={{
          flex: 1,
          backgroundColor: "#10161B",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Editor Toolbar */}
        <div
          style={{
            padding: "8px 16px",
            backgroundColor: "var(--surface)",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Button
              variant={isDrawing ? "danger" : "primary"}
              size="sm"
              icon={isDrawing ? undefined : <Plus size={14} />}
              onClick={isDrawing ? () => setIsDrawing(false) : handleStartNewZone}
            >
              {isDrawing ? "Cancel drawing" : "Draw zone"}
            </Button>

            {isDrawing && (
              <Button
                variant="primary"
                size="sm"
                icon={<Check size={14} />}
                disabled={draftPolygon.length < 3}
                onClick={handleCommitNewZone}
              >
                Finish polygon ({draftPolygon.length} pts)
              </Button>
            )}

            <Button
              variant="secondary"
              size="sm"
              icon={<CornerUpLeft size={14} />}
              disabled={historyIndex === 0}
              onClick={handleUndo}
              title="Undo (Cmd+Z)"
            >
              Undo
            </Button>

            <button
              type="button"
              onClick={() => setGridSnap(!gridSnap)}
              style={{
                background: "none",
                border: "none",
                padding: "2px 6px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: gridSnap ? "var(--surface-raised)" : "transparent",
                color: "var(--text-muted)",
                fontSize: "12px",
                cursor: "pointer",
                marginLeft: "8px",
              }}
            >
              Snap 8px: <strong style={{ color: "var(--text)" }}>{gridSnap ? "ON" : "OFF"}</strong>
            </button>
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              (hold <Kbd>Shift</Kbd> to freehand)
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Button variant="ghost" size="sm" icon={<Upload size={14} />} onClick={() => fileInputRef.current?.click()}>
              Import
            </Button>
            <Button variant="ghost" size="sm" icon={<Download size={14} />} onClick={handleExportJson}>
              Export
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Save size={14} />}
              loading={saving}
              onClick={handleSaveToBackend}
            >
              Save zones
            </Button>
          </div>
        </div>

        {/* Validation Error Banner */}
        {validationError && (
          <div
            role="alert"
            style={{
              padding: "6px 16px",
              backgroundColor: "var(--danger-subtle)",
              color: "var(--danger-strong)",
              borderBottom: "1px solid var(--danger)",
              fontSize: "12px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              zIndex: 10,
            }}
          >
            <AlertTriangle size={14} />
            <span>{validationError}</span>
          </div>
        )}

        {/* SVG Drawing Surface */}
        <div
          style={{
            flex: 1,
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
          }}
        >
          <img
            src={snapshotUrl}
            alt="Camera snapshot for zone alignment"
            style={{
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
              pointerEvents: "none",
            }}
            onError={(e) => {
              // fallback if snapshot not yet captured
              e.currentTarget.style.display = "none";
            }}
          />

          <svg
            viewBox={`0 0 ${config.frame.width} ${config.frame.height}`}
            onClick={handleSvgClick}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              cursor: isDrawing ? "crosshair" : "default",
            }}
          >
            {/* Existing Zones */}
            {config.zones.map((zone) => {
              const isSelected = zone.id === selectedZoneId;
              const strokeColor =
                zone.type === "danger"
                  ? "var(--danger)"
                  : zone.type === "restricted"
                  ? "var(--warn)"
                  : "var(--info)";
              const fillColor =
                zone.type === "danger"
                  ? "rgba(232, 89, 12, 0.2)"
                  : zone.type === "restricted"
                  ? "rgba(242, 169, 0, 0.2)"
                  : "rgba(31, 111, 208, 0.2)";

              const pts = zone.polygon.map((p) => `${p[0]},${p[1]}`).join(" ");

              return (
                <g key={zone.id} onClick={(e) => { e.stopPropagation(); setSelectedZoneId(zone.id); }}>
                  <polygon
                    points={pts}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={isSelected ? "4" : "2"}
                    strokeDasharray={isSelected ? "6,3" : "none"}
                    style={{ cursor: "pointer" }}
                  />
                  {/* Vertices */}
                  {isSelected &&
                    zone.polygon.map((pt, idx) => (
                      <circle
                        key={idx}
                        cx={pt[0]}
                        cy={pt[1]}
                        r={6}
                        fill="#FFFFFF"
                        stroke={strokeColor}
                        strokeWidth={2}
                      />
                    ))}
                </g>
              );
            })}

            {/* In-progress Draft Polygon */}
            {isDrawing && draftPolygon.length > 0 && (
              <g>
                <polyline
                  points={draftPolygon.map((p) => `${p[0]},${p[1]}`).join(" ")}
                  fill="rgba(31, 111, 208, 0.15)"
                  stroke="var(--info)"
                  strokeWidth="2"
                  strokeDasharray="4,4"
                />
                {draftPolygon.map((pt, idx) => (
                  <circle
                    key={idx}
                    cx={pt[0]}
                    cy={pt[1]}
                    r={5}
                    fill="var(--info)"
                    stroke="#FFFFFF"
                    strokeWidth={2}
                  />
                ))}
              </g>
            )}

            {/* Live Person Footprints overlay */}
            {personFootprints.map((fp) => (
              <circle
                key={fp.track_id}
                cx={fp.x}
                cy={fp.y}
                r={4}
                fill="var(--ok)"
                stroke="#FFFFFF"
                strokeWidth={1.5}
              />
            ))}
          </svg>
        </div>
      </div>

      {/* Side Panel: Zone Properties & List */}
      <aside
        style={{
          width: "320px",
          backgroundColor: "var(--surface)",
          borderLeft: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        <div style={{ padding: "16px", borderBottom: "1px solid var(--border)" }}>
          <h2 style={{ fontSize: "16px", margin: "0 0 4px 0" }}>Zones Inventory</h2>
          <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: 0 }}>
            {config.zones.length} zones configured.
          </p>
        </div>

        <div style={{ padding: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
          {config.zones.map((zone) => {
            const isSelected = zone.id === selectedZoneId;
            return (
              <div
                key={zone.id}
                onClick={() => setSelectedZoneId(zone.id)}
                style={{
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: isSelected ? "var(--surface-raised)" : "transparent",
                  border: isSelected ? "1px solid var(--border-strong)" : "1px solid transparent",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: "13px" }}>{zone.id}</strong>
                  <ZoneBadge type={zone.type} name={zone.type} />
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  PPE: {zone.required_ppe.join(", ") || "none"} &middot; {zone.polygon.length} points
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Zone Properties Editor */}
        {activeZone && (
          <div style={{ padding: "16px", borderTop: "1px solid var(--border)", marginTop: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <span style={{ fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: "var(--text-muted)" }}>
                Selected: {activeZone.id}
              </span>
              <Button
                variant="danger"
                size="sm"
                icon={<Trash2 size={13} />}
                onClick={handleDeleteSelected}
              >
                Delete
              </Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div>
                <label htmlFor="zone-type-select" style={{ fontSize: "12px", color: "var(--text-muted)" }}>Zone Classification</label>
                <select
                  id="zone-type-select"
                  aria-label="Zone Classification"
                  value={activeZone.type}
                  onChange={(e) => {
                    const nextCfg = {
                      ...config,
                      zones: config.zones.map((z) =>
                        z.id === activeZone.id ? { ...z, type: e.target.value as ZoneType } : z
                      ),
                    };
                    pushState(nextCfg);
                  }}
                  style={{
                    width: "100%",
                    marginTop: "4px",
                    padding: "6px 8px",
                    backgroundColor: "var(--surface-raised)",
                    color: "var(--text)",
                    border: "1px solid var(--border-strong)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "13px",
                  }}
                >
                  <option value="safe">Safe</option>
                  <option value="restricted">Restricted</option>
                  <option value="danger">Danger</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: "12px", color: "var(--text-muted)" }}>Required PPE</label>
                <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                  {["helmet", "vest"].map((ppe) => {
                    const hasPPE = activeZone.required_ppe.includes(ppe);
                    return (
                      <button
                        key={ppe}
                        onClick={() => {
                          const nextPPE = hasPPE
                            ? activeZone.required_ppe.filter((p) => p !== ppe)
                            : [...activeZone.required_ppe, ppe];
                          const nextCfg = {
                            ...config,
                            zones: config.zones.map((z) =>
                              z.id === activeZone.id ? { ...z, required_ppe: nextPPE } : z
                            ),
                          };
                          pushState(nextCfg);
                        }}
                        style={{
                          padding: "4px 8px",
                          borderRadius: "var(--radius-sm)",
                          border: hasPPE ? "1px solid var(--info)" : "1px solid var(--border-strong)",
                          backgroundColor: hasPPE ? "var(--info-subtle)" : "var(--surface-raised)",
                          color: hasPPE ? "var(--info-strong)" : "var(--text)",
                          fontSize: "12px",
                          cursor: "pointer",
                        }}
                      >
                        {ppe}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div
          role="status"
          style={{
            position: "fixed",
            bottom: "24px",
            right: "24px",
            padding: "10px 18px",
            backgroundColor: "var(--text)",
            color: "var(--surface-raised)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-popover)",
            fontSize: "13px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            zIndex: 9999,
          }}
        >
          <Check size={14} style={{ color: "var(--ok)" }} />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
};
