# SiteSentinel: Dashboard Design

## 1. Subject and audience
A safety officer watching a live site camera. The primary job: notice a real violation within seconds, see proof, and acknowledge it. The secondary job (site manager): see where and when violations cluster. Visual language comes from site signage and industrial control rooms: functional, high-contrast, quiet until something is wrong.

## 2. Principles
1. Quiet by default, loud only for incidents. Normal state is calm neutral surfaces; color is reserved for meaning.
2. Evidence first. Every incident shows its blurred clip thumbnail, zone and duration without a click.
3. Honest system state. Engine precision (FP16 or INT8), FPS and MQTT status are always visible, so the PipeGen contribution is never hidden.
4. One memorable element: the live video panel with zone overlays whose outlines change as the state changes.

## 3. Color tokens
SiteSentinel implements dual-theme tokens as CSS variables (light default; dark "control room" theme default for Present mode). Contrast is verified to maintain at least 4.5:1 for text and 3:1 for UI boundaries in both modes.

| Token | Light (Default) | Dark (Control Room) | Use |
|---|---|---|---|
| `--bg` | `#E3E6E8` (concrete-100) | `#10161B` (near-black steel) | Main application background |
| `--surface` | `#F4F5F6` (concrete-50) | `#172129` (dark steel) | Panels, cards, sidebars |
| `--surface-raised` | `#FFFFFF` (pure white) | `#1E2A33` (steel-900) | Modals, drawers, popovers, active tabs |
| `--border` | `#D0D5D9` | `#283743` | Neutral component and panel dividers |
| `--border-strong` | `#9EACB5` | `#3E5160` | Input borders, active outlines, table headers |
| `--text` | `#1E2A33` (steel-900) | `#F4F5F6` (concrete-50) | Primary copy, titles, numbers |
| `--text-muted` | `#566874` | `#8B9CA8` | Captions, secondary labels, metadata |
| `--text-inverse` | `#FFFFFF` | `#10161B` | Text on solid semantic badges |
| `--info` | `#1F6FD0` (signal-blue) | `#1F6FD0` | Safe zones, focus rings, info badges |
| `--info-subtle` | `#E8F2FC` | `#0F2D54` | Low-priority badge and row backgrounds |
| `--info-strong` | `#134B8C` | `#6CB1FC` | High-contrast info text and accents |
| `--warn` | `#F2A900` (caution-amber) | `#F2A900` | Restricted zones, MEDIUM severity |
| `--warn-subtle` | `#FEF8E7` | `#4D3500` | Medium-priority badge backgrounds |
| `--warn-strong` | `#9E6D00` | `#FFCC66` | High-contrast warning text and accents |
| `--danger` | `#E8590C` (hazard-orange) | `#E8590C` | Danger zones, HIGH severity, active violation |
| `--danger-subtle` | `#FCEEE7` | `#541D02` | High-priority badge and alert backgrounds |
| `--danger-strong` | `#9E3804` | `#FF8E52` | High-contrast danger text and accents |
| `--ok` | `#2E8B57` (clear-green) | `#2E8B57` | Healthy system status, compliant workers |
| `--ok-subtle` | `#EBF6F0` | `#0E3621` | Compliant status chip backgrounds |
| `--ok-strong` | `#1B5334` | `#5FCA92` | High-contrast success text and accents |

Severity is never conveyed by color alone: each level also pairs with a Lucide icon (`Info`, `AlertTriangle`, `AlertOctagon`, `CheckCircle2`) and a text label.

## 4. Typography
- Headings and large numbers: `@fontsource/barlow-condensed` 600 weight.
  - Display: 32px / 36px line-height
  - Heading 1: 24px / 28px
  - Heading 2: 18px / 24px
- Body and UI: `@fontsource/ibm-plex-sans` (400 regular, 500 medium, 600 semibold).
  - Body: 14px / 20px
  - Small / Caption: 12px / 16px
- Identifiers, timestamps, and numbers: `@fontsource/ibm-plex-mono` (400, 600).
- Tabular numerals (`font-variant-numeric: tabular-nums`) applied across all numbers and data tables.
- Sentence case everywhere. Max line length 72 characters.

## 5. Spacing, Elevation, and Motion
- Base unit: 4px grid (4, 8, 12, 16, 24, 32, 48px).
- Corner radius: 4px for buttons, inputs, tabs, and controls; 6px for panels and cards; 999px for status chips.
- Elevation: Clean industrial borders (`1px solid var(--border)`); shadows strictly reserved for floating popovers and dialog overlays (`0 4px 16px rgba(0, 0, 0, 0.16)`).
- Focus ring: 2px `--info` with 2px offset for keyboard accessibility (`:focus-visible`).
- Motion: Restrained 120ms to 180ms ease-out transitions for interactive state changes; honor `prefers-reduced-motion: reduce`.

## 6. Layout and Navigation (Desktop 1440px, Tablet 1024px, Mobile 390px)
```
+-----------------------------------------------------------------------+
| SiteSentinel   cam-01 | Engine INT8 | 25 FPS | 38.9 ms | MQTT ok | GPU |
+----+----------------------------------+-------------------------------+
| N  |                                  |  Incidents                    |
| A  |   Live annotated video           |  [thumb] No helmet            |
| V  |   (zones outlined, boxes, IDs)   |   press-area  3.4 s           |
|    |                                  |  [thumb] Zone entry           |
| R  |                                  |   crane-drop                  |
| A  +----------------------------------+-------------------------------+
| I  | Today by zone                    | Violations per hour           |
| L  +----------------------------------+-------------------------------+
+----+------------------------------------------------------------------+
```
- Navigation rail (collapsible, shortcuts `g l`, `g i`, `g z`, `g r`, `g s`): Live, Incidents, Zones, Reports, System.
- Global command palette (`Cmd/Ctrl+K`): quick jump, search incidents, toggle Present mode (`P`) and theme.
- Responsive layout: 1440px desktop side-by-side; 1024px collapses feed below video; 390px mobile presents feed first with collapsible video.

## 7. Screens
1. **Live view** (`/`): Video stream with zone overlay SVG and hazard violation highlights, virtualized incident feed with severity markers, zone distribution, 24h hourly distribution, compliance score.
2. **Incident detail** (`/incidents/:id` & side drawer): Blurred MP4 clip player, scrub timeline with violation window, metadata grid, acknowledge action, note thread, copy JSON, download clip.
3. **Incidents table** (`/incidents`): Dense sortable filterable table, server-side keyset pagination, URL query parameters, CSV export, bulk acknowledge.
4. **Zone editor** (`/zones`): Polygon editor on live snapshot, vertex add/move/delete, 8px grid snapping, undo/redo (`Cmd/Ctrl+Z`), inline validation, required PPE toggles, live foot-point footprint visualization.
5. **Reports** (`/reports`): Date range selector, compliance percentage, weekday-hour compliance heatmap, trend lines, CSV export, accessible table toggle.
6. **System** (`/system`): Engine precision and build card, live metrics sparklines, service health matrix, FP32/FP16/INT8 comparison table with grouped bar chart, privacy audit score.
7. **Design Gallery** (`/design`): Development showcase of all primitives in every interactive state.

## 8. Primitives Catalog
Every component implements default, hover, focus-visible, active, disabled, loading, and error states:
- `Button` (primary, secondary, ghost, danger; sizes sm, md; loading spinner)
- `IconButton` (accessible aria-label, tooltip integration)
- `Input`, `Select`, `Switch`, `SegmentedControl`
- `Badge` (severity LOW/MEDIUM/HIGH, zone safe/restricted/danger, status open/acked)
- `StatusDot` (ok, degraded, down with pulse on degraded/down)
- `Panel` (header, body, footer, collapsible)
- `Table` (dense, sticky header, right-aligned tabular numerals)
- `Skeleton`, `EmptyState`, `ErrorState`, `Toast`
- `KeyboardHint`, `Kbd`
- `Stat` (label, tabular value, trend delta, sparkline)
- `Sparkline`, `Timeline`

## 9. Copy and Tone Rules
Plain verbs and sentence case. Buttons name their action ("Acknowledge", "Save zone", "Export CSV"). The same action keeps the same name in toasts: "Zone saved". Incident names: "No helmet", "No vest", "Zone entry", "Danger-zone dwell".
Error format: what happened, why if known, what to do ("Camera lost. Check the USB cable or the RTSP address in config/sentinel.yaml.").
Strictly prohibited: exclamation marks, jokes, slang, "Oops", decorative emoji, fabricated filler text.

## 10. Motion and Accessibility (WCAG 2.2 AA)
- 120ms to 180ms ease-out transitions for state changes only.
- Keyboard navigation: visible 2px focus ring with 2px offset.
- Semantic HTML landmarks (`header`, `nav`, `main`, `aside`, `section`).
- ARIA live region (`polite` for LOW/MEDIUM incidents, `assertive` for HIGH incidents).
- Zero color-only meaning: every status pairs icon + color + label.

## 11. Present Mode
Activated with key `P` or header toggle:
- Switches automatically to dark "control room" theme.
- Maximizes video panel and incident feed.
- Hides editing controls and navigation chrome while preserving telemetry HealthBar.
- Fully optimized for full-screen control-room displays and hackathon judges.

