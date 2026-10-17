PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    zone TEXT,
    confidence REAL NOT NULL,
    duration_s REAL NOT NULL,
    evidence_clip TEXT,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    status TEXT NOT NULL DEFAULT 'open',
    acked_at TEXT,
    acked_by TEXT,
    evidence_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(type);
CREATE INDEX IF NOT EXISTS idx_incidents_zone ON incidents(zone);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);

CREATE TABLE IF NOT EXISTS incident_notes (
    note_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    author TEXT NOT NULL,
    note_text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incident_notes_inc_id ON incident_notes(incident_id);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    clip_path TEXT NOT NULL,
    thumbnail_path TEXT,
    duration_s REAL NOT NULL,
    is_blurred INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zones_versions (
    version INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS outbox (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    published_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);

CREATE TABLE IF NOT EXISTS health_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    fps REAL,
    latency_ms REAL,
    gpu_util REAL,
    gpu_power_w REAL,
    details TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_health_timestamp ON health_samples(timestamp DESC);

CREATE TABLE IF NOT EXISTS metrics_hourly (
    hour_bucket TEXT NOT NULL,
    zone TEXT NOT NULL,
    incident_type TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hour_bucket, zone, incident_type)
);
