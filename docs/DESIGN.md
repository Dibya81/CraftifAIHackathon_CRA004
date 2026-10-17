# SiteSentinel: Dashboard Design

## 1. Subject and audience
A safety officer watching a live site camera. The primary job: notice a real violation within seconds, see proof, and acknowledge it. The secondary job (site manager): see where and when violations cluster. Visual language comes from site signage and industrial control rooms: functional, high-contrast, quiet until something is wrong.

## 2. Principles
1. Quiet by default, loud only for incidents. Normal state is calm neutral surfaces; color is reserved for meaning.
2. Evidence first. Every incident shows its blurred clip thumbnail, zone and duration without a click.
3. Honest system state. Engine precision (FP16 or INT8), FPS and MQTT status are always visible, so the PipeGen contribution is never hidden.
4. One memorable element: the live video panel with zone overlays whose outlines change as the state changes.

## 3. Color tokens
| Token | Hex | Use |
|---|---|---|
| steel-900 | #1E2A33 | App chrome, text on light |
| concrete-100 | #E3E6E8 | Page background |
| concrete-50 | #F4F5F6 | Panels |
| signal-blue | #1F6FD0 | Safe zones, links, focus ring |
| hazard-orange | #E8590C | HIGH incidents, danger zones |
| caution-amber | #F2A900 | MEDIUM incidents, restricted zones |
| clear-green | #2E8B57 | Compliant state, healthy system |

Severity is never conveyed by color alone: each level also has an icon and a text label.

## 4. Typography
- Headings and large numbers: Barlow Condensed (signage feel, semibold). Scale: 32 / 24 / 18.
- Body and data: IBM Plex Sans, 14 / 16, line-height 1.5. Tabular numerals for counts and times.
- Sentence case everywhere. Line length under 80 characters.

## 5. Layout (desktop, 1440 px)
```
+--------------------------------------------------------------+
| SiteSentinel   cam-01 | Engine INT8 | 31 FPS | MQTT ok | GPU  |
+---------------------------------------+----------------------+
|                                       |  Incidents           |
|   Live annotated video                |  [thumb] No helmet   |
|   (zones outlined, boxes, track IDs)  |   press-area  3.4 s  |
|                                       |  [thumb] Zone entry  |
|                                       |   crane-drop         |
+----------------------+----------------+----------------------+
| Today by zone        | Violations per hour                   |
+----------------------+---------------------------------------+
```
Alignment: left-aligned text, numbers right-aligned in tables. Tablet collapses the incident feed under the video; mobile shows the feed first.

## 6. Screens
1. Live view (default): video, incident feed, zone counts, hourly chart, health bar.
2. Incident detail: clip player, timeline of the violation, zone, confidence, acknowledge and add-note actions.
3. Zone editor: draw polygons on a still frame, set type and required PPE, save to `zones.json`.
4. Reports: compliance percentage by zone, type and hour; export CSV.
5. System: engine precision, FPS, latency, GPU power, FP16 vs INT8 comparison from PipeGen reports.

## 7. Components and states
- Incident row: icon, type, zone, duration, time, thumbnail. States: new (bold, left bar in severity color), acknowledged (muted).
- Zone overlay: outline color by zone type; turns hazard-orange with a thicker stroke while a violation is active.
- Health pill: green when FPS is above target and MQTT connected; amber when degraded; orange with a banner when the camera is lost.
- Empty states: "No incidents in the last hour. Cameras are healthy." Errors state what failed and what to do: "Camera lost. Check the USB cable or the RTSP address in config/sentinel.yaml."

## 8. Copy rules
Plain verbs and sentence case. Buttons say what they do: "Acknowledge", "Save zone", "Export CSV". The same action keeps the same name in toasts: "Zone saved". Incident names: "No helmet", "No vest", "Zone entry", "Danger-zone dwell".

## 9. Motion
Only for state change: a new incident slides into the feed once; zone outlines transition color over 150 ms. Respect reduced-motion settings. No decorative animation.

## 10. Accessibility
Visible keyboard focus (signal-blue ring), contrast at least 4.5:1 for text, severity shown by icon plus label plus color, incident feed announced through an ARIA live region.

## 11. Demo mode
A "Present" toggle enlarges the video and feed, hides the zone editor, and keeps the health bar visible for judges.
