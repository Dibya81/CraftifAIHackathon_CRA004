import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HealthBar } from "../components/HealthBar";
import { HealthState } from "../types";

describe("HealthBar Component", () => {
  const mockHealthy: HealthState = {
    status: "ok",
    uptime_s: 3600,
    camera: "up",
    mqtt: "up",
    engine_precision: "INT8",
    fps: 31.4,
    latency_ms: 32.1,
    gpu_util: 65,
    gpu_power_w: 12.3,
    components: [
      { name: "pipeline", status: "ok", detail: "Active stream" },
      { name: "rule_engine", status: "ok", detail: "Active rules" },
      { name: "evidence_writer", status: "ok", detail: "Ring buffer operational" },
      { name: "api", status: "ok", detail: "REST & WS healthy" },
      { name: "broker", status: "ok", detail: "MQTT connected" },
    ],
  };

  it("renders status dot and engine precision when confirmed by payload", () => {
    render(
      <HealthBar
        health={mockHealthy}
        activeScreen="live"
        onSelectScreen={vi.fn()}
        presentMode={false}
        onTogglePresent={vi.fn()}
      />
    );

    expect(screen.getByText("SiteSentinel")).toBeInTheDocument();
    expect(screen.getByText("Engine INT8")).toBeInTheDocument();
    // System operational pill must NOT exist
    expect(screen.queryByText("System operational")).not.toBeInTheDocument();
    expect(screen.getByText(/31/)).toBeInTheDocument();
  });

  it("renders em-dash '—' when metrics are unavailable and never fabricates numbers", () => {
    const emptyHealth: HealthState = {
      status: "degraded",
      uptime_s: 0,
      camera: "down",
      mqtt: "down",
      fps: null,
      latency_ms: null,
      engine_precision: null,
      gpu_util: null,
      gpu_power_w: null,
    };

    render(
      <HealthBar
        health={emptyHealth}
        activeScreen="live"
        onSelectScreen={vi.fn()}
        presentMode={false}
        onTogglePresent={vi.fn()}
      />
    );

    // Em-dashes rendered for missing values
    expect(screen.getByText(/— FPS/)).toBeInTheDocument();
    expect(screen.getByText(/— ms/)).toBeInTheDocument();
    expect(screen.getByText(/GPU —/)).toBeInTheDocument();
    expect(screen.getByText(/Engine —/)).toBeInTheDocument();
    // Engine precision chip must not appear when engine_precision is null
    expect(screen.queryByText("Engine INT8")).not.toBeInTheDocument();
  });

  it("expands component list on status dot click and displays heartbeats", () => {
    render(
      <HealthBar
        health={mockHealthy}
        activeScreen="live"
        onSelectScreen={vi.fn()}
        presentMode={false}
        onTogglePresent={vi.fn()}
      />
    );

    const toggleBtn = screen.getByTestId("health-status-dropdown-btn");
    expect(toggleBtn).toBeInTheDocument();

    // Click to expand
    fireEvent.click(toggleBtn);

    expect(screen.getByText("System Components")).toBeInTheDocument();
    expect(screen.getByText("pipeline")).toBeInTheDocument();
    expect(screen.getByText("rule engine")).toBeInTheDocument();
    expect(screen.getByText("broker")).toBeInTheDocument();
  });

  it("derives status correctly from degraded or down payloads", () => {
    const degradedHealth: HealthState = {
      ...mockHealthy,
      status: "degraded",
      camera: "down",
    };

    render(
      <HealthBar
        health={degradedHealth}
        activeScreen="live"
        onSelectScreen={vi.fn()}
        presentMode={false}
        onTogglePresent={vi.fn()}
      />
    );

    expect(screen.getByText("NO SIGNAL")).toBeInTheDocument();
  });
});
