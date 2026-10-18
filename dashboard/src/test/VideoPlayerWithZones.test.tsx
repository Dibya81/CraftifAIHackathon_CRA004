import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VideoPlayerWithZones, getZoneColor } from "../components/VideoPlayerWithZones";
import { ZoneDefinition } from "../types";

describe("VideoPlayerWithZones Component", () => {
  const mockZones: ZoneDefinition[] = [
    {
      id: "safe-path",
      type: "safe",
      required_ppe: [],
      polygon: [
        [0, 0],
        [100, 0],
        [100, 100],
        [0, 100],
      ],
    },
    {
      id: "danger-crane",
      type: "danger",
      required_ppe: ["helmet"],
      polygon: [
        [200, 200],
        [400, 200],
        [400, 400],
        [200, 400],
      ],
    },
  ];

  it("calculates correct zone colors including active violation highlight", () => {
    const safeColors = getZoneColor("safe", false);
    expect(safeColors.stroke).toBe("var(--info)");

    const dangerColors = getZoneColor("danger", false);
    expect(dangerColors.stroke).toBe("var(--danger)");

    const violationColors = getZoneColor("safe", true);
    expect(violationColors.stroke).toBe("var(--danger)");
    expect(violationColors.fill).toContain("rgba(232, 89, 12");
  });

  it("does not draw zone overlays when no frame is present", () => {
    render(
      <VideoPlayerWithZones
        zones={mockZones}
        activeZoneViolations={["danger-crane"]}
        initialFrameLoaded={false}
      />
    );

    // Overlays must not be drawn until a frame is loaded
    expect(screen.queryByTestId("zones-svg-overlay")).not.toBeInTheDocument();
  });

  it("renders SVG overlays and zone polygons when frame is loaded", () => {
    render(
      <VideoPlayerWithZones
        zones={mockZones}
        activeZoneViolations={["danger-crane"]}
        fps={30}
        initialFrameLoaded={true}
      />
    );

    expect(screen.getByTestId("zones-svg-overlay")).toBeInTheDocument();
    expect(screen.getByTestId("zone-polygon-safe-path")).toBeInTheDocument();
    expect(screen.getByTestId("zone-polygon-danger-crane")).toBeInTheDocument();

    // Toggle button works
    const toggleBtn = screen.getByTitle("Hide zone overlays");
    fireEvent.click(toggleBtn);
    expect(screen.queryByTestId("zones-svg-overlay")).not.toBeInTheDocument();
  });

  it("shows privacy badge only when blurredSource is confirmed and frame is loaded", () => {
    const { rerender } = render(
      <VideoPlayerWithZones
        zones={mockZones}
        initialFrameLoaded={true}
        blurredSource={false}
      />
    );
    expect(screen.queryByText(/Face Blurring Enforced/i)).not.toBeInTheDocument();

    rerender(
      <VideoPlayerWithZones
        zones={mockZones}
        initialFrameLoaded={true}
        blurredSource={true}
      />
    );
    expect(screen.getByText(/Face Blurring Enforced/i)).toBeInTheDocument();
  });
});
