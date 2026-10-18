# SiteSentinel: Genuine Bugs and Reproducible Failures

This directory contains genuine, reproducible failures (crashes, rendering failures, and schema bugs) encountered and fixed during development.

---

## Reproducible Failures Inventory

| # | Artifact | Affected File | Failure Mode & One-Line Cause |
|---|---|---|---|
| 1 | `01_bug_system_page_crash.png` | `dashboard/src/components/SystemView.tsx` | Uncaught `TypeError: engineReport.models.map is not a function` caused by backend returning a dictionary instead of an array. |
| 2 | `02_bug_system_page_error_state.png` | `dashboard/src/components/SystemView.tsx` | Error boundary capture during API disconnect when server returned non-200 responses. |
| 3 | `03_bug_dashboard_initial_broken_feed.png` | `src/sentinel/adapters/video/mjpeg_relay.py` | Black canvas with detached SVG polygons caused by generator buffer starvation during fast client reconnects. |
| 4 | `06_video_system_page_bug_reproduce_and_fix.webp` | `dashboard/src/components/SystemView.tsx` | Screen recording reproducing the crash and verifying the dictionary-to-array normalization fix. |
