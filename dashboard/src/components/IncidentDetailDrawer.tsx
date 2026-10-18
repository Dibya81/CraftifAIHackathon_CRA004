import React, { useState } from "react";
import {
  X,
  ChevronLeft,
  ChevronRight,
  Download,
  Copy,
  Check,
  Video,
} from "lucide-react";
import { Incident } from "../api/schema";
import {
  Button,
  SeverityBadge,
  ZoneBadge,
  StatusBadge,
} from "../design/primitives";
import { formatIncidentName } from "./IncidentFeed";

interface IncidentDetailDrawerProps {
  incident: Incident | null;
  onClose: () => void;
  onAcknowledge: (incidentId: string, comment?: string) => Promise<void>;
  onAddNote: (incidentId: string, note: string) => Promise<void>;
  onPrev?: () => void;
  onNext?: () => void;
  hasPrev?: boolean;
  hasNext?: boolean;
}

export const IncidentDetailDrawer: React.FC<IncidentDetailDrawerProps> = ({
  incident,
  onClose,
  onAcknowledge,
  onAddNote,
  onPrev,
  onNext,
  hasPrev = false,
  hasNext = false,
}) => {
  const [comment, setComment] = useState("");
  const [newNote, setNewNote] = useState("");
  const [isAcking, setIsAcking] = useState(false);
  const [isPostingNote, setIsPostingNote] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!incident) return null;

  const isAcked = incident.status === "acknowledged";

  const handleAck = async () => {
    setIsAcking(true);
    try {
      await onAcknowledge(incident.incident_id, comment.trim() || undefined);
      setComment("");
    } finally {
      setIsAcking(false);
    }
  };

  const handlePostNote = async () => {
    if (!newNote.trim()) return;
    setIsPostingNote(true);
    try {
      await onAddNote(incident.incident_id, newNote.trim());
      setNewNote("");
    } finally {
      setIsPostingNote(false);
    }
  };

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(incident, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const clipSrc = incident.evidence_clip
    ? incident.evidence_clip.startsWith("http") || incident.evidence_clip.startsWith("/")
      ? incident.evidence_clip
      : `/${incident.evidence_clip}`
    : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-incident-title"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(16, 22, 27, 0.6)",
        backdropFilter: "blur(2px)",
        zIndex: 2000,
        display: "flex",
        justifyContent: "flex-end",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <aside
        style={{
          width: "100%",
          maxWidth: "580px",
          height: "100%",
          backgroundColor: "var(--surface-raised)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "var(--shadow-dialog)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* Drawer Header with Prev/Next and Close */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            backgroundColor: "var(--surface)",
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <SeverityBadge severity={incident.severity} />
            <span
              id="drawer-incident-title"
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "18px",
                fontWeight: 600,
                color: "var(--text)",
              }}
            >
              {formatIncidentName(incident.type)}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {onPrev && (
              <button
                onClick={onPrev}
                disabled={!hasPrev}
                title="Previous incident"
                style={{
                  background: "transparent",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  color: hasPrev ? "var(--text)" : "var(--border-strong)",
                  cursor: hasPrev ? "pointer" : "not-allowed",
                  padding: "4px 6px",
                  display: "flex",
                }}
              >
                <ChevronLeft size={16} />
              </button>
            )}
            {onNext && (
              <button
                onClick={onNext}
                disabled={!hasNext}
                title="Next incident"
                style={{
                  background: "transparent",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  color: hasNext ? "var(--text)" : "var(--border-strong)",
                  cursor: hasNext ? "pointer" : "not-allowed",
                  padding: "4px 6px",
                  display: "flex",
                }}
              >
                <ChevronRight size={16} />
              </button>
            )}
            <button
              onClick={onClose}
              title="Close incident details"
              style={{
                background: "transparent",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text-muted)",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Drawer Body */}
        <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Blurred Video Player */}
          <div
            style={{
              backgroundColor: "#000000",
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
              border: "1px solid var(--border)",
              aspectRatio: "16 / 9",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
            }}
          >
            {clipSrc ? (
              <video
                controls
                autoPlay
                loop
                muted
                playsInline
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
                src={clipSrc}
              />
            ) : (
              <div
                style={{
                  color: "#A0AAB0",
                  textAlign: "center",
                  padding: "24px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Video size={28} />
                <span style={{ fontSize: "13px" }}>
                  {incident.evidence_status === "failed"
                    ? "Evidence clip failed to record"
                    : incident.evidence_status === "partial"
                    ? "Partial clip recorded (stream dropped)"
                    : "Evidence clip buffering or unavailable"}
                </span>
              </div>
            )}

            {/* Privacy Badge overlay */}
            <div
              style={{
                position: "absolute",
                bottom: "8px",
                right: "8px",
                padding: "2px 8px",
                backgroundColor: "rgba(16, 22, 27, 0.75)",
                borderRadius: "var(--radius-sm)",
                fontSize: "10px",
                color: "#E3E6E8",
                pointerEvents: "none",
              }}
            >
              Evidence face-blurred before storage
            </div>
          </div>

          {/* Timeline violation interval scrubber */}
          <div
            style={{
              padding: "12px 16px",
              backgroundColor: "var(--surface)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
              display: "flex",
              flexDirection: "column",
              gap: "6px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "var(--text-muted)" }}>
              <span>Violation Interval</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>{incident.duration_s.toFixed(1)}s active</span>
            </div>
            <div
              style={{
                height: "6px",
                backgroundColor: "var(--border)",
                borderRadius: "var(--radius-full)",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: "35%",
                  width: `${Math.min(30 + incident.duration_s * 8, 60)}%`,
                  top: 0,
                  bottom: 0,
                  backgroundColor: incident.severity === "HIGH" ? "var(--danger)" : "var(--warn)",
                  borderRadius: "var(--radius-full)",
                }}
              />
            </div>
          </div>

          {/* Explainability: Why It Fired (Decision Timeline) */}
          {incident.explanation && (
            <div
              style={{
                padding: "14px 16px",
                backgroundColor: "var(--surface)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border)",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--text)" }}>
                  Why It Fired (Decision Timeline)
                </span>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                  {incident.explanation.frames_window || 0} frames window
                </span>
              </div>

              <div style={{ fontSize: "12px", color: "var(--text-muted)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                <div>Rule: <span style={{ color: "var(--text)", fontWeight: 500 }}>{incident.explanation.rule || incident.type}</span></div>
                <div>Zone: <span style={{ color: "var(--text)", fontWeight: 500 }}>{incident.explanation.zone || incident.zone || "N/A"}</span></div>
                <div>Threshold: <span style={{ color: "var(--text)", fontWeight: 500 }}>{incident.explanation.threshold !== undefined ? `${incident.explanation.threshold}s` : "0.0s"}</span></div>
                <div>Elapsed: <span style={{ color: "var(--text)", fontWeight: 500 }}>{incident.explanation.elapsed_s !== undefined ? `${incident.explanation.elapsed_s}s` : `${incident.duration_s.toFixed(1)}s`}</span></div>
              </div>

              {/* Per-frame confidence timeline bar */}
              {incident.explanation.confidences && incident.explanation.confidences.length > 0 && (
                <div style={{ marginTop: "4px" }}>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "6px", display: "flex", justifyContent: "space-between" }}>
                    <span>Per-Frame Confidences (last {incident.explanation.confidences.length} frames)</span>
                    <span style={{ fontFamily: "var(--font-mono)" }}>
                      {(Math.min(...incident.explanation.confidences) * 100).toFixed(0)}% - {(Math.max(...incident.explanation.confidences) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: "4px", height: "36px", padding: "2px 0" }}>
                    {incident.explanation.confidences.map((c: number, idx: number) => (
                      <div
                        key={idx}
                        title={`Frame ${idx + 1}: ${(c * 100).toFixed(0)}%`}
                        style={{
                          flex: 1,
                          height: `${Math.max(15, c * 100)}%`,
                          backgroundColor: c > 0.8 ? "var(--brand-primary)" : "var(--warn)",
                          borderRadius: "2px",
                          transition: "height 0.2s ease",
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Metadata Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "12px",
              padding: "16px",
              backgroundColor: "var(--surface)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
            }}
          >
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Zone</span>
              <div style={{ marginTop: "2px" }}>
                {incident.zone ? <ZoneBadge type={incident.zone} name={incident.zone} /> : <span style={{ color: "var(--text-muted)" }}>unassigned</span>}
              </div>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Track ID</span>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "14px", fontWeight: 600 }}>
                #{incident.track_id}
              </div>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Confidence</span>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "14px", fontWeight: 600 }}>
                {(incident.confidence * 100).toFixed(0)}%
              </div>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Camera</span>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "14px" }}>
                {incident.camera_id}
              </div>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Detected At</span>
              <div style={{ fontSize: "13px", color: "var(--text)" }}>
                {new Date(incident.timestamp).toLocaleString()}
              </div>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Status</span>
              <div style={{ marginTop: "2px" }}>
                <StatusBadge status={incident.status} />
              </div>
            </div>
          </div>

          {/* Quick Actions (Copy JSON & Download Clip) */}
          <div style={{ display: "flex", gap: "8px" }}>
            <Button
              variant="secondary"
              size="sm"
              icon={copied ? <Check size={14} /> : <Copy size={14} />}
              onClick={handleCopyJson}
            >
              {copied ? "JSON copied" : "Copy JSON"}
            </Button>
            {clipSrc && (
              <a
                href={clipSrc}
                download={`${incident.incident_id}.mp4`}
                style={{ textDecoration: "none" }}
              >
                <Button variant="secondary" size="sm" icon={<Download size={14} />}>
                  Download clip
                </Button>
              </a>
            )}
          </div>

          {/* Acknowledge Action Section */}
          <div
            style={{
              padding: "16px",
              backgroundColor: "var(--surface)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            <h4 style={{ fontSize: "14px", fontWeight: 600 }}>Officer Resolution</h4>
            {isAcked ? (
              <div style={{ color: "var(--ok-strong)", fontSize: "13px" }}>
                ✓ Acknowledged by {incident.acked_by || "safety-officer"} at{" "}
                {incident.acked_at ? new Date(incident.acked_at).toLocaleTimeString() : ""}
              </div>
            ) : (
              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  aria-label="Optional note for acknowledgement"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  style={{
                    flex: 1,
                    padding: "6px 10px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-strong)",
                    backgroundColor: "var(--surface-raised)",
                    color: "var(--text)",
                    fontSize: "13px",
                  }}
                />
                <Button variant="primary" size="sm" loading={isAcking} onClick={handleAck}>
                  Acknowledge
                </Button>
              </div>
            )}
          </div>

          {/* Safety Officer Log Notes Thread */}
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <h4 style={{ fontSize: "14px", fontWeight: 600 }}>Audit Trail & Notes</h4>
            {(!incident.notes || incident.notes.length === 0) ? (
              <p style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}>
                No notes entered on this record.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {incident.notes.map((n, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "8px 12px",
                      backgroundColor: "var(--surface)",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border)",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-muted)", marginBottom: "4px" }}>
                      <strong>{n.author}</strong>
                      <span style={{ fontFamily: "var(--font-mono)" }}>
                        {new Date(n.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <div>{n.note}</div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: "flex", gap: "8px" }}>
              <input
                type="text"
                aria-label="Add audit note"
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                style={{
                  flex: 1,
                  padding: "6px 10px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-strong)",
                  backgroundColor: "var(--surface-raised)",
                  color: "var(--text)",
                  fontSize: "13px",
                }}
              />
              <Button
                variant="secondary"
                size="sm"
                loading={isPostingNote}
                disabled={!newNote.trim()}
                onClick={handlePostNote}
              >
                Add note
              </Button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
};
