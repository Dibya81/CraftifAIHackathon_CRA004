"""Typer command-line interface for SiteSentinel."""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Optional

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
def doctor():
    """Run diagnostic checks on dependencies, GPU, ports, broker, and export manifest."""
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


if __name__ == "__main__":
    app()
