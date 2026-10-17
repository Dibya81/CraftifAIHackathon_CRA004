import React, { useState, useEffect } from "react";
import { ZoneDefinition } from "../types";

interface ActiveDetection {
  track_id: number;
  box: [number, number, number, number]; // [x1, y1, x2, y2]
  label?: string;
  violating?: boolean;
}

interface VideoPlayerWithZonesProps {
  zones: ZoneDefinition[];
  activeZoneViolations?: string[]; // IDs of zones with active violations
  activeDetections?: ActiveDetection[];
  snapshotUrl?: string;
  frameWidth?: number;
  frameHeight?: number;
  fps?: number;
}

export const getZoneColor = (type: string, hasViolation: boolean): { stroke: string; fill: string } => {
  if (hasViolation) {
    return {
      stroke: "var(--hazard-orange)",
      fill: "rgba(232, 89, 12, 0.28)",
    };
  }
  switch (type) {
    case "danger":
      return {
        stroke: "var(--hazard-orange)",
        fill: "rgba(232, 89, 12, 0.14)",
      };
    case "restricted":
      return {
        stroke: "var(--caution-amber)",
        fill: "rgba(242, 169, 0, 0.14)",
      };
    case "safe":
    default:
      return {
        stroke: "var(--signal-blue)",
        fill: "rgba(31, 111, 208, 0.10)",
      };
  }
};

export const VideoPlayerWithZones: React.FC<VideoPlayerWithZonesProps> = ({
  zones,
  activeZoneViolations = [],
  activeDetections = [],
  snapshotUrl = "/api/zones/snapshot",
  frameWidth = 1920,
  frameHeight = 1080,
  fps = 30,
}) => {
  const [currentSnapshot, setCurrentSnapshot] = useState<string>(snapshotUrl);
  const [imageLoaded, setImageLoaded] = useState<boolean>(false);
  const [showOverlays, setShowOverlays] = useState<boolean>(true);

  // Periodically refresh snapshot timestamp to simulate live MJPEG stream
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentSnapshot(`${snapshotUrl}?t=${Date.now()}`);
    }, 1500);
    return () => clearInterval(interval);
  }, [snapshotUrl]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        backgroundColor: "var(--steel-900)",
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
        boxShadow: "var(--shadow-md)",
      }}
    >
      {/* Top Header Bar inside Video Container */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 10,
          padding: "10px 16px",
          background: "linear-gradient(to bottom, rgba(30,42,51,0.85) 0%, rgba(30,42,51,0) 100%)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          color: "var(--white)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            style={{
              display: "inline-block",
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              backgroundColor: "var(--hazard-orange)",
              boxShadow: "0 0 6px var(--hazard-orange)",
            }}
          />
          <span style={{ fontFamily: "var(--font-heading)", fontSize: "16px", letterSpacing: "0.5px" }}>
            LIVE STREAM &middot; CAM-01
          </span>
          <span style={{ fontSize: "12px", opacity: 0.8 }}>({fps} FPS)</span>
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={() => setShowOverlays(!showOverlays)}
            style={{
              background: showOverlays ? "rgba(31,111,208,0.5)" : "rgba(255,255,255,0.15)",
              border: "1px solid rgba(255,255,255,0.3)",
              color: "var(--white)",
              fontSize: "12px",
              padding: "4px 10px",
              borderRadius: "var(--radius-sm)",
              cursor: "pointer",
            }}
          >
            {showOverlays ? "Hide zones" : "Show zones"}
          </button>
        </div>
      </div>

      {/* Video / Snapshot Viewport with Aspect Ratio */}
      <div
        style={{
          position: "relative",
          width: "100%",
          paddingTop: "56.25%", // 16:9 Aspect Ratio
          backgroundColor: "#141c22",
        }}
      >
        {/* Background Image / Snapshot */}
        <img
          src={currentSnapshot}
          alt="Live camera feed"
          onLoad={() => setImageLoaded(true)}
          onError={() => setImageLoaded(false)}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: imageLoaded ? "block" : "none",
          }}
        />

        {/* Fallback industrial scene canvas if image fails to load or offline */}
        {!imageLoaded && (
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--concrete-100)",
              background: "radial-gradient(ellipse at center, #263540 0%, #161f26 100%)",
            }}
          >
            <div style={{ fontSize: "36px", marginBottom: "8px" }}>📹</div>
            <div style={{ fontFamily: "var(--font-heading)", fontSize: "18px" }}>CONNECTING TO CAMERA PIPELINE</div>
            <div style={{ fontSize: "12px", color: "#8E9DA8", marginTop: "4px" }}>
              Source: DeepStream / PipeGen TRT Engine
            </div>
          </div>
        )}

        {/* SVG Zone & Detection Overlay Layer */}
        {showOverlays && (
          <svg
            data-testid="zones-svg-overlay"
            viewBox={`0 0 ${frameWidth} ${frameHeight}`}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              pointerEvents: "none",
            }}
          >
            {/* Zone Polygons */}
            {zones.map((zone) => {
              const hasViolation = activeZoneViolations.includes(zone.id);
              const { stroke, fill } = getZoneColor(zone.type, hasViolation);
              const pointsStr = zone.polygon.map((p) => `${p[0]},${p[1]}`).join(" ");

              // Calculate centroid for zone label
              const xs = zone.polygon.map((p) => p[0]);
              const ys = zone.polygon.map((p) => p[1]);
              const minX = Math.min(...xs);
              const minY = Math.min(...ys);

              return (
                <g key={zone.id}>
                  <polygon
                    data-testid={`zone-polygon-${zone.id}`}
                    points={pointsStr}
                    stroke={stroke}
                    strokeWidth={hasViolation ? 4 : 2}
                    fill={fill}
                    strokeDasharray={zone.type === "restricted" ? "8 4" : undefined}
                    style={{
                      transition: "stroke 150ms ease, fill 150ms ease, stroke-width 150ms ease",
                    }}
                  />
                  {/* Zone Tag */}
                  <g transform={`translate(${minX + 12}, ${minY + 24})`}>
                    <rect
                      x={0}
                      y={-16}
                      width={zone.id.length * 10 + 70}
                      height={22}
                      rx={3}
                      fill="rgba(30, 42, 51, 0.85)"
                      stroke={stroke}
                      strokeWidth={1}
                    />
                    <text
                      x={6}
                      y={-1}
                      fill="#FFFFFF"
                      fontSize="12"
                      fontFamily="IBM Plex Sans, sans-serif"
                      fontWeight="bold"
                    >
                      {zone.id} [{zone.type}]
                    </text>
                  </g>
                </g>
              );
            })}

            {/* Tracked Detection Bounding Boxes */}
            {activeDetections.map((det) => {
              const [x1, y1, x2, y2] = det.box;
              const w = x2 - x1;
              const h = y2 - y1;
              const isViolating = !!det.violating;
              const boxColor = isViolating ? "var(--hazard-orange)" : "var(--signal-blue)";

              return (
                <g key={det.track_id}>
                  <rect
                    x={x1}
                    y={y1}
                    width={w}
                    height={h}
                    fill="none"
                    stroke={boxColor}
                    strokeWidth={2}
                    rx={2}
                  />
                  {/* Label badge */}
                  <g transform={`translate(${x1}, ${Math.max(16, y1 - 4)})`}>
                    <rect
                      x={0}
                      y={-14}
                      width={70}
                      height={16}
                      fill={boxColor}
                      rx={2}
                    />
                    <text
                      x={4}
                      y={-2}
                      fill="#FFFFFF"
                      fontSize="11"
                      fontFamily="IBM Plex Sans, sans-serif"
                      fontWeight="600"
                    >
                      ID #{det.track_id}
                    </text>
                  </g>
                </g>
              );
            })}
          </svg>
        )}

        {/* Live Privacy Watermark */}
        <div
          style={{
            position: "absolute",
            bottom: "8px",
            right: "12px",
            background: "rgba(30, 42, 51, 0.8)",
            color: "#A0B0BC",
            padding: "2px 8px",
            borderRadius: "var(--radius-sm)",
            fontSize: "11px",
            pointerEvents: "none",
          }}
        >
          🔒 Face Blurring Active (Privacy Enforced)
        </div>
      </div>
    </div>
  );
};
