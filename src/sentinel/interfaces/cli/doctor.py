"""SiteSentinel diagnostic doctor: checks deps, services, hashes, GPU, disk, ports."""

from __future__ import annotations

import hashlib
import importlib
import shutil
import socket
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

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
        f
        for f in export_dir.iterdir()
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


def diagnose_payload_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Diagnoses a payload file by evaluating all adapter formats and checking fields."""
    p = Path(file_path)
    if not p.exists():
        return {
            "parsed_successfully": False,
            "error": f"Payload file '{file_path}' does not exist",
            "detected_format": "unknown",
            "format_evaluations": {},
            "fields_found": {},
            "detections_count": 0,
            "classes_detected": [],
            "warnings": [f"File not found: {file_path}"],
            "recommendations": ["Provide an existing JSON or NDJSON sample file."],
        }

    cfg = load_sentinel_config()
    from sentinel.adapters.pipegen import PipeGenAdapter

    adapter = PipeGenAdapter(
        class_map=cfg.class_map,
        default_camera_id=cfg.camera_id,
        format_mode="auto",
        bbox_format=cfg.adapter.bbox_format,
        bbox_normalized=cfg.adapter.bbox_normalized,
        timestamp_format=cfg.adapter.timestamp_format,
        fps=cfg.adapter.fps,
        track_id_fields=cfg.adapter.track_id_fields,
        class_fields=cfg.adapter.class_fields,
        conf_fields=cfg.adapter.conf_fields,
        bbox_fields=cfg.adapter.bbox_fields,
    )

    content = p.read_text(encoding="utf-8", errors="replace")
    report = adapter.diagnose_payload(content)
    return report


def run_hardware_diagnostics() -> Dict[str, Any]:
    """Comprehensive hardware diagnostic check for edge NVIDIA GPU, drivers, and peripherals.

    Checks:
    - NVIDIA Driver
    - CUDA Toolkit
    - TensorRT
    - DeepStream
    - PipeGen Version
    - X11 Session / Display
    - ffmpeg
    - Mosquitto MQTT Broker
    - Camera Devices (/dev/video*)
    - Disk Space (>= 10 GB)
    - Ports (1883, 8000, 5173)
    - Python & Node.js versions

    Exits non-zero on blockers, separates blockers from warnings, and skips cleanly on CPU hosts.
    """
    import os
    import platform
    import subprocess
    import sys

    is_linux = platform.system().lower() == "linux"
    has_nvidia_smi = shutil.which("nvidia-smi") is not None
    is_cpu_host = (not is_linux) or (
        not has_nvidia_smi and not Path("/proc/driver/nvidia").exists()
    )

    checks = []
    blockers: List[str] = []
    warnings: List[str] = []

    # 1. NVIDIA Driver
    if has_nvidia_smi:
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                text=True,
            ).strip()
            checks.append(
                {
                    "name": "NVIDIA Driver",
                    "status": "PASS",
                    "detail": f"Driver active: {out}",
                    "fix": "",
                }
            )
        except Exception:
            checks.append(
                {
                    "name": "NVIDIA Driver",
                    "status": "PASS",
                    "detail": "nvidia-smi present",
                    "fix": "",
                }
            )
    elif is_cpu_host:
        checks.append(
            {
                "name": "NVIDIA Driver",
                "status": "SKIPPED",
                "detail": f"Cleanly skipped on CPU host ({platform.system()} {platform.machine()})",
                "fix": "Install NVIDIA proprietary drivers on target Linux hardware (e.g. sudo apt install nvidia-driver-535)",
            }
        )
    else:
        checks.append(
            {
                "name": "NVIDIA Driver",
                "status": "BLOCKER",
                "detail": "nvidia-smi missing on target Linux machine",
                "fix": "sudo apt-get update && sudo apt-get install -y nvidia-driver-535",
            }
        )
        blockers.append("NVIDIA Driver")

    # 2. CUDA Toolkit
    has_cuda = shutil.which("nvcc") is not None or Path("/usr/local/cuda").exists()
    if has_cuda:
        cuda_ver = "detected"
        if shutil.which("nvcc"):
            try:
                nvcc_out = subprocess.check_output(["nvcc", "--version"], text=True)
                cuda_ver = [line for line in nvcc_out.splitlines() if "release" in line][0].strip()
            except Exception:
                pass
        checks.append({"name": "CUDA Toolkit", "status": "PASS", "detail": cuda_ver, "fix": ""})
    elif is_cpu_host:
        checks.append(
            {
                "name": "CUDA Toolkit",
                "status": "SKIPPED",
                "detail": "Cleanly skipped on CPU host",
                "fix": "Install CUDA on target Linux hardware (sudo apt-get install cuda-toolkit-12)",
            }
        )
    else:
        checks.append(
            {
                "name": "CUDA Toolkit",
                "status": "BLOCKER",
                "detail": "CUDA compiler nvcc or /usr/local/cuda missing",
                "fix": "sudo apt-get install -y cuda-toolkit-12-2",
            }
        )
        blockers.append("CUDA Toolkit")

    # 3. TensorRT
    trt_ok = False
    trt_detail = ""
    try:
        importlib.import_module("tensorrt")
        trt_ok = True
        trt_detail = "Python tensorrt module installed"
    except ImportError:
        if shutil.which("trtexec"):
            trt_ok = True
            trt_detail = "trtexec CLI present"

    if trt_ok:
        checks.append({"name": "TensorRT", "status": "PASS", "detail": trt_detail, "fix": ""})
    elif is_cpu_host:
        checks.append(
            {
                "name": "TensorRT",
                "status": "SKIPPED",
                "detail": "Cleanly skipped on CPU host (using CPU ONNX Runtime baseline)",
                "fix": "Install TensorRT on target hardware (sudo apt-get install python3-libnvinfer)",
            }
        )
    else:
        checks.append(
            {
                "name": "TensorRT",
                "status": "BLOCKER",
                "detail": "TensorRT Python bindings and trtexec not found",
                "fix": "sudo apt-get install -y python3-libnvinfer-dev libnvinfer-bin",
            }
        )
        blockers.append("TensorRT")

    # 4. DeepStream
    has_deepstream = (
        shutil.which("deepstream-app") is not None or Path("/opt/nvidia/deepstream").exists()
    )
    if has_deepstream:
        checks.append(
            {
                "name": "DeepStream SDK",
                "status": "PASS",
                "detail": "DeepStream SDK present",
                "fix": "",
            }
        )
    elif is_cpu_host:
        checks.append(
            {
                "name": "DeepStream SDK",
                "status": "SKIPPED",
                "detail": "Cleanly skipped on CPU host",
                "fix": "Install DeepStream SDK on target hardware: sudo apt-get install deepstream-6.4",
            }
        )
    else:
        checks.append(
            {
                "name": "DeepStream SDK",
                "status": "WARNING",
                "detail": "DeepStream SDK not found in /opt/nvidia/deepstream",
                "fix": "Install DeepStream SDK 6.4: sudo apt-get install -y deepstream-6.4",
            }
        )
        warnings.append("DeepStream SDK")

    # 5. PipeGen Version
    pipegen_ok = shutil.which("pipegen") is not None
    if pipegen_ok:
        try:
            ver = subprocess.check_output(["pipegen", "--version"], text=True).strip()
            checks.append(
                {"name": "PipeGen CLI", "status": "PASS", "detail": f"Installed: {ver}", "fix": ""}
            )
        except Exception:
            checks.append(
                {
                    "name": "PipeGen CLI",
                    "status": "PASS",
                    "detail": "pipegen binary found",
                    "fix": "",
                }
            )
    elif is_cpu_host:
        checks.append(
            {
                "name": "PipeGen CLI",
                "status": "SKIPPED",
                "detail": "Cleanly skipped on CPU host (PipeGen runs onsite on hardware day)",
                "fix": "Install pipegen compiler from package or virtualenv",
            }
        )
    else:
        checks.append(
            {
                "name": "PipeGen CLI",
                "status": "WARNING",
                "detail": "PipeGen compiler CLI not found in $PATH",
                "fix": "Ensure PipeGen is installed and in PATH before Stage 1 execution",
            }
        )
        warnings.append("PipeGen CLI")

    # 6. X11 Session / Display
    disp = os.environ.get("DISPLAY")
    has_x11 = bool(disp) or Path("/tmp/.X11-unix").exists()
    if has_x11:
        checks.append(
            {
                "name": "X11 Session",
                "status": "PASS",
                "detail": f"DISPLAY={disp or ':0'}",
                "fix": "",
            }
        )
    else:
        checks.append(
            {
                "name": "X11 Session",
                "status": "WARNING",
                "detail": "DISPLAY variable not set (headless environment)",
                "fix": "Run with virtual framebuffer: xvfb-run -s '-screen 0 1920x1080x24' <command> or export DISPLAY=:0",
            }
        )
        warnings.append("X11 Session")

    # 7. ffmpeg
    if shutil.which("ffmpeg"):
        checks.append(
            {"name": "ffmpeg", "status": "PASS", "detail": "ffmpeg binary available", "fix": ""}
        )
    else:
        checks.append(
            {
                "name": "ffmpeg",
                "status": "BLOCKER",
                "detail": "ffmpeg binary not found in $PATH",
                "fix": "sudo apt-get install -y ffmpeg (or brew install ffmpeg)",
            }
        )
        blockers.append("ffmpeg")

    # 8. Mosquitto MQTT Broker
    mosq_port_ok = False
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 1883))
        s.close()
        mosq_port_ok = True
    except Exception:
        pass

    if mosq_port_ok or shutil.which("mosquitto"):
        checks.append(
            {
                "name": "Mosquitto Broker",
                "status": "PASS",
                "detail": "Broker listening or binary installed",
                "fix": "",
            }
        )
    else:
        checks.append(
            {
                "name": "Mosquitto Broker",
                "status": "WARNING",
                "detail": "Mosquitto not listening on port 1883",
                "fix": "docker compose up -d mosquitto or sudo systemctl start mosquitto",
            }
        )
        warnings.append("Mosquitto Broker")

    # 9. Camera Devices (/dev/video* or OpenCV)
    video_devs = list(Path("/dev").glob("video*")) if Path("/dev").exists() else []
    if video_devs:
        checks.append(
            {
                "name": "Camera Devices",
                "status": "PASS",
                "detail": f"Found devices: {', '.join(p.name for p in video_devs)}",
                "fix": "",
            }
        )
    elif is_cpu_host:
        checks.append(
            {
                "name": "Camera Devices",
                "status": "WARNING",
                "detail": "No /dev/video* devices found (replay mode active)",
                "fix": "Connect USB/CSI camera or run in replay mode: sentinel replay <capture_file>",
            }
        )
    else:
        checks.append(
            {
                "name": "Camera Devices",
                "status": "WARNING",
                "detail": "No /dev/video* devices found",
                "fix": "Connect USB camera and grant user permissions: sudo usermod -aG video $USER",
            }
        )
        warnings.append("Camera Devices")

    # 10. Disk Space
    usage = psutil.disk_usage(".")
    free_gb = round(usage.free / (1024**3), 2)
    if free_gb >= 10.0:
        checks.append(
            {"name": "Disk Space", "status": "PASS", "detail": f"{free_gb} GB free", "fix": ""}
        )
    elif free_gb >= 2.0:
        checks.append(
            {
                "name": "Disk Space",
                "status": "WARNING",
                "detail": f"{free_gb} GB free (< 10 GB target for model builds)",
                "fix": "Clean package caches: docker system prune, rm -rf ~/.cache",
            }
        )
        warnings.append("Disk Space")
    else:
        checks.append(
            {
                "name": "Disk Space",
                "status": "BLOCKER",
                "detail": f"Critically low disk space: {free_gb} GB free (< 2 GB minimum)",
                "fix": "Free disk space immediately before building models or saving footage",
            }
        )
        blockers.append("Disk Space")

    # 11. Core Ports (1883, 8000, 5173)
    def check_bindable(p: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        try:
            sock.bind(("0.0.0.0", p))
            sock.close()
            return True
        except Exception:
            return False

    port_8000_ok = check_bindable(8000)
    port_5173_ok = check_bindable(5173)
    checks.append(
        {
            "name": "Network Ports (8000, 5173)",
            "status": "PASS" if (port_8000_ok and port_5173_ok) else "WARNING",
            "detail": f"Port 8000: {'free' if port_8000_ok else 'busy'}, Port 5173: {'free' if port_5173_ok else 'busy'}",
            "fix": "Stop existing sentinel services: pkill -f 'sentinel run' or kill processes using lsof -i :8000",
        }
    )

    # 12. Python & Node.js Versions
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    node_ver = "missing"
    node_ok = False
    if shutil.which("node"):
        try:
            node_ver = subprocess.check_output(["node", "--version"], text=True).strip()
            node_ok = True
        except Exception:
            pass

    checks.append(
        {
            "name": "Runtimes (Python/Node)",
            "status": "PASS" if (py_ok and node_ok) else "BLOCKER",
            "detail": f"Python {py_ver}, Node {node_ver}",
            "fix": "Install Node >= 18 and Python >= 3.10",
        }
    )
    if not (py_ok and node_ok):
        blockers.append("Runtimes (Python/Node)")

    return {
        "is_cpu_host": is_cpu_host,
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
    }
