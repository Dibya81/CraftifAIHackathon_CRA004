import React, { useState } from "react";
import { Incident } from "../types";
import { formatIncidentName, getSeverityBadge } from "./IncidentFeed";

interface IncidentDetailModalProps {
  incident: Incident | null;
  onClose: () => void;
  onAcknowledge: (incidentId: string, comment?: string) => Promise<boolean>;
  onAddNote: (incidentId: string, note: string) => Promise<boolean>;
}

export const IncidentDetailModal: React.FC<IncidentDetailModalProps> = ({
  incident,
  onClose,
  onAcknowledge,
  onAddNote,
}) => {
  const [comment, setComment] = useState("");
  const [newNote, setNewNote] = useState("");
  const [isAcking, setIsAcking] = useState(false);
  const [isPostingNote, setIsPostingNote] = useState(false);

  if (!incident) return null;

  const severityBadge = getSeverityBadge(incident.severity);

  const handleAck = async () => {
    setIsAcking(true);
    await onAcknowledge(incident.incident_id, comment);
    setIsAcking(false);
    setComment("");
  };

  const handlePostNote = async () => {
    if (!newNote.trim()) return;
    setIsPostingNote(true);
    await onAddNote(incident.incident_id, newNote.trim());
    setIsPostingNote(false);
    setNewNote("");
  };

  // Resolve evidence video source
  const clipSrc = incident.evidence_clip
    ? incident.evidence_clip.startsWith("http") || incident.evidence_clip.startsWith("/")
      ? incident.evidence_clip
      : `/${incident.evidence_clip}`
    : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-incident-title"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(30, 42, 51, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2000,
        padding: "20px",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          backgroundColor: "var(--white)",
          borderRadius: "var(--radius-lg)",
          width: "100%",
          maxWidth: "760px",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "var(--shadow-md)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 24px",
            borderBottom: "1px solid var(--concrete-100)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            backgroundColor: "var(--concrete-50)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span
              style={{
                backgroundColor: severityBadge.bg,
                color: severityBadge.color,
                padding: "4px 8px",
                borderRadius: "var(--radius-sm)",
                fontSize: "12px",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <span>{severityBadge.icon}</span>
              <span>{severityBadge.label}</span>
            </span>
            <h2 id="modal-incident-title" style={{ fontSize: "20px", margin: 0 }}>
              {formatIncidentName(incident.type)} &middot; Track #{incident.track_id}
            </h2>
          </div>

          <button
            onClick={onClose}
            aria-label="Close dialog"
            style={{
              background: "none",
              border: "none",
              fontSize: "24px",
              cursor: "pointer",
              color: "var(--steel-700)",
            }}
          >
            &times;
          </button>
        </div>

        {/* Scrollable Body */}
        <div style={{ padding: "24px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Evidence Video / Thumbnail */}
          <div
            style={{
              backgroundColor: "var(--steel-900)",
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
              position: "relative",
              width: "100%",
              aspectRatio: "16/9",
            }}
          >
            {clipSrc ? (
              <video
                src={clipSrc}
                controls
                autoPlay
                loop
                muted
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
              />
            ) : (
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--concrete-100)",
                }}
              >
                <div style={{ fontSize: "32px", marginBottom: "8px" }}>📹</div>
                <div>Evidence clip is being encoded in background ring buffer</div>
                <div style={{ fontSize: "12px", color: "#8E9DA8", marginTop: "4px" }}>
                  10-second blurred event (5s pre / 5s post trigger)
                </div>
              </div>
            )}
            <div
              style={{
                position: "absolute",
                top: "10px",
                right: "12px",
                background: "rgba(30,42,51,0.85)",
                color: "var(--white)",
                padding: "2px 8px",
                borderRadius: "var(--radius-sm)",
                fontSize: "11px",
              }}
            >
              🔒 Face-blurred evidence
            </div>
          </div>

          {/* Key Facts Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: "12px",
              backgroundColor: "var(--concrete-50)",
              padding: "16px",
              borderRadius: "var(--radius-md)",
            }}
          >
            <div>
              <div style={{ fontSize: "11px", color: "var(--steel-700)", textTransform: "uppercase" }}>Zone</div>
              <div style={{ fontWeight: 600, fontSize: "15px" }}>{incident.zone || "unassigned"}</div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "var(--steel-700)", textTransform: "uppercase" }}>Duration</div>
              <div style={{ fontWeight: 600, fontSize: "15px" }}>{incident.duration_s.toFixed(1)} s</div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "var(--steel-700)", textTransform: "uppercase" }}>Confidence</div>
              <div style={{ fontWeight: 600, fontSize: "15px" }}>{(incident.confidence * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "var(--steel-700)", textTransform: "uppercase" }}>Detected at</div>
              <div style={{ fontWeight: 600, fontSize: "14px" }}>
                {new Date(incident.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>

          {/* Acknowledge Action Section */}
          <div
            style={{
              border: "1px solid var(--concrete-100)",
              padding: "16px",
              borderRadius: "var(--radius-md)",
            }}
          >
            <h4 style={{ fontSize: "15px", marginBottom: "8px" }}>Incident resolution</h4>
            {incident.acknowledged ? (
              <div style={{ color: "var(--clear-green)", fontWeight: 600, fontSize: "14px" }}>
                ✓ Acknowledged by {incident.ack_meta?.user || "Safety Officer"} at{" "}
                {incident.ack_meta?.acked_at ? new Date(incident.ack_meta.acked_at).toLocaleTimeString() : ""}
                {incident.ack_meta?.comment && (
                  <div style={{ fontSize: "13px", color: "var(--steel-700)", marginTop: "4px", fontWeight: 400 }}>
                    Note: "{incident.ack_meta.comment}"
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <input
                  type="text"
                  placeholder="Optional acknowledgement note..."
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--steel-700)",
                    fontSize: "13px",
                  }}
                />
                <button
                  onClick={handleAck}
                  disabled={isAcking}
                  style={{
                    backgroundColor: "var(--signal-blue)",
                    color: "var(--white)",
                    border: "none",
                    padding: "8px 18px",
                    borderRadius: "var(--radius-sm)",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {isAcking ? "Saving..." : "Acknowledge"}
                </button>
              </div>
            )}
          </div>

          {/* Officer Notes Thread */}
          <div>
            <h4 style={{ fontSize: "15px", marginBottom: "10px" }}>Safety log notes</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "12px" }}>
              {(!incident.notes || incident.notes.length === 0) && (
                <div style={{ fontSize: "13px", color: "var(--steel-700)", fontStyle: "italic" }}>
                  No additional notes recorded yet.
                </div>
              )}
              {incident.notes?.map((n, i) => (
                <div
                  key={i}
                  style={{
                    backgroundColor: "var(--concrete-50)",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "13px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontWeight: 600 }}>{n.author}</span>
                    <span style={{ fontSize: "11px", color: "var(--steel-700)" }}>
                      {new Date(n.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div>{n.note}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: "10px" }}>
              <input
                type="text"
                placeholder="Add notes to audit trail..."
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--steel-700)",
                  fontSize: "13px",
                }}
              />
              <button
                onClick={handlePostNote}
                disabled={isPostingNote || !newNote.trim()}
                style={{
                  backgroundColor: "var(--steel-900)",
                  color: "var(--white)",
                  border: "none",
                  padding: "8px 16px",
                  borderRadius: "var(--radius-sm)",
                  cursor: newNote.trim() ? "pointer" : "not-allowed",
                  opacity: newNote.trim() ? 1 : 0.6,
                }}
              >
                Add note
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
