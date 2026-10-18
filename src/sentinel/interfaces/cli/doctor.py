"""SiteSentinel diagnostic doctor: checks deps, services, hashes, GPU, disk, ports."""

from __future__ import annotations

import hashlib
import importlib
import shutil
import socket
from pathlib import Path
from typing import Any, Dict, Tuple

import psutil

from sentinel.config import load_sentinel_config


def check_python_dependencies() -> Tuple[bool, str, str]:
    """Verifies all mandatory Python packages are installed."""
    required = [
        "fastapi",
        "pydantic",
        "cv2",
        "shapely",
        "paho.mqtt",
        "numpy",
        "psutil",
        "typer",
        "hypothesis",
        "pytest",
    ]
    missing = []
    for pkg in required:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        return (
            False,
            f"Missing Python packages: {', '.join(missing)}",
            "Run: pip install -r requirements.txt",
        )
    return True, f"All {len(required)} core packages installed", ""


def check_pipegen_export_hash() -> Tuple[bool, str, str]:
    """Verifies pipegen/export/.manifest.sha256 integrity."""
    manifest_file = Path("pipegen/export/.manifest.sha256")
    if not manifest_file.exists():
        return (
            False,
            "Manifest file 'pipegen/export/.manifest.sha256' missing",
            "Run: shasum -a 256 pipegen/export/* > pipegen/export/.manifest.sha256",
        )

    lines = [
        line.strip()
        for line in manifest_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        return False, "Manifest file is empty", "Regenerate manifest for pipegen/export files"

    export_dir = Path("pipegen/export")
    real_files = [
        f for f in export_dir.iterdir()
        if f.is_file() and f.name not in {".gitkeep", ".manifest.sha256"}
    ]
    if not real_files:
        return (
            False,
            "pipegen/export contains only .gitkeep (status PENDING - no real export present)",
            "Ingest real PipeGen export via: ./scripts/ingest_pipegen_export.sh <export_path>",
        )

    for line in lines:
        expected_hash, rel_path = line.split(maxsplit=1)
        rel_path = rel_path.strip()
        if rel_path.startswith("./"):
            rel_path = rel_path[2:]
        target = export_dir / rel_path
        if not target.exists():
            return (
                False,
                f"Export file missing: {rel_path}",
                "Restore pipegen/export files from repository origin",
            )
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            return (
                False,
                f"Hash mismatch for {rel_path}",
                "Do not edit pipegen/export; revert modifications",
            )

    return True, f"PipeGen export intact ({len(real_files)} real files verified)", ""


def check_mosquitto_reachable() -> Tuple[bool, str, str]:
    """Checks if configured MQTT broker is accepting connections."""
    cfg = load_sentinel_config()
    host = cfg.mqtt.host
    port = cfg.mqtt.port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((host, port))
        s.close()
        return True, f"Mosquitto reachable at {host}:{port}", ""
    except Exception:
        return (
            False,
            f"Mosquitto unreachable at {host}:{port}",
            "Start broker: docker compose up -d mosquitto",
        )


def check_gpu_presence() -> Tuple[bool, str, str]:
    """Checks if NVIDIA GPU and nvidia-smi are available."""
    if shutil.which("nvidia-smi"):
        return True, "NVIDIA GPU detected via nvidia-smi", ""
    return (
        False,
        "No GPU detected (CPU mode active)",
        "Hardware runs require NVIDIA GPU + TensorRT; CPU mode fine for test/judge",
    )


def check_disk_space() -> Tuple[bool, str, str]:
    """Checks available disk space in project workspace."""
    usage = psutil.disk_usage(".")
    free_gb = round(usage.free / (1024**3), 2)
    if free_gb < 2.0:
        return (
            False,
            f"Low disk space: {free_gb} GB free",
            "Free up at least 2 GB for evidence recording",
        )
    return True, f"Disk space adequate: {free_gb} GB free", ""


def check_port_free(port: int = 8000) -> Tuple[bool, str, str]:
    """Checks if API port is free."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind(("0.0.0.0", port))
        s.close()
        return True, f"Port {port} is free", ""
    except Exception:
        return (
            False,
            f"Port {port} is currently in use",
            f"Stop running process on port {port} or configure api.port in sentinel.yaml",
        )


def run_diagnostics() -> Dict[str, Any]:
    """Runs all doctor diagnostic checks and returns summary dict."""
    checks = [
        ("Python Dependencies", check_python_dependencies()),
        ("PipeGen Export Integrity", check_pipegen_export_hash()),
        ("Mosquitto Broker", check_mosquitto_reachable()),
        ("GPU Hardware", check_gpu_presence()),
        ("Disk Space", check_disk_space()),
        ("API Port (8000)", check_port_free(8000)),
    ]

    results = []
    all_ok = True
    for name, (ok, msg, fix) in checks:
        if not ok and name != "GPU Hardware" and name != "Mosquitto Broker":
            all_ok = False
        results.append({"check": name, "ok": ok, "message": msg, "fix": fix})

    return {"status": "ok" if all_ok else "warn", "checks": results}
