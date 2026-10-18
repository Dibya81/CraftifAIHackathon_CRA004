import { z } from "zod";

export const IncidentTypeSchema = z.enum(["NO_HELMET", "NO_VEST", "ZONE_INTRUSION", "DANGER_DWELL"]);
export type IncidentType = z.infer<typeof IncidentTypeSchema>;

export const SeveritySchema = z.enum(["LOW", "MEDIUM", "HIGH"]);
export type Severity = z.infer<typeof SeveritySchema>;

export const IncidentStatusSchema = z.enum(["open", "acknowledged"]);
export type IncidentStatus = z.infer<typeof IncidentStatusSchema>;

export const EvidenceStatusSchema = z.enum(["pending", "ready", "partial", "failed"]);
export type EvidenceStatus = z.infer<typeof EvidenceStatusSchema>;

export const IncidentNoteSchema = z.object({
  author: z.string().default("safety-officer"),
  note: z.string(),
  created_at: z.string(),
});
export type IncidentNote = z.infer<typeof IncidentNoteSchema>;

export const IncidentExplanationSchema = z.object({
  rule: z.string().optional(),
  thresholds: z.record(z.string(), z.any()).optional(),
  threshold: z.number().optional(),
  frames_window: z.number().optional(),
  confidences: z.array(z.number()).optional(),
  zone: z.string().nullable().optional(),
  timer_values: z.record(z.string(), z.any()).optional(),
  elapsed_s: z.number().optional(),
}).passthrough();
export type IncidentExplanation = z.infer<typeof IncidentExplanationSchema>;

export const IncidentSchema = z.object({
  incident_id: z.string(),
  timestamp: z.string(),
  camera_id: z.string().default("cam-01"),
  type: IncidentTypeSchema,
  severity: SeveritySchema,
  track_id: z.number(),
  zone: z.string().nullable().default(null),
  confidence: z.number().min(0).max(1),
  duration_s: z.number().min(0),
  evidence_clip: z.string().nullable().default(null),
  schema_version: z.string().default("1.0"),
  status: IncidentStatusSchema.default("open"),
  acked_at: z.string().nullable().optional(),
  acked_by: z.string().nullable().optional(),
  notes: z.array(IncidentNoteSchema).default([]),
  evidence_status: EvidenceStatusSchema.default("pending"),
  explanation: IncidentExplanationSchema.nullable().optional(),
});
export type Incident = z.infer<typeof IncidentSchema>;

export const IncidentsListResponseSchema = z.object({
  items: z.array(IncidentSchema),
  next_cursor: z.string().nullable().optional(),
  total: z.number().optional(),
});
export type IncidentsListResponse = z.infer<typeof IncidentsListResponseSchema>;

export const ComponentHealthSchema = z.object({
  name: z.string(),
  status: z.string(),
  last_heartbeat: z.string().nullable().optional(),
  detail: z.string().nullable().optional(),
});
export type ComponentHealth = z.infer<typeof ComponentHealthSchema>;

export const HealthResponseSchema = z.object({
  status: z.enum(["ok", "degraded", "down"]),
  uptime_s: z.number(),
  camera: z.string(),
  mqtt: z.string(),
  engine_precision: z.string().nullable().optional(),
  fps: z.number().nullable().optional(),
  latency_ms: z.number().nullable().optional(),
  gpu_util: z.number().nullable().optional(),
  gpu_power_w: z.number().nullable().optional(),
  mode: z.string().default("LIVE"),
  replay_file: z.string().nullable().optional(),
  components: z.array(ComponentHealthSchema).default([]),
  privacy: z.object({
    blurred_source: z.boolean().default(false),
    enforced: z.boolean().optional(),
    camera_active: z.boolean().optional(),
  }).default({ blurred_source: false }),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const ZoneDefinitionSchema = z.object({
  id: z.string(),
  type: z.enum(["safe", "restricted", "danger"]),
  required_ppe: z.array(z.string()).default([]),
  polygon: z.array(z.array(z.number())),
});
export type ZoneDefinition = z.infer<typeof ZoneDefinitionSchema>;

export const ZonesResponseSchema = z.object({
  frame: z.object({
    width: z.number(),
    height: z.number(),
  }),
  zones: z.array(ZoneDefinitionSchema),
  version: z.number().optional(),
  updated_at: z.string().optional(),
});
export type ZonesResponse = z.infer<typeof ZonesResponseSchema>;

export const StatsResponseSchema = z.object({
  window: z.string(),
  total_incidents: z.number(),
  by_type: z.record(z.string(), z.number()),
  by_zone: z.record(z.string(), z.number()),
  by_severity: z.record(z.string(), z.number()),
  by_hour: z.array(z.object({
    hour: z.string(),
    count: z.number(),
  })),
  compliance_percentage: z.number(),
});
export type StatsResponse = z.infer<typeof StatsResponseSchema>;
