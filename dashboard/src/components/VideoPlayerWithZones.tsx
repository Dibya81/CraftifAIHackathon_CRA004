import React, { useState, useEffect, useRef } from "react";
import {
  Eye,
  EyeOff,
  Maximize,
  Minimize,
  Download,
  ShieldCheck,
  Box,
  VideoOff,
  RefreshCw,
} from "lucide-react";
import { ZoneDefinition } from "../types";

interface ActiveDetection {
  track_id: number;
  box: [number, number, number, number]; // [x1, y1, x2, y2]
  label?: string;
  violating?: boolean;
}

interface VideoPlayerWithZonesProps {
  zones: ZoneDefinition[];
  activeZoneViolations?: string[];
  activeDetections?: ActiveDetection[];
  snapshotUrl?: string;
  streamUrl?: string;
  frameWidth?: number;
  frameHeight?: number;
  fps?: number | null;
  blurredSource?: boolean;
  initialFrameLoaded?: boolean;
}

export const getZoneColor = (type: string, hasViolation: boolean): { stroke: string; fill: string } => {
  if (hasViolation) {
    return {
      stroke: "var(--danger)",
      fill: "rgba(232, 89, 12, 0.28)",
    };
  }
  switch (type) {
    case "danger":
      return {
        stroke: "var(--danger)",
        fill: "rgba(232, 89, 12, 0.14)",
      };
    case "restricted":
      return {
        stroke: "var(--warn)",
        fill: "rgba(242, 169, 0, 0.14)",
      };
    case "safe":
    default:
      return {
        stroke: "var(--info)",
        fill: "rgba(31, 111, 208, 0.10)",
      };
  }
};

export const VideoPlayerWithZones: React.FC<VideoPlayerWithZonesProps> = ({
  zones,
  activeZoneViolations = [],
  activeDetections = [],
  snapshotUrl = "/api/zones/snapshot",
  streamUrl = "/api/stream/live.mjpg",
  frameWidth = 1920,
  frameHeight = 1080,
  fps = null,
  blurredSource = false,
  initialFrameLoaded = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "live" | "no_signal" | "error">(
    initialFrameLoaded ? "live" : "connecting"
  );
  const [frameLoaded, setFrameLoaded] = useState<boolean>(initialFrameLoaded);
  const [currentStreamSrc, setCurrentStreamSrc] = useState<string>(streamUrl);
  const [showZones, setShowZones] = useState<boolean>(true);
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const isFirstMount = useRef(true);
  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    setCurrentStreamSrc(`${streamUrl}?t=${Date.now()}`);
    setStreamStatus("connecting");
    setFrameLoaded(false);
  }, [streamUrl]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  const handleRetry = () => {
    setStreamStatus("connecting");
    setFrameLoaded(false);
    setCurrentStreamSrc(`${streamUrl}?retry=${Date.now()}`);
  };

  const handleDownloadSnapshot = () => {
    const a = document.createElement("a");
    a.href = `${snapshotUrl}?download=${Date.now()}`;
    a.download = `sitesentinel-snapshot-${Date.now()}.jpg`;
    a.click();
  };

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        backgroundColor: "#10161B",
        borderRadius: "6px",
        overflow: "hidden",
        border: "1px solid var(--border)",
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
          padding: "8px 14px",
          background: "linear-gradient(to bottom, rgba(16, 22, 27, 0.9) 0%, rgba(16, 22, 27, 0) 100%)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          color: "#FFFFFF",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              display: "inline-block",
              width: "7px",
              height: "7px",
              borderRadius: "50%",
              backgroundColor:
                frameLoaded && activeZoneViolations.length > 0
                  ? "var(--danger)"
                  : frameLoaded
                  ? "var(--ok)"
                  : "var(--text-muted)",
            }}
          />
          <span
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "14px",
              letterSpacing: "0.2px",
              fontWeight: 600,
            }}
          >
            {frameLoaded ? "Live stream" : "Camera 01"}
          </span>
          <span style={{ fontSize: "11px", opacity: 0.75, fontFamily: "var(--font-mono)" }}>
            {fps != null && frameLoaded ? `(${Math.round(fps)} FPS)` : ""}
          </span>
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", gap: "6px" }}>
          <button
            onClick={() => setShowBoxes(!showBoxes)}
            title={showBoxes ? "Hide bounding boxes" : "Show bounding boxes"}
            style={{
              background: showBoxes ? "rgba(31, 111, 208, 0.5)" : "rgba(255, 255, 255, 0.12)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              color: "#FFFFFF",
              fontSize: "11px",
              padding: "3px 8px",
              borderRadius: "4px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <Box size={12} />
            <span>Boxes</span>
          </button>

          <button
            onClick={() => setShowZones(!showZones)}
            title={showZones ? "Hide zone overlays" : "Show zone overlays"}
            style={{
              background: showZones ? "rgba(31, 111, 208, 0.5)" : "rgba(255, 255, 255, 0.12)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              color: "#FFFFFF",
              fontSize: "11px",
              padding: "3px 8px",
              borderRadius: "4px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            {showZones ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>Zones</span>
          </button>

          <button
            onClick={handleDownloadSnapshot}
            title="Download frame snapshot"
            style={{
              background: "rgba(255, 255, 255, 0.12)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              color: "#FFFFFF",
              padding: "3px 8px",
              borderRadius: "4px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
            }}
          >
            <Download size={12} />
          </button>

          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit fullscreen" : "Toggle fullscreen"}
            style={{
              background: "rgba(255, 255, 255, 0.12)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              color: "#FFFFFF",
              padding: "3px 8px",
              borderRadius: "4px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
            }}
          >
            {isFullscreen ? <Minimize size={12} /> : <Maximize size={12} />}
          </button>
        </div>
      </div>

      {/* Video Viewport (16:9 Aspect Ratio) */}
      <div
        style={{
          position: "relative",
          width: "100%",
          paddingTop: "56.25%",
          backgroundColor: "#10161B",
          overflow: "hidden",
        }}
      >
        {/* Continuous Stream Image */}
        <img
          src={currentStreamSrc}
          alt=""
          role="presentation"
          onLoad={() => {
            setFrameLoaded(true);
            setStreamStatus("live");
          }}
          onError={() => {
            setFrameLoaded(false);
            setStreamStatus("no_signal");
          }}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            objectFit: "contain",
            display: streamStatus === "live" ? "block" : "none",
          }}
        />

        {/* Connecting State: Calm skeleton */}
        {streamStatus === "connecting" && (
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
              backgroundColor: "#10161B",
              color: "var(--text-muted)",
              gap: "8px",
            }}
          >
            <RefreshCw size={22} style={{ animation: "spin 1.5s linear infinite", opacity: 0.7 }} />
            <span style={{ fontSize: "12px", fontFamily: "var(--font-mono)" }}>Connecting to video feed...</span>
          </div>
        )}

        {/* No Signal State: Plain message, actionable next steps, zero broken icons */}
        {(streamStatus === "no_signal" || streamStatus === "error") && (
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
              backgroundColor: "#10161B",
              color: "#C5D0D8",
              padding: "24px",
              textAlign: "center",
              gap: "8px",
            }}
          >
            <VideoOff size={30} style={{ color: "#788896", marginBottom: "4px" }} />
            <span style={{ fontSize: "14px", fontWeight: 600, color: "#F0F4F8" }}>No video signal received</span>
            <p style={{ fontSize: "12px", color: "#8E9EAA", maxWidth: "420px", margin: "0 0 10px 0", lineHeight: 1.5 }}>
              The camera pipeline is not currently sending frames to the relay. To start the live simulation stream:
            </p>
            <code
              style={{
                backgroundColor: "rgba(255, 255, 255, 0.06)",
                padding: "6px 12px",
                borderRadius: "4px",
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                color: "var(--info-strong)",
                marginBottom: "12px",
                border: "1px solid rgba(255, 255, 255, 0.1)",
              }}
            >
              ./scripts/run_demo.sh --sim
            </code>
            <button
              onClick={handleRetry}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "5px 12px",
                backgroundColor: "rgba(255, 255, 255, 0.1)",
                border: "1px solid rgba(255, 255, 255, 0.2)",
                color: "#FFFFFF",
                borderRadius: "4px",
                fontSize: "11px",
                cursor: "pointer",
              }}
            >
              <RefreshCw size={11} />
              <span>Retry stream</span>
            </button>
          </div>
        )}

        {/* SVG Zone & Detection Overlay Layer: DRAWN ONLY WHEN FRAME IS PRESENT */}
        {frameLoaded && showZones && (
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
                    strokeWidth={hasViolation ? 3 : 2}
                    fill={fill}
                    strokeDasharray={zone.type === "restricted" ? "8 4" : undefined}
                    className={hasViolation ? "animate-alert-pulse" : undefined}
                  />
                  {/* Plain Zone Tag: text only, no decorative icons */}
                  <g transform={`translate(${minX + 8}, ${minY + 20})`}>
                    <rect
                      x={0}
                      y={-14}
                      width={zone.id.length * 8 + 48}
                      height={18}
                      rx={2}
                      fill="rgba(16, 22, 27, 0.85)"
                      stroke={stroke}
                      strokeWidth={1}
                    />
                    <text
                      x={6}
                      y={-2}
                      fill="#FFFFFF"
                      fontSize="10"
                      fontFamily="IBM Plex Sans, sans-serif"
                      fontWeight="600"
                    >
                      {zone.id} [{zone.type}]
                    </text>
                  </g>
                </g>
              );
            })}

            {/* Tracked Detection Bounding Boxes */}
            {showBoxes &&
              activeDetections.map((det) => {
                const [x1, y1, x2, y2] = det.box;
                const w = x2 - x1;
                const h = y2 - y1;
                const isViolating = !!det.violating;
                const boxColor = isViolating ? "var(--danger)" : "var(--info)";

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
                    <g transform={`translate(${x1}, ${Math.max(16, y1 - 4)})`}>
                      <rect
                        x={0}
                        y={-14}
                        width={58}
                        height={16}
                        fill={boxColor}
                        rx={2}
                      />
                      <text
                        x={4}
                        y={-2}
                        fill="#FFFFFF"
                        fontSize="10"
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

        {/* Live Privacy Watermark: ONLY shown when confirmed by backend AND frame is loaded */}
        {frameLoaded && blurredSource && (
          <div
            style={{
              position: "absolute",
              bottom: "8px",
              right: "12px",
              background: "rgba(16, 22, 27, 0.85)",
              color: "#A0B0BC",
              padding: "2px 8px",
              borderRadius: "4px",
              fontSize: "11px",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              pointerEvents: "none",
              border: "1px solid rgba(255, 255, 255, 0.12)",
            }}
          >
            <ShieldCheck size={12} style={{ color: "var(--ok)" }} />
            <span>Face Blurring Enforced</span>
          </div>
        )}
      </div>
    </div>
  );
};
