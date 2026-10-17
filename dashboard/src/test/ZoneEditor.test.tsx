import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ZoneEditor } from "../components/ZoneEditor";
import { ZonesConfig } from "../types";

describe("ZoneEditor Component", () => {
  const mockConfig: ZonesConfig = {
    frame: { width: 1920, height: 1080 },
    zones: [
      {
        id: "press-area",
        type: "restricted",
        required_ppe: ["helmet"],
        polygon: [
          [100, 100],
          [500, 100],
          [500, 500],
          [100, 500],
        ],
      },
    ],
  };

  it("renders existing zones list", () => {
    render(
      <ZoneEditor
        initialConfig={mockConfig}
        onSaveConfig={vi.fn().mockResolvedValue(true)}
      />
    );

    expect(screen.getAllByText("press-area").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/restricted · PPE: helmet/)).toBeInTheDocument();
  });

  it("switches to drawing mode on draw new zone button click", () => {
    render(
      <ZoneEditor
        initialConfig={mockConfig}
        onSaveConfig={vi.fn().mockResolvedValue(true)}
      />
    );

    const drawBtn = screen.getByText("+ Draw new zone");
    fireEvent.click(drawBtn);

    expect(screen.getByText(/DRAWING NEW ZONE/i)).toBeInTheDocument();
    expect(screen.getByText("Save zone")).toBeInTheDocument();
  });
});
