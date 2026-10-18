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
  status?: "open" | "acknowledged";
  acked_at?: string | null;
  acked_by?: string | null;
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
  evidence_status?: "pending" | "ready" | "partial" | "failed";
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

export interface ComponentHealth {
  name: string;
  status: string;
  last_heartbeat?: string | null;
  detail?: string | null;
}

export interface HealthState {
  status: "ok" | "degraded" | "down";
  uptime_s: number;
  camera: string;
  mqtt: string;
  engine_precision?: string | null;
  fps?: number | null;
  latency_ms?: number | null;
  gpu_util?: number | null;
  gpu_power_w?: number | null;
  mode?: "LIVE" | "REPLAY" | "SIMULATED";
  replay_file?: string | null;
  components?: ComponentHealth[];
  privacy?: {
    blurred_source?: boolean;
    enforced?: boolean;
    camera_active?: boolean;
  };
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
