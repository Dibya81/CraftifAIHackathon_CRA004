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
  };

  it("renders healthy system state and engine precision", () => {
    const onSelect = vi.fn();
    const onTogglePresent = vi.fn();

    render(
      <HealthBar
        health={mockHealthy}
        activeScreen="live"
        onSelectScreen={onSelect}
        presentMode={false}
        onTogglePresent={onTogglePresent}
      />
    );

    expect(screen.getByText("SiteSentinel")).toBeInTheDocument();
    expect(screen.getByText("Engine INT8")).toBeInTheDocument();
    expect(screen.getByText("System healthy")).toBeInTheDocument();
    expect(screen.getByText(/31 FPS/)).toBeInTheDocument();
  });

  it("displays camera lost warning banner when camera is down", () => {
    const mockCameraDown: HealthState = {
      ...mockHealthy,
      camera: "down",
      status: "degraded",
    };

    render(
      <HealthBar
        health={mockCameraDown}
        activeScreen="live"
        onSelectScreen={vi.fn()}
        presentMode={false}
        onTogglePresent={vi.fn()}
      />
    );

    expect(screen.getByText("Camera lost")).toBeInTheDocument();
    expect(
      screen.getByText(/Camera lost\. Check the USB cable or the RTSP address/i)
    ).toBeInTheDocument();
  });

  it("allows switching screens via navigation buttons", () => {
    const onSelect = vi.fn();

    render(
      <HealthBar
        health={mockHealthy}
        activeScreen="live"
        onSelectScreen={onSelect}
        presentMode={false}
        onTogglePresent={vi.fn()}
      />
    );

    const zonesBtn = screen.getByText("Zone editor");
    fireEvent.click(zonesBtn);
    expect(onSelect).toHaveBeenCalledWith("zones");
  });

  it("toggles present mode when clicked", () => {
    const onToggle = vi.fn();

    render(
      <HealthBar
        health={mockHealthy}
        activeScreen="live"
        onSelectScreen={vi.fn()}
        presentMode={false}
        onTogglePresent={onToggle}
      />
    );

    const presentBtn = screen.getByText("Present mode");
    fireEvent.click(presentBtn);
    expect(onToggle).toHaveBeenCalled();
  });
});
