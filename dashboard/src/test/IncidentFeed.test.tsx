import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { IncidentFeed, formatIncidentName } from "../components/IncidentFeed";
import { Incident } from "../types";

describe("IncidentFeed Component", () => {
  it("formats incident names according to design guidelines", () => {
    expect(formatIncidentName("NO_HELMET")).toBe("No helmet");
    expect(formatIncidentName("NO_VEST")).toBe("No vest");
    expect(formatIncidentName("ZONE_INTRUSION")).toBe("Zone entry");
    expect(formatIncidentName("DANGER_DWELL")).toBe("Danger-zone dwell");
  });

  it("shows empty state when no incidents exist", () => {
    render(
      <IncidentFeed
        incidents={[]}
        selectedIncidentId={null}
        onSelectIncident={vi.fn()}
      />
    );

    expect(
      screen.getByText("No incidents in the last 24 hours.")
    ).toBeInTheDocument();
  });

  it("renders incidents and handles selection click", () => {
    const mockIncidents: Incident[] = [
      {
        incident_id: "inc-101",
        timestamp: new Date().toISOString(),
        camera_id: "cam-01",
        type: "NO_HELMET",
        severity: "HIGH",
        track_id: 42,
        zone: "press-area",
        confidence: 0.95,
        duration_s: 3.4,
        evidence_clip: "evidence/inc-101.mp4",
        status: "open",
      },
    ];

    const onSelect = vi.fn();
    render(
      <IncidentFeed
        incidents={mockIncidents}
        selectedIncidentId={null}
        onSelectIncident={onSelect}
      />
    );

    expect(screen.getByText("No helmet")).toBeInTheDocument();
    expect(screen.getByText(/press-area/)).toBeInTheDocument();
    expect(screen.getAllByText("HIGH").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/3\.4s/)).toBeInTheDocument();

    const row = screen.getByRole("listitem");
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith(mockIncidents[0]);
  });
});
