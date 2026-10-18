import { Incident, HealthResponse, ZonesResponse, StatsResponse } from "./schema";

export type MockScenario = "calm" | "busy_shift" | "camera_lost" | "mqtt_down" | "many_incidents";

export const MOCK_ZONES: ZonesResponse = {
  frame: { width: 1920, height: 1080 },
  version: 1,
  zones: [
    {
      id: "walkway",
      type: "safe",
      required_ppe: ["helmet"],
      polygon: [
        [150, 600],
        [950, 600],
        [950, 1020],
        [150, 1020],
      ],
    },
    {
      id: "press-area",
      type: "restricted",
      required_ppe: ["helmet", "vest"],
      polygon: [
        [1000, 450],
        [1550, 450],
        [1550, 950],
        [1000, 950],
      ],
    },
    {
      id: "crane-drop",
      type: "danger",
      required_ppe: ["helmet", "vest"],
      polygon: [
        [1400, 150],
        [1880, 150],
        [1880, 650],
        [1400, 650],
      ],
    },
  ],
};

export const INITIAL_MOCK_INCIDENTS: Incident[] = [
  {
    incident_id: "06a02ee1-9cc3-4ac1-ad47-a061012a2c9d",
    timestamp: new Date(Date.now() - 45 * 1000).toISOString(),
    camera_id: "cam-01",
    type: "NO_HELMET",
    severity: "MEDIUM",
    track_id: 2,
    zone: "walkway",
    confidence: 0.92,
    duration_s: 2.4,
    evidence_clip: "/evidence/sample/sample_incident.mp4",
    schema_version: "1.0",
    status: "open",
    notes: [],
    evidence_status: "ready",
  },
  {
    incident_id: "06a02ee1-9cc3-4ac1-ad47-a061012a2c9e",
    timestamp: new Date(Date.now() - 140 * 1000).toISOString(),
    camera_id: "cam-01",
    type: "ZONE_INTRUSION",
    severity: "HIGH",
    track_id: 4,
    zone: "press-area",
    confidence: 0.96,
    duration_s: 0.0,
    evidence_clip: "/evidence/sample/sample_incident.mp4",
    schema_version: "1.0",
    status: "open",
    notes: [],
    evidence_status: "ready",
  },
  {
    incident_id: "06a02ee1-9cc3-4ac1-ad47-a061012a2c9f",
    timestamp: new Date(Date.now() - 650 * 1000).toISOString(),
    camera_id: "cam-01",
    type: "DANGER_DWELL",
    severity: "HIGH",
    track_id: 7,
    zone: "crane-drop",
    confidence: 0.94,
    duration_s: 5.8,
    evidence_clip: null,
    schema_version: "1.0",
    status: "acknowledged",
    acked_at: new Date(Date.now() - 500 * 1000).toISOString(),
    acked_by: "safety-officer",
    notes: [
      {
        author: "safety-officer",
        note: "Worker guided back to pedestrian walkway.",
        created_at: new Date(Date.now() - 490 * 1000).toISOString(),
      },
    ],
    evidence_status: "pending",
  },
  {
    incident_id: "06a02ee1-9cc3-4ac1-ad47-a061012a2ca0",
    timestamp: new Date(Date.now() - 1800 * 1000).toISOString(),
    camera_id: "cam-01",
    type: "NO_VEST",
    severity: "LOW",
    track_id: 11,
    zone: "walkway",
    confidence: 0.88,
    duration_s: 3.1,
    evidence_clip: null,
    schema_version: "1.0",
    status: "acknowledged",
    acked_at: new Date(Date.now() - 1700 * 1000).toISOString(),
    acked_by: "supervisor",
    notes: [],
    evidence_status: "ready",
  },
];

export function getMockHealth(scenario: MockScenario = "busy_shift"): HealthResponse {
  const baseComponents = [
    { name: "pipeline", status: "ok", last_heartbeat: new Date().toISOString(), detail: "Pipeline stream active" },
    { name: "rule_engine", status: "ok", last_heartbeat: new Date().toISOString(), detail: "Rule engine active" },
    { name: "evidence_writer", status: "ok", last_heartbeat: new Date().toISOString(), detail: "Storage ready" },
    { name: "api", status: "ok", last_heartbeat: new Date().toISOString(), detail: "API active" },
    { name: "broker", status: "ok", last_heartbeat: new Date().toISOString(), detail: "Broker active" },
  ];

  if (scenario === "camera_lost") {
    return {
      status: "down",
      uptime_s: 4120,
      camera: "lost",
      mqtt: "connected",
      engine_precision: "INT8",
      fps: 0.0,
      latency_ms: 0.0,
      gpu_util: null,
      gpu_power_w: null,
      mode: "LIVE",
      replay_file: null,
      components: baseComponents.map((c) => (c.name === "pipeline" ? { ...c, status: "down", detail: "Camera signal lost" } : c)),
      privacy: { blurred_source: false },
    };
  }
  if (scenario === "mqtt_down") {
    return {
      status: "degraded",
      uptime_s: 4120,
      camera: "operational",
      mqtt: "disconnected",
      engine_precision: "INT8",
      fps: 25.0,
      latency_ms: 38.9,
      gpu_util: 34,
      gpu_power_w: 14.8,
      mode: "LIVE",
      replay_file: null,
      components: baseComponents.map((c) => (c.name === "broker" ? { ...c, status: "disconnected", detail: "MQTT broker unreachable" } : c)),
      privacy: { blurred_source: true },
    };
  }
  if (scenario === "calm") {
    return {
      status: "ok",
      uptime_s: 9400,
      camera: "operational",
      mqtt: "connected",
      engine_precision: "INT8",
      fps: 25.0,
      latency_ms: 36.2,
      gpu_util: 31,
      gpu_power_w: 14.2,
      mode: "LIVE",
      replay_file: null,
      components: baseComponents,
      privacy: { blurred_source: true },
    };
  }
  return {
    status: "ok",
    uptime_s: 3600,
    camera: "operational",
    mqtt: "connected",
    engine_precision: "INT8",
    fps: 25.0,
    latency_ms: 38.9,
    gpu_util: 38,
    gpu_power_w: 15.4,
    mode: "LIVE",
    replay_file: null,
    components: baseComponents,
    privacy: { blurred_source: true },
  };
}

export function getMockStats(): StatsResponse {
  const hours = [];
  const now = new Date();
  for (let i = 23; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 3600 * 1000);
    const hourLabel = `${d.getHours().toString().padStart(2, "0")}:00`;
    // realistic distribution peaking around shift transitions
    const count = (i === 2 || i === 8 || i === 14) ? 3 : (i % 4 === 0) ? 1 : 0;
    hours.push({ hour: hourLabel, count });
  }

  return {
    window: "24h",
    total_incidents: 8,
    by_type: {
      NO_HELMET: 3,
      NO_VEST: 1,
      ZONE_INTRUSION: 3,
      DANGER_DWELL: 1,
    },
    by_zone: {
      walkway: 4,
      "press-area": 3,
      "crane-drop": 1,
    },
    by_severity: {
      LOW: 1,
      MEDIUM: 3,
      HIGH: 4,
    },
    by_hour: hours,
    compliance_percentage: 97.8,
  };
}

export function generateManyMockIncidents(count: number = 300): Incident[] {
  const result: Incident[] = [...INITIAL_MOCK_INCIDENTS];
  const types: Incident["type"][] = ["NO_HELMET", "NO_VEST", "ZONE_INTRUSION", "DANGER_DWELL"];
  const zones = ["walkway", "press-area", "crane-drop"];
  const severities: Incident["severity"][] = ["LOW", "MEDIUM", "HIGH"];

  for (let i = 4; i < count; i++) {
    const type = types[i % types.length];
    const severity = type === "ZONE_INTRUSION" || type === "DANGER_DWELL" ? "HIGH" : severities[i % severities.length];
    const zone = zones[i % zones.length];
    const ts = new Date(Date.now() - (i * 240 + Math.random() * 60) * 1000).toISOString();
    const acked = i > 15;

    result.push({
      incident_id: `mock-${i.toString().padStart(4, "0")}`,
      timestamp: ts,
      camera_id: "cam-01",
      type,
      severity,
      track_id: (i % 25) + 1,
      zone,
      confidence: 0.85 + (i % 15) * 0.01,
      duration_s: type === "ZONE_INTRUSION" ? 0 : 1.5 + (i % 5) * 0.8,
      evidence_clip: acked ? "/evidence/sample/sample_incident.mp4" : null,
      schema_version: "1.0",
      status: acked ? "acknowledged" : "open",
      acked_at: acked ? new Date(new Date(ts).getTime() + 60000).toISOString() : null,
      acked_by: acked ? "safety-officer" : null,
      notes: [],
      evidence_status: "ready",
    });
  }
  return result;
}
