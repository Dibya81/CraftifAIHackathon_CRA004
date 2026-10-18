# SiteSentinel Dashboard Evidence & Visual Snapshots

This directory contains verified UI captures of the **SiteSentinel Control Room Dashboard** rendered in SIMULATED mode (`sentinel run --sim` serving live 25 FPS OpenCV frames, zone polygons, and matching detections).

All screenshots are captured from the production-built React 18 + TypeScript application running on self-hosted `@fontsource` typography (`Barlow Condensed 600`, `IBM Plex Sans`, `IBM Plex Mono`) with strict adherence to industrial control room design guidelines (`docs/DESIGN.md`).

---

## Screenshot Inventory & View Descriptions

| File | Resolution / Mode | Description |
|---|---|---|
| [`dashboard-live-simulated.png`](dashboard-live-simulated.png) | 1440x900 / SIMULATED Mode | Redesigned control room view with persistent 'Simulated data. Not a live camera.' banner, real-time OpenCV stream with blurred faces, live SVG zone overlays, dense grid incident feed, and hand-tuned hourly histogram. |
| [`dashboard-live-dark.png`](dashboard-live-dark.png) | 1440x900 / Dark Steel (SIMULATED) | Dark control room theme. Steel near-black surfaces (`#0C1014`, `#141A21`), high contrast `>= 4.5:1`, low eye fatigue under 24/7 operator monitoring conditions. |
| [`dashboard-live-light.png`](dashboard-live-light.png) | 1440x900 / Light (SIMULATED) | High-contrast daytime inspection theme with crisp typography and clean dividers. |
| [`dashboard-health-dropdown.png`](dashboard-health-dropdown.png) | 1440x900 / Component Telemetry | Expanded health status dropdown showing underlying components: pipeline, rule_engine, evidence_writer, API, and MQTT broker with heartbeat timestamps. |
| [`dashboard-1024.png`](dashboard-1024.png) | 1024x800 / Tablet Viewport | Tablet breakpoint layout with responsive grid adaptation and scroll containment. |
| [`dashboard-390.png`](dashboard-390.png) | 390x800 / Mobile Viewport | Mobile viewport layout with vertical component stacking and responsive telemetry bars. |
| [`dashboard-present-mode.png`](dashboard-present-mode.png) | Fullscreen / Present Mode (`P`) | Distraction-free presentation mode for control room monitors and hackathon demo stages. Collapses editing chrome, expands live video canvas and active incident feed while maintaining universal top telemetry health bar. |
| [`dashboard-incidents.png`](dashboard-incidents.png) | 1440x900 / Audit Log | Tabular records of detected safety infractions with multi-column filtering, URL query parameter state persistence, CSV export, and bulk acknowledgment. |
| [`dashboard-zones.png`](dashboard-zones.png) | 1440x900 / Zone Editor | Interactive polygon authoring tool. 8px grid snapping, geometric self-intersection detection, undo/redo (`Cmd+Z`), live person footprint overlays, and zero-downtime hot-reload (`PUT /api/zones`). |
| [`dashboard-reports.png`](dashboard-reports.png) | 1440x900 / Compliance Trends | Historical safety intelligence. Date range filtering, weekday × shift hour incident heatmap, compliance percentages, and accessible table alternatives. |
| [`dashboard-system.png`](dashboard-system.png) | 1440x900 / Silicon Telemetry | Deep PipeGen integration telemetry. INT8 vs FP16 vs FP32 TensorRT engine comparison scorecard, real-time FPS/latency sparklines, and privacy-by-design audit certificates. |

---

## Verification & Reproducibility

To re-run the frontend quality checks or generate the production build:

```bash
# Verify TypeScript strict types and Vitest component suite (100% pass)
npm --prefix dashboard run check

# Compile production bundle (< 110 KB gzipped shell, zero external network calls)
npm --prefix dashboard run build

# Start preview server on port 4173
npm --prefix dashboard run preview -- --port 4173
```
