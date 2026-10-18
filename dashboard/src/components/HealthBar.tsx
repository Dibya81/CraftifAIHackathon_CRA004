import React, { useState, useEffect, useRef } from "react";
import {
  Shield,
  Activity,
  Cpu,
  Radio,
  Video,
  VideoOff,
  Sun,
  Moon,
  Maximize2,
  Minimize2,
  Command,
  WifiOff,
  CheckCircle2,
  AlertCircle,
  XCircle,
  ChevronDown,
} from "lucide-react";
import { HealthState, ComponentHealth } from "../types";
import { StatusDot } from "../design/primitives";
import { useAppStore } from "../state/useAppStore";
import { WebSocketConnectionState } from "../api/websocket";

interface HealthBarProps {
  health: HealthState;
  activeScreen?: string;
  onSelectScreen?: (screen: string) => void;
  presentMode?: boolean;
  onTogglePresent?: () => void;
  connectionState?: WebSocketConnectionState;
}

export const HealthBar: React.FC<HealthBarProps> = ({
  health,
  activeScreen: _activeScreen,
  onSelectScreen: _onSelectScreen,
  presentMode: propPresentMode,
  onTogglePresent: propTogglePresent,
  connectionState = "connected",
}) => {
  const store = useAppStore();
  const presentMode = propPresentMode !== undefined ? propPresentMode : store.presentMode;
  const togglePresent = propTogglePresent || store.togglePresentMode;

  const [currentTime, setCurrentTime] = useState("");
  const [showComponents, setShowComponents] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  // Close component popover on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowComponents(false);
      }
    };
    if (showComponents) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showComponents]);

  const isCameraLost = health.camera !== "up" && health.camera !== "operational";
  const isMqttDown = health.mqtt !== "up" && health.mqtt !== "connected";
  const fpsNum = health.fps ?? null;
  const isDegraded = health.status === "degraded" || isMqttDown || (fpsNum !== null && fpsNum > 0 && fpsNum < 20);
  const isDown = health.status === "down" || isCameraLost;

  const statusState: "ok" | "degraded" | "down" = isDown ? "down" : isDegraded ? "degraded" : "ok";
  const statusLabel = isDown ? "Camera lost" : isDegraded ? "Degraded" : "Operational";

  const defaultComponents: ComponentHealth[] = [
    {
      name: "pipeline",
      status: !isCameraLost ? "ok" : "down",
      detail: !isCameraLost && fpsNum !== null ? `Receiving frames @ ${fpsNum.toFixed(0)} FPS` : "No frame signal received",
    },
    {
      name: "rule_engine",
      status: !isMqttDown || health.mode === "SIMULATED" ? "ok" : "idle",
      detail: !isMqttDown || health.mode === "SIMULATED" ? "Processing detections" : "Awaiting detections stream",
    },
    {
      name: "evidence_writer",
      status: "ok",
      detail: "Storage ready",
    },
    {
      name: "api",
      status: "ok",
      detail: "REST & WebSocket operational",
    },
    {
      name: "broker",
      status: !isMqttDown ? "ok" : "down",
      detail: !isMqttDown ? "Connected to broker" : "MQTT broker disconnected",
    },
  ];

  const componentsList = health.components && health.components.length > 0 ? health.components : defaultComponents;

  return (
    <>
      <header
        role="banner"
        style={{
          backgroundColor: "var(--surface)",
          borderBottom: "1px solid var(--border)",
          color: "var(--text)",
          padding: "6px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
          minHeight: "44px",
          userSelect: "none",
        }}
      >
        {/* Left: Brand, Camera, Precision, Telemetry */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Shield size={16} strokeWidth={2} style={{ color: "var(--info)" }} />
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "18px",
                fontWeight: 600,
                letterSpacing: "0.2px",
                color: "var(--text)",
              }}
            >
              SiteSentinel
            </span>
          </div>

          {/* Camera indicator */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "2px 8px",
              backgroundColor: "var(--surface-raised)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
            }}
          >
            {isCameraLost ? (
              <VideoOff size={12} strokeWidth={2} style={{ color: "var(--danger)" }} />
            ) : (
              <Video size={12} strokeWidth={2} style={{ color: "var(--ok)" }} />
            )}
            <span>{isCameraLost ? "NO SIGNAL" : "cam-01"}</span>
          </div>

          {/* Engine Precision Badge */}
          {health.engine_precision ? (
            <span
              style={{
                padding: "2px 8px",
                backgroundColor: "var(--info-subtle)",
                border: "1px solid var(--info)",
                color: "var(--info-strong)",
                borderRadius: "4px",
                fontSize: "11px",
                fontWeight: 600,
                fontFamily: "var(--font-mono)",
              }}
            >
              Engine {health.engine_precision}
            </span>
          ) : (
            <span
              title="Engine precision report unavailable"
              style={{
                padding: "2px 8px",
                backgroundColor: "var(--surface-raised)",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
                borderRadius: "4px",
                fontSize: "11px",
                fontFamily: "var(--font-mono)",
                cursor: "help",
              }}
            >
              Engine —
            </span>
          )}

          {/* Real Telemetry Numbers */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "12px",
              color: "var(--text-muted)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <Activity size={12} strokeWidth={2} />
              {fpsNum !== null ? (
                <>
                  <strong style={{ color: "var(--text)", fontWeight: 500 }}>{fpsNum.toFixed(0)}</strong> FPS
                </>
              ) : (
                <span title="Camera stream inactive" style={{ color: "var(--text-muted)", cursor: "help" }}>
                  — FPS
                </span>
              )}
            </span>

            <span>&middot;</span>

            <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
              {health.latency_ms != null ? (
                <>
                  <strong style={{ color: "var(--text)", fontWeight: 500 }}>{health.latency_ms.toFixed(1)}</strong> ms
                </>
              ) : (
                <span title="Pipeline latency unavailable" style={{ color: "var(--text-muted)", cursor: "help" }}>
                  — ms
                </span>
              )}
            </span>

            <span>&middot;</span>

            <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <Cpu size={12} strokeWidth={2} />
              {health.gpu_util != null ? (
                <span>
                  GPU {health.gpu_util}% {health.gpu_power_w != null && `(${health.gpu_power_w.toFixed(1)}W)`}
                </span>
              ) : (
                <span title="GPU metrics require NVIDIA GPU with nvidia-smi" style={{ color: "var(--text-muted)", cursor: "help" }}>
                  GPU —
                </span>
              )}
            </span>

            <span>&middot;</span>

            <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <Radio size={12} strokeWidth={2} style={{ color: isMqttDown ? "var(--warn)" : "var(--ok)" }} />
              <span>MQTT {isMqttDown ? "offline" : "ok"}</span>
            </span>
          </div>
        </div>

        {/* Right: Expandable Component Health Dot, Clock, Theme, Present */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", position: "relative" }}>
          {connectionState === "reconnecting" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: "2px 6px",
                backgroundColor: "var(--warn-subtle)",
                border: "1px solid var(--warn)",
                color: "var(--warn-strong)",
                borderRadius: "4px",
                fontSize: "11px",
              }}
            >
              <WifiOff size={11} strokeWidth={2} />
              <span>Reconnecting...</span>
            </span>
          )}

          {/* Clickable Status Dot with Component List Expansion */}
          <div ref={dropdownRef} style={{ position: "relative" }}>
            <button
              data-testid="health-status-dropdown-btn"
              onClick={() => setShowComponents(!showComponents)}
              aria-expanded={showComponents}
              aria-haspopup="true"
              title="Click to view component heartbeats and health details"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "3px 8px",
                backgroundColor: "var(--surface-raised)",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                cursor: "pointer",
                color: "var(--text)",
                fontSize: "11px",
                fontWeight: 500,
              }}
            >
              <StatusDot status={statusState} />
              <span>{statusLabel}</span>
              <ChevronDown size={11} strokeWidth={2} style={{ opacity: 0.7 }} />
            </button>

            {/* Component list dropdown popover */}
            {showComponents && (
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  right: 0,
                  marginTop: "6px",
                  width: "280px",
                  backgroundColor: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.25)",
                  zIndex: 100,
                  padding: "10px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderBottom: "1px solid var(--border)",
                    paddingBottom: "6px",
                    marginBottom: "8px",
                    fontSize: "11px",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                    color: "var(--text-muted)",
                  }}
                >
                  <span>System Components</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px" }}>{health.uptime_s}s uptime</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {componentsList.map((comp) => {
                    const isCompOk = comp.status === "ok";
                    const isCompDegraded = comp.status === "degraded" || comp.status === "idle";
                    return (
                      <div
                        key={comp.name}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: "8px",
                          padding: "6px 8px",
                          backgroundColor: "var(--surface-raised)",
                          borderRadius: "4px",
                          fontSize: "11px",
                        }}
                      >
                        <div style={{ marginTop: "2px" }}>
                          {isCompOk ? (
                            <CheckCircle2 size={13} style={{ color: "var(--ok)" }} />
                          ) : isCompDegraded ? (
                            <AlertCircle size={13} style={{ color: "var(--warn)" }} />
                          ) : (
                            <XCircle size={13} style={{ color: "var(--danger)" }} />
                          )}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <strong style={{ color: "var(--text)", textTransform: "capitalize" }}>
                              {comp.name.replace(/_/g, " ")}
                            </strong>
                            <span
                              style={{
                                fontSize: "10px",
                                fontFamily: "var(--font-mono)",
                                color: isCompOk ? "var(--ok)" : isCompDegraded ? "var(--warn)" : "var(--danger)",
                              }}
                            >
                              {comp.status}
                            </span>
                          </div>
                          {comp.detail && (
                            <div style={{ color: "var(--text-muted)", fontSize: "10px", marginTop: "2px" }}>
                              {comp.detail}
                            </div>
                          )}
                          {comp.last_heartbeat && (
                            <div
                              style={{
                                color: "var(--text-muted)",
                                fontSize: "9px",
                                fontFamily: "var(--font-mono)",
                                marginTop: "2px",
                                opacity: 0.8,
                              }}
                            >
                              hb: {comp.last_heartbeat.slice(11, 19)}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--text-muted)",
              letterSpacing: "0.5px",
            }}
          >
            {currentTime}
          </span>

          {/* Command Palette Button */}
          <button
            onClick={store.toggleCommandPalette}
            title="Command Palette (Cmd+K)"
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              color: "var(--text-muted)",
              padding: "3px 6px",
              display: "inline-flex",
              alignItems: "center",
              gap: "3px",
              cursor: "pointer",
              fontSize: "11px",
            }}
          >
            <Command size={11} strokeWidth={2} />
            <span style={{ fontFamily: "var(--font-mono)" }}>K</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={store.toggleTheme}
            title={`Switch to ${store.theme === "light" ? "dark (control room)" : "light"} theme`}
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              color: "var(--text)",
              padding: "4px 6px",
              display: "inline-flex",
              alignItems: "center",
              cursor: "pointer",
            }}
          >
            {store.theme === "light" ? <Moon size={13} strokeWidth={2} /> : <Sun size={13} strokeWidth={2} />}
          </button>

          {/* Present Mode Toggle */}
          <button
            onClick={togglePresent}
            title="Present Mode (P)"
            style={{
              background: presentMode ? "var(--info)" : "var(--surface-raised)",
              color: presentMode ? "#FFFFFF" : "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              padding: "3px 8px",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: 500,
            }}
          >
            {presentMode ? <Minimize2 size={11} strokeWidth={2} /> : <Maximize2 size={11} strokeWidth={2} />}
            <span>Present</span>
          </button>
        </div>
      </header>

      {/* Down State Alert Banner */}
      {isDown && (
        <div
          role="alert"
          style={{
            backgroundColor: "var(--danger)",
            color: "#FFFFFF",
            padding: "6px 16px",
            fontSize: "12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <VideoOff size={14} strokeWidth={2} />
            <span>
              <strong>Camera signal lost.</strong> No frame data is reaching the pipeline. Check camera or simulator.
            </span>
          </div>
          <span style={{ fontSize: "11px", opacity: 0.9 }}>Auto-reconnecting...</span>
        </div>
      )}
    </>
  );
};
