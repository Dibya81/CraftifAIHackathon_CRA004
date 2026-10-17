import React, { useState } from "react";
import { ZoneDefinition, ZonesConfig, ZoneType } from "../types";

interface ZoneEditorProps {
  initialConfig: ZonesConfig;
  snapshotUrl?: string;
  onSaveConfig: (config: ZonesConfig) => Promise<boolean>;
}

export const ZoneEditor: React.FC<ZoneEditorProps> = ({
  initialConfig,
  snapshotUrl = "/api/zones/snapshot",
  onSaveConfig,
}) => {
  const [config, setConfig] = useState<ZonesConfig>(initialConfig);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(
    initialConfig.zones.length > 0 ? initialConfig.zones[0].id : null
  );
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [draftPolygon, setDraftPolygon] = useState<number[][]>([]);
  const [newZoneId, setNewZoneId] = useState<string>("");
  const [newZoneType, setNewZoneType] = useState<ZoneType>("restricted");
  const [newRequiredPPE, setNewRequiredPPE] = useState<string[]>(["helmet"]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = config.frame.width / rect.width;
    const scaleY = config.frame.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    setDraftPolygon([...draftPolygon, [x, y]]);
  };

  const handleStartNewZone = () => {
    setIsDrawing(true);
    setDraftPolygon([]);
    setNewZoneId(`zone-${config.zones.length + 1}`);
    setNewZoneType("restricted");
    setNewRequiredPPE(["helmet"]);
  };

  const handleSaveZone = async () => {
    if (isDrawing) {
      if (draftPolygon.length < 3) {
        alert("A polygon requires at least 3 vertices.");
        return;
      }
      if (!newZoneId.trim()) {
        alert("Zone ID is required.");
        return;
      }
      // Check duplicate ID
      if (config.zones.some((z) => z.id === newZoneId.trim())) {
        alert("Zone ID must be unique.");
        return;
      }

      const newZone: ZoneDefinition = {
        id: newZoneId.trim(),
        type: newZoneType,
        required_ppe: newRequiredPPE,
        polygon: draftPolygon,
      };

      const updatedConfig: ZonesConfig = {
        ...config,
        zones: [...config.zones, newZone],
      };

      setSaving(true);
      const success = await onSaveConfig(updatedConfig);
      setSaving(false);
      if (success) {
        setConfig(updatedConfig);
        setIsDrawing(false);
        setDraftPolygon([]);
        setSelectedZoneId(newZone.id);
        showToast("Zone saved");
      }
    } else if (selectedZoneId) {
      // Save existing configuration
      setSaving(true);
      const success = await onSaveConfig(config);
      setSaving(false);
      if (success) {
        showToast("Zone saved");
      }
    }
  };

  const handleDeleteZone = async (id: string) => {
    if (!confirm(`Delete zone "${id}"?`)) return;
    const updatedConfig: ZonesConfig = {
      ...config,
      zones: config.zones.filter((z) => z.id !== id),
    };
    setSaving(true);
    const success = await onSaveConfig(updatedConfig);
    setSaving(false);
    if (success) {
      setConfig(updatedConfig);
      setSelectedZoneId(updatedConfig.zones.length > 0 ? updatedConfig.zones[0].id : null);
      showToast("Zone removed");
    }
  };

  const togglePPE = (ppe: string) => {
    if (newRequiredPPE.includes(ppe)) {
      setNewRequiredPPE(newRequiredPPE.filter((p) => p !== ppe));
    } else {
      setNewRequiredPPE([...newRequiredPPE, ppe]);
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "24px", position: "relative" }}>
      {/* Toast Banner */}
      {toastMessage && (
        <div
          role="status"
          style={{
            position: "fixed",
            bottom: "24px",
            right: "24px",
            backgroundColor: "var(--steel-900)",
            color: "var(--white)",
            padding: "10px 18px",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-md)",
            borderLeft: "4px solid var(--clear-green)",
            zIndex: 1000,
            fontSize: "14px",
            fontWeight: 500,
          }}
        >
          {toastMessage}
        </div>
      )}

      {/* Frame with SVG Drawing Surface */}
      <div
        style={{
          backgroundColor: "var(--steel-900)",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
          boxShadow: "var(--shadow-md)",
        }}
      >
        <div
          style={{
            padding: "10px 16px",
            backgroundColor: "var(--steel-800)",
            color: "var(--white)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontFamily: "var(--font-heading)", fontSize: "16px" }}>
            {isDrawing ? "DRAWING NEW ZONE (CLICK ON FRAME TO ADD VERTICES)" : "ZONE PREVIEW & GEOMETRY"}
          </span>
          {isDrawing && (
            <span style={{ fontSize: "12px", color: "var(--caution-amber)" }}>
              {draftPolygon.length} vertices plotted
            </span>
          )}
        </div>

        <div style={{ position: "relative", width: "100%", paddingTop: "56.25%", backgroundColor: "#12191F" }}>
          <img
            src={snapshotUrl}
            alt="Reference snapshot frame"
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />

          {/* Interactive SVG Layer */}
          <svg
            onClick={handleSvgClick}
            data-testid="zone-editor-svg"
            viewBox={`0 0 ${config.frame.width} ${config.frame.height}`}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              cursor: isDrawing ? "crosshair" : "default",
            }}
          >
            {/* Existing Saved Zones */}
            {config.zones.map((zone) => {
              const isSelected = zone.id === selectedZoneId;
              const pointsStr = zone.polygon.map((p) => `${p[0]},${p[1]}`).join(" ");
              let stroke = "var(--signal-blue)";
              let fill = "rgba(31, 111, 208, 0.15)";
              if (zone.type === "danger") {
                stroke = "var(--hazard-orange)";
                fill = "rgba(232, 89, 12, 0.20)";
              } else if (zone.type === "restricted") {
                stroke = "var(--caution-amber)";
                fill = "rgba(242, 169, 0, 0.20)";
              }

              return (
                <g key={zone.id} onClick={() => !isDrawing && setSelectedZoneId(zone.id)} style={{ cursor: "pointer" }}>
                  <polygon
                    points={pointsStr}
                    stroke={isSelected ? "#FFF" : stroke}
                    strokeWidth={isSelected ? 4 : 2}
                    fill={fill}
                  />
                  {zone.polygon[0] && (
                    <text
                      x={zone.polygon[0][0] + 10}
                      y={zone.polygon[0][1] + 20}
                      fill="#FFF"
                      fontSize="14"
                      fontWeight="bold"
                      stroke="rgba(0,0,0,0.8)"
                      strokeWidth="2"
                      paintOrder="stroke"
                    >
                      {zone.id}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Currently Drawing Polygon */}
            {isDrawing && draftPolygon.length > 0 && (
              <g>
                <polyline
                  points={draftPolygon.map((p) => `${p[0]},${p[1]}`).join(" ")}
                  fill="rgba(242, 169, 0, 0.2)"
                  stroke="var(--caution-amber)"
                  strokeWidth={3}
                  strokeDasharray="6 4"
                />
                {draftPolygon.map(([x, y], idx) => (
                  <circle key={idx} cx={x} cy={y} r={6} fill="#FFF" stroke="var(--hazard-orange)" strokeWidth={2} />
                ))}
              </g>
            )}
          </svg>
        </div>
      </div>

      {/* Controls & Configuration Sidebar */}
      <div
        style={{
          backgroundColor: "var(--white)",
          padding: "20px",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-sm)",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
        }}
      >
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "20px" }}>Zone configuration</h3>

        {!isDrawing ? (
          <>
            <div>
              <label style={{ display: "block", fontSize: "12px", color: "var(--steel-700)", marginBottom: "6px" }}>
                Active zones
              </label>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {config.zones.map((z) => (
                  <div
                    key={z.id}
                    onClick={() => setSelectedZoneId(z.id)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid",
                      borderColor: z.id === selectedZoneId ? "var(--signal-blue)" : "var(--concrete-100)",
                      backgroundColor: z.id === selectedZoneId ? "var(--signal-blue-light)" : "var(--concrete-50)",
                      cursor: "pointer",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "13px" }}>{z.id}</div>
                      <div style={{ fontSize: "11px", color: "var(--steel-700)" }}>
                        {z.type} &middot; PPE: {z.required_ppe.join(", ") || "none"}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteZone(z.id);
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--hazard-orange)",
                        cursor: "pointer",
                        fontSize: "12px",
                      }}
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={handleStartNewZone}
              style={{
                backgroundColor: "var(--steel-900)",
                color: "var(--white)",
                border: "none",
                padding: "10px 16px",
                borderRadius: "var(--radius-sm)",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              + Draw new zone
            </button>
          </>
        ) : (
          <>
            {/* New Zone Form */}
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Zone ID
              </label>
              <input
                type="text"
                value={newZoneId}
                onChange={(e) => setNewZoneId(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--steel-700)",
                  fontSize: "13px",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Zone type
              </label>
              <select
                value={newZoneType}
                onChange={(e) => setNewZoneType(e.target.value as ZoneType)}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--steel-700)",
                  fontSize: "13px",
                }}
              >
                <option value="safe">Safe (Authorized access)</option>
                <option value="restricted">Restricted (PPE check required)</option>
                <option value="danger">Danger (No entry / strict dwell limit)</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
                Required PPE
              </label>
              <div style={{ display: "flex", gap: "16px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}>
                  <input
                    type="checkbox"
                    checked={newRequiredPPE.includes("helmet")}
                    onChange={() => togglePPE("helmet")}
                  />
                  Hard hat
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}>
                  <input
                    type="checkbox"
                    checked={newRequiredPPE.includes("vest")}
                    onChange={() => togglePPE("vest")}
                  />
                  Safety vest
                </label>
              </div>
            </div>

            <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
              <button
                onClick={handleSaveZone}
                disabled={saving || draftPolygon.length < 3}
                style={{
                  flex: 1,
                  backgroundColor: "var(--signal-blue)",
                  color: "var(--white)",
                  border: "none",
                  padding: "10px",
                  borderRadius: "var(--radius-sm)",
                  fontWeight: 600,
                  cursor: draftPolygon.length >= 3 ? "pointer" : "not-allowed",
                  opacity: draftPolygon.length >= 3 ? 1 : 0.6,
                }}
              >
                {saving ? "Saving..." : "Save zone"}
              </button>
              <button
                onClick={() => {
                  setIsDrawing(false);
                  setDraftPolygon([]);
                }}
                style={{
                  backgroundColor: "var(--concrete-100)",
                  border: "none",
                  padding: "10px 14px",
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
            </div>
            {draftPolygon.length > 0 && (
              <button
                onClick={() => setDraftPolygon(draftPolygon.slice(0, -1))}
                style={{
                  background: "none",
                  border: "1px solid var(--concrete-100)",
                  padding: "6px",
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                  fontSize: "12px",
                }}
              >
                Undo last point
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
};
