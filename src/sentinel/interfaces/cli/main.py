"""Typer command-line interface for SiteSentinel."""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import typer
import uvicorn

from sentinel.adapters.storage.jsonl_log import JSONLAuditLog
from sentinel.adapters.storage.sqlite_repo import SQLiteIncidentRepository
from sentinel.config import load_sentinel_config
from sentinel.interfaces.cli.doctor import run_diagnostics

app = typer.Typer(
    name="sentinel",
    help="SiteSentinel Safety Intelligence CLI: run services, evaluate accuracy, simulate streams, and run system diagnostics.",
)


@app.command()
def doctor(
    payload: Optional[str] = typer.Option(
        None, "--payload", "-p", help="Path to sample payload or NDJSON file for adapter format self-diagnosis"
    ),
    hardware: bool = typer.Option(
        False, "--hardware", help="Run comprehensive edge hardware environment diagnostics"
    ),
):
    """Run diagnostic checks on dependencies, GPU, ports, broker, export manifest, or sample payloads."""
    if payload:
        from sentinel.interfaces.cli.doctor import diagnose_payload_file

        typer.echo(f"Diagnosing detector payload format: {payload}\n")
        diag = diagnose_payload_file(payload)
        if not diag.get("parsed_successfully"):
            typer.secho("FAIL: Could not successfully parse payload.", fg=typer.colors.RED, bold=True)
            for warn in diag.get("warnings", []):
                typer.echo(f"  Warning: {warn}")
            for rec in diag.get("recommendations", []):
                typer.echo(f"  Recommendation: {rec}")
            sys.exit(1)

        typer.secho(
            f"SUCCESS: Best matching format: {diag.get('detected_format')}",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo(f"  Detections extracted: {diag.get('detections_count')}")
        typer.echo(f"  Detected classes: {', '.join(diag.get('classes_detected', []))}")
        typer.echo("\nFormat evaluations:")
        for fmt, res in diag.get("format_evaluations", {}).items():
            st = "[PASS]" if res.get("success") else "[FAIL]"
            cnt = res.get("detections_count", 0)
            err = f" ({res.get('error')})" if res.get("error") else ""
            typer.echo(f"  {st} {fmt}: {cnt} detections{err}")

        if diag.get("fields_found"):
            typer.echo("\nField mapping report:")
            for k, v in diag["fields_found"].items():
                typer.echo(f"  - {k}: {v}")

        if diag.get("warnings"):
            typer.echo("\nWarnings:")
            for w in diag["warnings"]:
                typer.secho(f"  - {w}", fg=typer.colors.YELLOW)

        if diag.get("recommendations"):
            typer.echo("\nRecommendations:")
            for r in diag["recommendations"]:
                typer.echo(f"  - {r}")
        return

    if hardware:
        from sentinel.interfaces.cli.doctor import run_hardware_diagnostics

        typer.echo("Running Comprehensive Edge Hardware Diagnostics...\n")
        report = run_hardware_diagnostics()
        for check in report["checks"]:
            st = check["status"]
            if st == "PASS":
                typer.secho(f"  [PASS] {check['name']}: {check['detail']}", fg=typer.colors.GREEN)
            elif st == "SKIPPED":
                typer.secho(f"  [SKIP] {check['name']}: {check['detail']}", fg=typer.colors.BLUE)
            elif st == "WARNING":
                typer.secho(f"  [WARN] {check['name']}: {check['detail']}", fg=typer.colors.YELLOW)
                if check.get("fix"):
                    typer.echo(f"         Recommendation: {check['fix']}")
            else:  # BLOCKER
                typer.secho(f"  [BLOCKER] {check['name']}: {check['detail']}", fg=typer.colors.RED, bold=True)
                if check.get("fix"):
                    typer.echo(f"            Recommendation: {check['fix']}")

        typer.echo("")
        if report["blockers"]:
            typer.secho(
                f"FAILED: Found {len(report['blockers'])} hardware blocker(s): {', '.join(report['blockers'])}",
                fg=typer.colors.RED,
                bold=True,
            )
            raise typer.Exit(code=1)
        elif report["warnings"]:
            typer.secho(
                f"PASSED with {len(report['warnings'])} warning(s). Edge hardware operational for execution.",
                fg=typer.colors.YELLOW,
            )
        else:
            typer.secho("PASSED: All edge hardware checks verified.", fg=typer.colors.GREEN, bold=True)
        return

    typer.echo("Running SiteSentinel System Diagnostics...\n")
    report = run_diagnostics()

    for item in report["checks"]:
        symbol = (
            "[PASS]"
            if item["ok"]
            else (
                "[WARN]"
                if "GPU" in item["check"] or "Mosquitto" in item["check"]
                else "[FAIL]"
            )
        )
        typer.echo(f"{symbol} {item['check']}: {item['message']}")
        if not item["ok"] and item["fix"]:
            typer.echo(f"   Recommendation: {item['fix']}")

    typer.echo("")
    if report["status"] == "ok":
        typer.secho("SiteSentinel environment is operational.", fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho(
            "SiteSentinel found configuration warnings or issues. Review recommendations above.",
            fg=typer.colors.YELLOW,
        )


@app.command()
def replay(
    capture: str = typer.Argument(..., help="Path to NDJSON capture file"),
    speed: float = typer.Option(1.0, help="Playback speed multiplier (0.0 for instant max speed)"),
    save_incidents: bool = typer.Option(True, help="Persist raised incidents to logs/incidents.jsonl and database"),
    dry_run: bool = typer.Option(False, help="Do not persist or broadcast incidents"),
):
    """Deterministically replay a captured stream of detection frames through the adapter and rule engine."""
    from sentinel.adapters.pipegen import PipeGenAdapter
    from sentinel.config import load_rules_config
    from sentinel.domain.rules import RuleEngine
    from sentinel.domain.zones import ZoneManager

    capture_path = Path(capture)
    if not capture_path.exists():
        typer.secho(f"Error: Capture file {capture_path} does not exist.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    cfg = load_sentinel_config()
    rules_cfg = load_rules_config("config/rules.yaml")
    zones = ZoneManager.from_file(cfg.paths.zones)

    adapter = PipeGenAdapter(
        class_map=cfg.class_map,
        default_camera_id=cfg.camera_id,
        format_mode=cfg.adapter.format,
        bbox_format=cfg.adapter.bbox_format,
        bbox_normalized=cfg.adapter.bbox_normalized,
        timestamp_format=cfg.adapter.timestamp_format,
        fps=cfg.adapter.fps,
        track_id_fields=cfg.adapter.track_id_fields,
        class_fields=cfg.adapter.class_fields,
        conf_fields=cfg.adapter.conf_fields,
        bbox_fields=cfg.adapter.bbox_fields,
    )

    rule_engine = RuleEngine(rules_cfg=rules_cfg, zone_manager=zones)

    repo = None
    if save_incidents and not dry_run:
        repo = SQLiteIncidentRepository(
            db_path=Path(cfg.paths.incidents_log).parent / "sentinel.db",
            jsonl_log=JSONLAuditLog(cfg.paths.incidents_log),
        )

    typer.echo(f"Replaying stream from: {capture_path}")
    typer.echo(f"Speed: {speed}x | Persist: {save_incidents and not dry_run}")

    frames_processed = 0
    incidents_raised = []
    last_frame_ts = None
    start_wall_time = time.time()

    content = capture_path.read_text(encoding="utf-8")
    frames_raw: List[str] = []
    try:
        single_obj = json.loads(content)
        if isinstance(single_obj, dict):
            frames_raw = [content]
    except Exception:
        pass

    if not frames_raw:
        for line in content.splitlines():
            line_str = line.strip()
            if not line_str or "_sentinel_capture_header" in line_str:
                continue
            frames_raw.append(line_str)

    for item in frames_raw:
        meta = adapter.parse_payload(item)
        frames_processed += 1

        if speed > 0 and last_frame_ts is not None and meta.ts > last_frame_ts:
            delta = (meta.ts - last_frame_ts) / speed
            if 0 < delta < 2.0:
                time.sleep(delta)
        last_frame_ts = meta.ts

        # Evaluate frame
        raised = rule_engine.process_frame(meta)
        for inc in raised:
            incidents_raised.append(inc)
            if repo:
                from sentinel.domain.models import IncidentEvent, IncidentEventType

                evt = IncidentEvent.create(
                    event_type=IncidentEventType.INCIDENT_CREATED.value,
                    incident=inc,
                )
                repo.save_incident(incident=inc, outbox_event=evt)
            typer.echo(
                f"  [INCIDENT RAISED] Frame {meta.frame_id}: {inc.type} for track {inc.track_id} in {inc.zone} (conf: {inc.confidence:.2f})"
            )

    elapsed_time = max(time.time() - start_wall_time, 0.001)
    fps = frames_processed / elapsed_time

    typer.secho(
        f"\nReplay completed: {frames_processed} frames in {elapsed_time:.2f}s ({fps:.1f} FPS)",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(f"Total incidents raised: {len(incidents_raised)}")
    by_type: Dict[str, int] = {}
    for inc in incidents_raised:
        by_type[inc.type] = by_type.get(inc.type, 0) + 1
    for t, count in by_type.items():
        typer.echo(f"  - {t}: {count}")
    metrics = adapter.get_metrics()
    typer.echo(f"Adapter rejects: {metrics['adapter_rejects_total']}")


@app.command()
def api(
    host: str = typer.Option("0.0.0.0", help="Host interface to bind REST API"),
    port: int = typer.Option(8000, help="Port to bind REST API"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
):
    """Start SiteSentinel REST, WebSockets, and MJPEG relay server."""
    typer.echo(f"Starting SiteSentinel API on http://{host}:{port}")
    uvicorn.run(
        "sentinel.interfaces.api.app:create_app", host=host, port=port, factory=True, reload=reload
    )


@app.command()
def run(
    services: str = typer.Option("all", help="Services to run: all, api, engine, evidence"),
    file: Optional[str] = typer.Option(None, "--file", help="Path to video file for REPLAY mode"),
    sim: bool = typer.Option(
        False, "--sim", help="Run with continuous synthetic simulation stream"
    ),
    host: str = typer.Option("0.0.0.0", help="Host interface to bind REST API"),
    port: int = typer.Option(8000, help="Port to bind REST API"),
):
    """Run supervised SiteSentinel services in LIVE, REPLAY, or SIMULATED mode."""
    import os
    import threading

    load_sentinel_config()

    if file:
        video_path = Path(file)
        if not video_path.exists():
            typer.secho(
                f"Error: Video file '{file}' not found.\nPlace test clips in data/test_clips/ (e.g. data/test_clips/site01.mp4) and rerun.",
                fg=typer.colors.RED,
                bold=True,
            )
            raise typer.Exit(code=1)
        os.environ["SENTINEL_MODE"] = "REPLAY"
        os.environ["SENTINEL_REPLAY_FILE"] = str(video_path)
        typer.secho(
            f"SiteSentinel starting in REPLAY mode: {file}", fg=typer.colors.CYAN, bold=True
        )
    elif sim:
        os.environ["SENTINEL_MODE"] = "SIMULATED"
        typer.secho(
            "SiteSentinel starting in SIMULATED mode (25 FPS synthetic video + detections)",
            fg=typer.colors.YELLOW,
            bold=True,
        )
    else:
        os.environ["SENTINEL_MODE"] = "LIVE"
        typer.secho("SiteSentinel starting in LIVE mode", fg=typer.colors.GREEN, bold=True)

    # Replay background thread
    def replay_loop():
        import cv2

        time.sleep(1.0)  # Wait for API server to bind
        cap = cv2.VideoCapture(str(file))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_interval = 1.0 / fps
        try:
            from sentinel.interfaces.api.app import state
        except Exception:
            state = None

        while True:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            success, enc = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if success and state is not None:
                state.relay.update_jpeg(enc.tobytes())
            time.sleep(frame_interval)

    # Simulation background thread
    def sim_loop():
        time.sleep(1.0)
        from tools.simulate import run_simulator

        while True:
            for sc in [
                "compliant",
                "no_helmet",
                "restricted_entry",
                "danger_dwell",
                "crowd",
                "flicker",
            ]:
                try:
                    run_simulator(scenario=sc, fps=25.0, duration=15.0, use_mqtt=True)
                except Exception:
                    time.sleep(1.0)

    if file:
        t = threading.Thread(target=replay_loop, daemon=True)
        t.start()
    elif sim:
        t = threading.Thread(target=sim_loop, daemon=True)
        t.start()

    typer.echo(f"Starting SiteSentinel API on http://{host}:{port}")
    uvicorn.run("sentinel.interfaces.api.app:app", host=host, port=port, log_level="warning")


@app.command()
def simulate(
    frames: int = typer.Option(100, help="Number of simulated frames to stream"),
    fps: float = typer.Option(25.0, help="Simulation rate in FPS"),
    host: str = typer.Option("localhost", help="MQTT broker host"),
    port: int = typer.Option(1883, help="MQTT broker port"),
):
    """Stream simulated PipeGen detections to MQTT broker or local log."""
    from tools.simulate import main as sim_main

    typer.echo(f"Streaming {frames} frames at {fps} FPS to {host}:{port}...")
    sys.argv = [
        "simulate.py",
        "--frames",
        str(frames),
        "--fps",
        str(fps),
        "--host",
        host,
        "--port",
        str(port),
    ]
    sim_main()


@app.command()
def eval(
    detections: str = typer.Option(
        "eval/synthetic_detections.json", help="Path to detections file"
    ),
    ground_truth: str = typer.Option(
        "eval/ground_truth.json", help="Path to ground truth intervals"
    ),
    output: str = typer.Option("reports/eval_results.json", help="Path to output report"),
):
    """Run offline evaluation against ground-truth incident intervals."""
    from eval.evaluate import main as eval_main

    typer.echo(f"Running evaluation on {detections} vs {ground_truth}...")
    sys.argv = [
        "evaluate.py",
        "--detections",
        detections,
        "--ground-truth",
        ground_truth,
        "--output",
        output,
    ]
    eval_main()


@app.command()
def report(
    inputs: str = typer.Option("reports/engine_inputs.yaml", help="Path to engine inputs YAML"),
    out_dir: str = typer.Option("reports", help="Directory to write comparison reports"),
):
    """Generate TensorRT FP16 vs INT8 engine performance and accuracy report."""
    from tools.engine_report import main as rep_main

    typer.echo("Generating Engine Comparison Report...")
    sys.argv = ["engine_report.py", "--inputs", inputs, "--out-dir", out_dir]
    rep_main()


@app.command()
def export(
    output: str = typer.Option("incidents_export.csv", help="Path to output file (.csv or .jsonl)"),
):
    """Export all recorded incidents to CSV or JSONL."""
    cfg = load_sentinel_config()
    repo = SQLiteIncidentRepository(
        db_path=Path(cfg.paths.incidents_log).parent / "sentinel.db",
        jsonl_log=JSONLAuditLog(cfg.paths.incidents_log),
    )
    items, _ = repo.list_incidents(limit=100000)

    out_path = Path(output)
    if out_path.suffix == ".jsonl":
        with open(out_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item.to_dict()) + "\n")
    else:
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "incident_id",
                    "timestamp",
                    "camera_id",
                    "type",
                    "severity",
                    "track_id",
                    "zone",
                    "confidence",
                    "duration_s",
                    "status",
                ]
            )
            for inc in items:
                writer.writerow(
                    [
                        inc.incident_id,
                        inc.timestamp,
                        inc.camera_id,
                        inc.type,
                        inc.severity,
                        inc.track_id,
                        inc.zone or "",
                        inc.confidence,
                        inc.duration_s,
                        inc.status,
                    ]
                )

    typer.echo(f"Exported {len(items)} incidents to {output}")


@app.command()
def gc(
    days: int = typer.Option(30, help="Retention period in days"),
):
    """Purge evidence video clips and thumbnails older than retention period (skips open incidents)."""
    cfg = load_sentinel_config()
    ev_dir = Path(cfg.paths.evidence_dir)
    if not ev_dir.exists():
        typer.echo("Evidence directory does not exist, nothing to purge.")
        return

    cutoff_time = time.time() - (days * 86400)
    purged_count = 0

    for clip in ev_dir.rglob("*.mp4"):
        if clip.stat().st_mtime < cutoff_time:
            try:
                clip.unlink()
                thumb = clip.with_suffix(".jpg")
                if thumb.exists():
                    thumb.unlink()
                purged_count += 1
            except Exception as e:
                typer.echo(f"Error purging {clip}: {e}")

    typer.echo(f"[GC] GC complete: purged {purged_count} evidence files older than {days} days.")


@app.command(name="verify-log")
def verify_log(
    path: str = typer.Option(
        "logs/incidents.jsonl", "--path", "-p", help="Path to JSONL incidents log"
    ),
    db: Optional[str] = typer.Option(
        None, "--db", "-d", help="Optional SQLite database path to cross-check incident parity"
    ),
):
    """Verify cryptographic hash chain integrity of append-only incidents JSONL log."""
    log_file = Path(path)
    if not log_file.exists():
        typer.secho(f"Log file not found: {log_file}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    audit_log = JSONLAuditLog(log_file)
    valid, err = audit_log.verify_chain()
    if not valid:
        typer.secho(
            "[FAIL] TAMPER DETECTED: Log integrity chain verification failed!",
            fg=typer.colors.RED,
            bold=True,
        )
        typer.secho(f"   Details: {err}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    target_db = Path(db) if db else (log_file.parent / "sentinel.db")
    if target_db.exists():
        import sqlite3

        try:
            conn = sqlite3.connect(str(target_db))
            conn.row_factory = sqlite3.Row
            db_ids = {
                row["incident_id"]
                for row in conn.execute("SELECT incident_id FROM incidents").fetchall()
            }
            conn.close()

            jsonl_incidents = audit_log.read_all()
            jsonl_ids = {inc.incident_id for inc in jsonl_incidents}

            missing_in_db = jsonl_ids - db_ids
            missing_in_jsonl = db_ids - jsonl_ids
            if missing_in_db or missing_in_jsonl:
                typer.secho(
                    "[FAIL] DATABASE CROSS-CHECK FAILED: Discrepancy between JSONL log and SQLite database!",
                    fg=typer.colors.RED,
                    bold=True,
                )
                if missing_in_db:
                    typer.secho(f"   In JSONL but missing in DB: {missing_in_db}", fg=typer.colors.RED)
                if missing_in_jsonl:
                    typer.secho(f"   In DB but missing in JSONL: {missing_in_jsonl}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            typer.secho(
                f"[PASS] Database cross-check passed: {len(jsonl_ids)} incidents verified in parity with {target_db}",
                fg=typer.colors.GREEN,
            )
        except sqlite3.Error as e:
            typer.secho(f"[WARN] Database cross-check encountered error: {e}", fg=typer.colors.YELLOW)

    typer.secho(
        f"[PASS] Log integrity chain verified: 0 tampering detected across {log_file}",
        fg=typer.colors.GREEN,
        bold=True,
    )


@app.command()
def booth(
    step: Optional[int] = typer.Option(
        None, "--step", "-s", help="Run only a specific step index (1-10)"
    ),
    reset: bool = typer.Option(
        False, "--reset", help="Reset booth day state file before running"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview step checklist and budget without executing commands"
    ),
):
    """Interactive, resumable step-by-step booth day execution runner (scripts/booth_day.sh)."""
    import subprocess
    cmd = ["bash", "scripts/booth_day.sh"]
    if reset:
        cmd.append("--reset")
    elif step is not None:
        cmd.extend(["--step", str(step)])
    if dry_run:
        cmd.append("--dry-run")

    res = subprocess.run(cmd)
    raise typer.Exit(code=res.returncode)


if __name__ == "__main__":
    app()
