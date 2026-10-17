"""System hardware and environment telemetry probe implementing SystemProbe port."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import psutil


class LocalSystemProbe:
    """Probes host hardware, system resources, and optional GPU metrics."""

    def __init__(self, evidence_dir: Path | str = "evidence") -> None:
        self.evidence_dir = Path(evidence_dir)
        self._process = psutil.Process(os.getpid())

    def get_gpu_metrics(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Queries nvidia-smi if present for GPU utilization (%), power (W), and temp (C)."""
        if not shutil.which("nvidia-smi"):
            return None, None, None
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,power.draw,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.0
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                util = float(parts[0]) if len(parts) > 0 and parts[0] else None
                power = float(parts[1]) if len(parts) > 1 and parts[1] else None
                temp = float(parts[2]) if len(parts) > 2 and parts[2] else None
                return util, power, temp
        except Exception:
            pass
        return None, None, None

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns structured system telemetry dictionary."""
        gpu_util, gpu_power_w, gpu_temp_c = self.get_gpu_metrics()
        mem_info = self._process.memory_info()
        cpu_pct = self._process.cpu_percent(interval=None)

        disk_free_gb: Optional[float] = None
        try:
            if self.evidence_dir.exists():
                usage = psutil.disk_usage(str(self.evidence_dir))
                disk_free_gb = round(usage.free / (1024**3), 2)
        except Exception:
            pass

        return {
            "process_cpu_pct": round(cpu_pct, 1),
            "process_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "gpu_util": gpu_util,
            "gpu_power_w": gpu_power_w,
            "gpu_temp_c": gpu_temp_c,
            "disk_free_gb": disk_free_gb,
            "has_gpu": gpu_util is not None,
        }
