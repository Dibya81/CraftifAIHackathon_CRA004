export type IncidentType = "NO_HELMET" | "NO_VEST" | "ZONE_INTRUSION" | "DANGER_DWELL";
export type SeverityType = "LOW" | "MEDIUM" | "HIGH";
export type ZoneType = "safe" | "restricted" | "danger";

export interface Incident {
  incident_id: string;
  timestamp: string;
  camera_id: string;
  type: IncidentType;
  severity: SeverityType;
  track_id: number;
  zone: string | null;
  confidence: number;
  duration_s: number;
  evidence_clip: string | null;
  acknowledged?: boolean;
  ack_meta?: {
    acked_at: string;
    user: string;
    comment?: string;
  };
  notes?: Array<{
    note: string;
    author: string;
    created_at: string;
  }>;
}

export interface ZoneDefinition {
  id: string;
  type: ZoneType;
  required_ppe: string[];
  polygon: number[][];
}

export interface ZonesConfig {
  frame: { width: number; height: number };
  zones: ZoneDefinition[];
}

export interface HealthState {
  status: "ok" | "degraded" | "down";
  uptime_s: number;
  camera: string;
  mqtt: string;
  engine_precision: string;
  fps: number;
  latency_ms: number;
  gpu_util: number | null;
  gpu_power_w: number | null;
}

export interface StatsData {
  window: string;
  total_incidents: number;
  by_type: Record<string, number>;
  by_zone: Record<string, number>;
  by_severity: Record<string, number>;
  by_hour: Array<{ hour: string; count: number }>;
  compliance_percentage: number;
}
