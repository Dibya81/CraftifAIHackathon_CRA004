import React from "react";
import { StatsData } from "../types";

interface TodayByZoneAndHourlyProps {
  stats: StatsData;
}

export const TodayByZoneAndHourly: React.FC<TodayByZoneAndHourlyProps> = ({ stats }) => {
  const maxHourCount = Math.max(1, ...stats.by_hour.map((h) => h.count));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "24px", marginTop: "24px" }}>
      {/* Today by Zone Card */}
      <div
        style={{
          backgroundColor: "var(--white)",
          padding: "20px",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-sm)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <h3 style={{ fontSize: "18px", marginBottom: "14px" }}>Today by zone</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", flex: 1, justifyContent: "center" }}>
          {Object.keys(stats.by_zone).length === 0 ? (
            <div style={{ fontSize: "13px", color: "var(--steel-700)", textAlign: "center", padding: "16px 0" }}>
              No zone violations today
            </div>
          ) : (
            Object.entries(stats.by_zone).map(([zone, count]) => {
              const maxZone = Math.max(1, ...Object.values(stats.by_zone));
              const pct = (count / maxZone) * 100;
              return (
                <div key={zone}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
                    <span style={{ fontWeight: 600 }}>{zone}</span>
                    <span style={{ fontVariantNumeric: "tabular-nums", color: "var(--steel-700)" }}>{count}</span>
                  </div>
                  <div style={{ height: "6px", backgroundColor: "var(--concrete-100)", borderRadius: "3px", overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${pct}%`,
                        backgroundColor: zone === "crane-drop" ? "var(--hazard-orange)" : "var(--caution-amber)",
                        borderRadius: "3px",
                      }}
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Violations per hour Card */}
      <div
        style={{
          backgroundColor: "var(--white)",
          padding: "20px",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <h3 style={{ fontSize: "18px", marginBottom: "14px" }}>Violations per hour</h3>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: "8px",
            height: "90px",
            borderBottom: "1px solid var(--concrete-100)",
            paddingBottom: "4px",
          }}
        >
          {stats.by_hour.map((h) => {
            const barHeight = Math.max(4, (h.count / maxHourCount) * 100);
            return (
              <div
                key={h.hour}
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "4px",
                  height: "100%",
                  justifyContent: "flex-end",
                }}
              >
                {h.count > 0 && (
                  <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--steel-700)" }}>{h.count}</span>
                )}
                <div
                  style={{
                    width: "100%",
                    maxWidth: "24px",
                    height: `${barHeight}%`,
                    backgroundColor: h.count > 0 ? "var(--hazard-orange)" : "var(--concrete-100)",
                    borderRadius: "2px 2px 0 0",
                    transition: "height 150ms ease",
                  }}
                />
                <span style={{ fontSize: "10px", color: "var(--steel-700)" }}>{h.hour}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
