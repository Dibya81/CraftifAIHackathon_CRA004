import React from "react";
import { HealthState } from "../types";

interface HealthBarProps {
  health: HealthState;
  activeScreen: string;
  onSelectScreen: (screen: string) => void;
  presentMode: boolean;
  onTogglePresent: () => void;
}

export const HealthBar: React.FC<HealthBarProps> = ({
  health,
  activeScreen,
  onSelectScreen,
  presentMode,
  onTogglePresent,
}) => {
  const isDegraded = health.status === "degraded" || health.fps < 20;
  const isCameraLost = health.camera !== "up";

  let statusBg = "var(--clear-green)";
  let statusText = "System healthy";
  if (isCameraLost) {
    statusBg = "var(--hazard-orange)";
    statusText = "Camera lost";
  } else if (isDegraded) {
    statusBg = "var(--caution-amber)";
    statusText = "Degraded";
  }

  return (
    <header
      role="banner"
      style={{
        backgroundColor: "var(--steel-900)",
        color: "var(--white)",
        padding: "10px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid var(--steel-800)",
        flexWrap: "wrap",
        gap: "12px",
      }}
    >
      {/* Brand & Camera Info */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "20px" }}>🛡️</span>
          <span style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, letterSpacing: "1px" }}>
            SiteSentinel
          </span>
        </div>

        <span
          style={{
            background: "rgba(255,255,255,0.12)",
            padding: "3px 8px",
            borderRadius: "var(--radius-sm)",
            fontSize: "12px",
            fontFamily: "monospace",
          }}
        >
          {health.camera === "up" ? "cam-01" : "CAMERA DISCONNECTED"}
        </span>

        {/* Engine Precision Tag */}
        <span
          style={{
            background: "rgba(31, 111, 208, 0.3)",
            border: "1px solid var(--signal-blue)",
            color: "#A4D2FF",
            padding: "3px 8px",
            borderRadius: "var(--radius-sm)",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          Engine {health.engine_precision || "INT8"}
        </span>

        {/* FPS & Latency */}
        <span style={{ fontSize: "13px", color: "var(--concrete-100)" }}>
          {health.fps.toFixed(0)} FPS &middot; {health.latency_ms.toFixed(1)} ms
        </span>
      </div>

      {/* Screen Navigation */}
      {!presentMode && (
        <nav aria-label="Main Navigation" style={{ display: "flex", gap: "6px" }}>
          {[
            { id: "live", label: "Live view" },
            { id: "zones", label: "Zone editor" },
            { id: "reports", label: "Reports" },
            { id: "system", label: "System" },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => onSelectScreen(item.id)}
              style={{
                background: activeScreen === item.id ? "rgba(255,255,255,0.18)" : "transparent",
                border: "none",
                color: activeScreen === item.id ? "var(--white)" : "var(--concrete-100)",
                padding: "6px 14px",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                fontWeight: activeScreen === item.id ? 600 : 400,
                fontSize: "13px",
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
      )}

      {/* Right controls: System Health Pill + Present Mode Toggle */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {/* Health pill */}
        <div
          data-testid="health-pill"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "4px 10px",
            borderRadius: "12px",
            backgroundColor: statusBg,
            color: "var(--white)",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#FFF" }} />
          <span>{statusText}</span>
        </div>

        {/* Present mode toggle */}
        <button
          onClick={onTogglePresent}
          style={{
            background: presentMode ? "var(--hazard-orange)" : "rgba(255,255,255,0.12)",
            border: "1px solid rgba(255,255,255,0.2)",
            color: "var(--white)",
            padding: "5px 12px",
            borderRadius: "var(--radius-sm)",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          {presentMode ? "Exit present" : "Present mode"}
        </button>
      </div>

      {/* Warning banner if camera lost */}
      {isCameraLost && (
        <div
          role="alert"
          style={{
            width: "100%",
            backgroundColor: "var(--hazard-orange)",
            color: "var(--white)",
            padding: "6px 12px",
            marginTop: "6px",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          Camera lost. Check the USB cable or the RTSP address in config/sentinel.yaml.
        </div>
      )}
    </header>
  );
};
