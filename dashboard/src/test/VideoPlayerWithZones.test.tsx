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
    expect(safeColors.stroke).toBe("var(--signal-blue)");

    const dangerColors = getZoneColor("danger", false);
    expect(dangerColors.stroke).toBe("var(--hazard-orange)");

    const violationColors = getZoneColor("safe", true);
    expect(violationColors.stroke).toBe("var(--hazard-orange)");
    expect(violationColors.fill).toContain("rgba(232, 89, 12");
  });

  it("renders SVG overlays and zone polygons", () => {
    render(
      <VideoPlayerWithZones
        zones={mockZones}
        activeZoneViolations={["danger-crane"]}
        fps={30}
      />
    );

    expect(screen.getByTestId("zones-svg-overlay")).toBeInTheDocument();
    expect(screen.getByTestId("zone-polygon-safe-path")).toBeInTheDocument();
    expect(screen.getByTestId("zone-polygon-danger-crane")).toBeInTheDocument();

    // Toggle button works
    const toggleBtn = screen.getByText("Hide zones");
    fireEvent.click(toggleBtn);
    expect(screen.queryByTestId("zones-svg-overlay")).not.toBeInTheDocument();
  });
});
