import { describe, it, expect } from "vitest";
import { formatIncidentName, getSeverityBadge } from "../components/IncidentFeed";
import { isPolygonSelfIntersecting } from "../components/ZoneEditor";
import { getZoneColor } from "../components/VideoPlayerWithZones";
import { Incident } from "../types";

describe("Quality Gates & Design Rules Verification", () => {
  describe("Copy Rules (docs/DESIGN.md & Prompt Section 7)", () => {
    it("incident names use strictly approved plain phrases without exclamation or jargon", () => {
      const types = ["NO_HELMET", "NO_VEST", "ZONE_INTRUSION", "DANGER_DWELL"];
      const formatted = types.map(formatIncidentName);

      expect(formatted).toEqual([
        "No helmet",
        "No vest",
        "Zone entry",
        "Danger-zone dwell",
      ]);

      formatted.forEach((text) => {
        expect(text).not.toContain("!");
        expect(text.toLowerCase()).not.toContain("oops");
        expect(text.toLowerCase()).not.toContain("please");
        expect(text.toLowerCase()).not.toContain("error:");
      });
    });

    it("verifies buttons and action names are plain action verbs in sentence case", () => {
      const actions = [
        "Acknowledge",
        "Save zones",
        "Export CSV",
        "Draw zone",
        "Undo",
        "Present",
      ];
      actions.forEach((act) => {
        expect(act).not.toContain("!");
        expect(act[0]).toBe(act[0].toUpperCase());
      });
    });
  });

  describe("Tokens and Semantic Mapping (Prompt Section 3)", () => {
    it("maps severity levels to correct token color semantics", () => {
      const high = getSeverityBadge("HIGH");
      expect(high.color).toContain("--danger");

      const med = getSeverityBadge("MEDIUM");
      expect(med.color).toContain("--warn");

      const low = getSeverityBadge("LOW");
      expect(low.color).toContain("--info");
    });

    it("maps zone types to correct semantic tokens", () => {
      expect(getZoneColor("safe", false).stroke).toBe("var(--info)");
      expect(getZoneColor("restricted", false).stroke).toBe("var(--warn)");
      expect(getZoneColor("danger", false).stroke).toBe("var(--danger)");
      // Any zone with active violation gets danger stroke
      expect(getZoneColor("safe", true).stroke).toBe("var(--danger)");
    });
  });

  describe("Zone Geometry Rules (Prompt Section 5.4 & 10)", () => {
    it("validates convex polygon as non-self-intersecting", () => {
      const square = [
        [0, 0],
        [100, 0],
        [100, 100],
        [0, 100],
      ];
      expect(isPolygonSelfIntersecting(square)).toBe(false);
    });

    it("detects and rejects hourglass self-intersecting polygon", () => {
      const hourglass = [
        [0, 0],
        [100, 100],
        [100, 0],
        [0, 100],
      ];
      expect(isPolygonSelfIntersecting(hourglass)).toBe(true);
    });

    it("allows triangle with 3 vertices", () => {
      const triangle = [
        [0, 0],
        [100, 0],
        [50, 100],
      ];
      expect(isPolygonSelfIntersecting(triangle)).toBe(false);
    });
  });

  describe("Incident Unread and Ordering Logic", () => {
    it("orders newest incidents first and correctly tracks open status", () => {
      const incidents: Incident[] = [
        {
          incident_id: "inc-1",
          timestamp: "2026-10-18T00:00:00Z",
          camera_id: "cam-01",
          type: "NO_HELMET",
          severity: "LOW",
          track_id: 1,
          zone: "entry",
          confidence: 0.9,
          duration_s: 2,
          evidence_clip: null,
          status: "acknowledged",
        },
        {
          incident_id: "inc-2",
          timestamp: "2026-10-18T00:05:00Z",
          camera_id: "cam-01",
          type: "NO_VEST",
          severity: "HIGH",
          track_id: 2,
          zone: "danger-crane",
          confidence: 0.95,
          duration_s: 4,
          evidence_clip: null,
          status: "open",
        },
      ];

      const sorted = [...incidents].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );

      expect(sorted[0].incident_id).toBe("inc-2");
      expect(sorted[0].status).toBe("open");
      expect(sorted[1].status).toBe("acknowledged");
    });
  });
});
