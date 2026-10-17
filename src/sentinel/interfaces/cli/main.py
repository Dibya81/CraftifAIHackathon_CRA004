"""Typer command-line interface for SiteSentinel."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
import time
from pathlib import Path

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
    typer.echo("🔍 Running SiteSentinel System Diagnostics...\n")
    report = run_diagnostics()

    for item in report["checks"]:
        symbol = (
            "✅ [PASS]"
            if item["ok"]
            else (
                "⚠️  [WARN]"
                if "GPU" in item["check"] or "Mosquitto" in item["check"]
                else "❌ [FAIL]"
            )
        )
        typer.echo(f"{symbol} {item['check']}: {item['message']}")
        if not item["ok"] and item["fix"]:
            typer.echo(f"   💡 Recommendation: {item['fix']}")

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
    typer.echo(f"🚀 Starting SiteSentinel API on http://{host}:{port}")
    uvicorn.run(
        "sentinel.interfaces.api.app:create_app", host=host, port=port, factory=True, reload=reload
    )


@app.command()
def run(
    services: str = typer.Option("all", help="Services to run: all, api, engine, evidence"),
):
    """Run supervised SiteSentinel services."""
    from sentinel.runtime.supervisor import ProcessSupervisor

    cfg = load_sentinel_config()
    supervisor = ProcessSupervisor(config=cfg)

    async def run_api():
        config = uvicorn.Config(
            "sentinel.interfaces.api.app:create_app",
            host=cfg.api.host,
            port=cfg.api.port,
            factory=True,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        await server.serve()

    if services in {"all", "api"}:
        supervisor.register_service("api", run_api)

    typer.echo(f"🛡️  Starting SiteSentinel Supervisor ({services})...")
    try:
        asyncio.run(supervisor.start())
    except KeyboardInterrupt:
        typer.echo("\nShutting down SiteSentinel...")


@app.command()
def simulate(
    frames: int = typer.Option(100, help="Number of simulated frames to stream"),
    fps: float = typer.Option(25.0, help="Simulation rate in FPS"),
    host: str = typer.Option("localhost", help="MQTT broker host"),
    port: int = typer.Option(1883, help="MQTT broker port"),
):
    """Stream simulated PipeGen detections to MQTT broker or local log."""
    from tools.simulate import main as sim_main

    typer.echo(f"🎬 Streaming {frames} frames at {fps} FPS to {host}:{port}...")
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

    typer.echo(f"📊 Running evaluation on {detections} vs {ground_truth}...")
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

    typer.echo("📈 Generating Engine Comparison Report...")
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

    typer.echo(f"✅ Exported {len(items)} incidents to {output}")


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

    typer.echo(f"🧹 GC complete: purged {purged_count} evidence files older than {days} days.")


if __name__ == "__main__":
    app()
