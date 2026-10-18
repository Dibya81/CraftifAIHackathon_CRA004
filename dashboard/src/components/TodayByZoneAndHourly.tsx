import React, { useState } from "react";
import { StatsData } from "../types";

interface TodayByZoneAndHourlyProps {
  stats: StatsData;
}

export const TodayByZoneAndHourly: React.FC<TodayByZoneAndHourlyProps> = ({ stats }) => {
  const [hoveredHour, setHoveredHour] = useState<{ hour: string; count: number } | null>(null);

  // Normalize 24h hourly buckets
  const now = new Date();
  const currentHourNum = now.getHours();

  // If backend provided by_hour, use it, otherwise generate standard 24h structure
  const rawHours = stats.by_hour && stats.by_hour.length > 0 ? stats.by_hour : [];
  const totalViolations = rawHours.reduce((sum, h) => sum + h.count, 0);

  // Build full 24 hours if empty or sparse
  const hoursMap = new Map<string, number>();
  rawHours.forEach((h) => {
    // h.hour can be "09:00", "9", etc.
    const key = h.hour.includes(":") ? h.hour.split(":")[0] : h.hour.padStart(2, "0");
    hoursMap.set(key, h.count);
  });

  const full24Hours: { hour: string; hourNum: number; count: number }[] = [];
  for (let i = 0; i < 24; i++) {
    const key = i.toString().padStart(2, "0");
    full24Hours.push({
      hour: `${key}:00`,
      hourNum: i,
      count: hoursMap.get(key) || 0,
    });
  }

  const maxHourCount = Math.max(1, ...full24Hours.map((h) => h.count));
  const hasViolations = totalViolations > 0;

  const zoneEntries = Object.entries(stats.by_zone || {});
  const maxZoneCount = Math.max(1, ...zoneEntries.map(([, count]) => count));

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 2fr",
        gap: "16px",
        marginTop: "16px",
      }}
    >
      {/* Today by Zone Panel */}
      <div
        style={{
          backgroundColor: "var(--surface)",
          borderRadius: "6px",
          border: "1px solid var(--border)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "10px 16px",
            borderBottom: "1px solid var(--border)",
            fontSize: "13px",
            fontWeight: 600,
            color: "var(--text)",
          }}
        >
          Violations by zone
        </div>
        <div style={{ padding: "14px 16px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          {zoneEntries.length === 0 ? (
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                textAlign: "center",
                padding: "24px 0",
              }}
            >
              No violations in the last 24 hours.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {zoneEntries.map(([zone, count]) => {
                const pct = (count / maxZoneCount) * 100;
                const barColor =
                  zone.toLowerCase().includes("danger") || zone === "crane-drop"
                    ? "var(--danger)"
                    : zone.toLowerCase().includes("press") || zone.toLowerCase().includes("restricted")
                    ? "var(--warn)"
                    : "var(--info)";

                return (
                  <div key={zone}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: "12px",
                        marginBottom: "4px",
                      }}
                    >
                      <span style={{ fontWeight: 500, color: "var(--text)" }}>{zone}</span>
                      <span
                        style={{
                          fontVariantNumeric: "tabular-nums",
                          fontFamily: "var(--font-mono)",
                          fontSize: "12px",
                          color: "var(--text)",
                          fontWeight: 600,
                        }}
                      >
                        {count}
                      </span>
                    </div>
                    <div
                      style={{
                        height: "5px",
                        backgroundColor: "var(--surface-raised, rgba(255,255,255,0.06))",
                        borderRadius: "2px",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${pct}%`,
                          backgroundColor: barColor,
                          borderRadius: "2px",
                          transition: "width 0.2s ease",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Violations per hour (24h) Panel */}
      <div
        style={{
          backgroundColor: "var(--surface)",
          borderRadius: "6px",
          border: "1px solid var(--border)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "10px 16px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text)" }}>
            Violations per hour (last 24 hours)
          </span>
          {hoveredHour && (
            <span style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              {hoveredHour.hour}: <strong>{hoveredHour.count}</strong>
            </span>
          )}
        </div>

        <div style={{ padding: "14px 16px", flex: 1, display: "flex", flexDirection: "column" }}>
          {!hasViolations ? (
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                textAlign: "center",
                padding: "36px 0",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flex: 1,
              }}
            >
              No violations in the last 24 hours.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", height: "100%", justifyContent: "flex-end" }}>
              {/* Bars container */}
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-end",
                  gap: "4px",
                  height: "90px",
                  borderBottom: "1px solid var(--border)",
                  paddingBottom: "2px",
                  position: "relative",
                }}
              >
                {full24Hours.map((h) => {
                  const isCurrent = h.hourNum === currentHourNum;
                  const isMax = h.count > 0 && h.count === maxHourCount;
                  const barHeightPct = h.count > 0 ? Math.max(8, (h.count / maxHourCount) * 100) : 0;

                  return (
                    <div
                      key={h.hour}
                      onMouseEnter={() => setHoveredHour(h)}
                      onMouseLeave={() => setHoveredHour(null)}
                      style={{
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        height: "100%",
                        justifyContent: "flex-end",
                        cursor: "pointer",
                        position: "relative",
                      }}
                      title={`${h.hour}: ${h.count} violation${h.count === 1 ? "" : "s"}`}
                    >
                      {/* Only show max count on top */}
                      {isMax && (
                        <span
                          style={{
                            fontSize: "9px",
                            fontFamily: "var(--font-mono)",
                            color: "var(--text)",
                            fontWeight: 600,
                            marginBottom: "2px",
                          }}
                        >
                          {h.count}
                        </span>
                      )}

                      <div
                        style={{
                          width: "6px",
                          height: h.count > 0 ? `${barHeightPct}%` : "2px",
                          backgroundColor:
                            h.count > 0
                              ? isCurrent
                                ? "var(--accent, #3b82f6)"
                                : "var(--danger)"
                              : isCurrent
                              ? "var(--text-muted)"
                              : "var(--border)",
                          borderRadius: "2px 2px 0 0",
                          outline: isCurrent ? "1px solid var(--accent, #3b82f6)" : "none",
                          transition: "height 0.2s ease, background-color 0.15s ease",
                        }}
                      />
                    </div>
                  );
                })}
              </div>

              {/* Hour Axis Labels every 3 hours */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: "6px",
                  fontSize: "10px",
                  color: "var(--text-muted)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                <span>00:00</span>
                <span>03:00</span>
                <span>06:00</span>
                <span>09:00</span>
                <span>12:00</span>
                <span>15:00</span>
                <span>18:00</span>
                <span>21:00</span>
                <span>23:00</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
