"""SiteSentinel: Edge Engine Comparison Report Generator.

Parses PipeGen speed reports and generates machine-readable JSON and human-readable Markdown comparison reports.

IMPORTANT: This tool REFUSES to render any performance number unless the corresponding
entry in engine_inputs.yaml has BOTH source_file and sha256 pointing at a
real raw report in evidence/pipegen/. Missing or null inputs produce a
PENDING document — not a fabricated one.

Usage:
  python tools/engine_report.py --inputs reports/engine_inputs.yaml --out-dir reports
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class EngineMetrics:
    precision: str
    framework: str
    fps: float
    inference_latency_ms: float
    end_to_end_latency_ms: float
    vram_mb: float
    gpu_power_w: float
    map_50: float
    speedup_vs_baseline: float = 1.0
    efficiency_fps_per_watt: float = 0.0


@dataclass
class EngineComparisonSummary:
    timestamp: str
    status: str
    device: str
    power_mode: str
    input_resolution: List[int]
    calibration_dataset: str
    provenance: str
    models: Dict[str, Optional[EngineMetrics]]
    int8_speedup_vs_fp16: Optional[float] = None
    int8_map_drop_vs_fp16: Optional[float] = None
    vram_reduction_pct: Optional[float] = None
    power_reduction_pct: Optional[float] = None
    ac6_speedup_pass: Optional[bool] = None
    ac6_map_pass: Optional[bool] = None
    ac6_overall_pass: Optional[bool] = None
    summary_text: str = ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_engine_inputs(yaml_path: str | Path) -> Dict[str, Any]:
    p = Path(yaml_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        raise FileNotFoundError(f"Engine inputs file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "models" not in data:
        raise ValueError(f"Invalid engine inputs file: missing 'models' section in {p}")
    return data


def validate_model_entry(key: str, m: Dict[str, Any]) -> List[str]:
    """Return list of validation errors for a model entry."""
    errors = []
    src = m.get("source_file")
    sha = m.get("sha256")
    fps = m.get("fps")

    if fps is not None:
        if not src:
            errors.append(f"[{key}] fps is defined but source_file is missing.")
        if not sha:
            errors.append(f"[{key}] fps is defined but sha256 is missing.")
        if src and sha:
            src_path = REPO_ROOT / src
            if not src_path.exists():
                errors.append(f"[{key}] source_file '{src}' does not exist on disk.")
            else:
                actual = sha256_file(src_path)
                if actual != sha:
                    errors.append(f"[{key}] sha256 mismatch for '{src}'.")
    return errors


def compute_engine_comparison(data: Dict[str, Any], validate_sources: bool = False) -> EngineComparisonSummary:
    """Compute engine comparison summary from dictionary data."""
    models_raw = data.get("models", {})
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Check if this is pending / empty data
    has_values = any(
        isinstance(m, dict) and m.get("fps") is not None
        for m in models_raw.values()
    )
    
    if not has_values:
        return EngineComparisonSummary(
            timestamp=now_ts,
            status="PENDING",
            device=data.get("device", "PENDING"),
            power_mode=data.get("power_mode", "PENDING"),
            input_resolution=data.get("input_resolution", [1920, 1080]),
            calibration_dataset=data.get("calibration_dataset", "PENDING"),
            provenance="PENDING",
            models={"fp32": None, "fp16": None, "int8": None},
            int8_speedup_vs_fp16=None,
            int8_map_drop_vs_fp16=None,
            vram_reduction_pct=None,
            power_reduction_pct=None,
            ac6_speedup_pass=None,
            ac6_map_pass=None,
            ac6_overall_pass=None,
            summary_text="PENDING: No real engine speed reports have been committed.",
        )

    if validate_sources:
        for key, m in models_raw.items():
            if isinstance(m, dict):
                errs = validate_model_entry(key, m)
                if errs:
                    raise ValueError(f"Un-sourced engine inputs detected: {'; '.join(errs)}")

    processed_models: Dict[str, Optional[EngineMetrics]] = {}
    for key, m in models_raw.items():
        if not isinstance(m, dict) or m.get("fps") is None:
            processed_models[key] = None
            continue
            
        fps = float(m["fps"])
        power = float(m.get("gpu_power_w", 0.0))
        eff = round(fps / power, 2) if power > 0 else 0.0
        
        processed_models[key] = EngineMetrics(
            precision=str(m.get("precision", key.upper())),
            framework=str(m.get("framework", "")),
            fps=fps,
            inference_latency_ms=float(m.get("inference_latency_ms", 0.0)),
            end_to_end_latency_ms=float(m.get("end_to_end_latency_ms", 0.0)),
            vram_mb=float(m.get("vram_mb", 0.0)),
            gpu_power_w=power,
            map_50=float(m.get("map_50", 0.0)),
            speedup_vs_baseline=float(m.get("speedup_vs_baseline", 1.0)),
            efficiency_fps_per_watt=eff,
        )

    fp16 = processed_models.get("fp16")
    int8 = processed_models.get("int8")

    if not fp16 or not int8:
        raise ValueError("Engine inputs must contain both 'fp16' and 'int8' models for comparison.")

    speedup_vs_fp16 = round(int8.fps / fp16.fps, 2)
    map_drop = round(fp16.map_50 - int8.map_50, 4)
    vram_red = round(((fp16.vram_mb - int8.vram_mb) / fp16.vram_mb) * 100.0, 1) if fp16.vram_mb > 0 else 0.0
    power_red = round(((fp16.gpu_power_w - int8.gpu_power_w) / fp16.gpu_power_w) * 100.0, 1) if fp16.gpu_power_w > 0 else 0.0

    speedup_pass = bool(speedup_vs_fp16 >= 1.25)
    map_pass = bool(map_drop <= 0.02)
    ac6_pass = bool(speedup_pass and map_pass)

    summary_text = (
        f"INT8 throughput speedup: {speedup_vs_fp16}x vs FP16 "
        f"({int8.fps:.1f} FPS vs {fp16.fps:.1f} FPS), mAP drop {map_drop:.3f}, "
        f"VRAM reduction {vram_red}%."
    )

    return EngineComparisonSummary(
        timestamp=now_ts,
        status="MEASURED" if data.get("provenance") == "MEASURED" else "SIMULATED",
        device=str(data.get("device", "NVIDIA Edge Device")),
        power_mode=str(data.get("power_mode", "Default")),
        input_resolution=data.get("input_resolution", [1920, 1080]),
        calibration_dataset=str(data.get("calibration_dataset", "models/calibration")),
        provenance=str(data.get("provenance", "SIMULATED")),
        models=processed_models,
        int8_speedup_vs_fp16=speedup_vs_fp16,
        int8_map_drop_vs_fp16=map_drop,
        vram_reduction_pct=vram_red,
        power_reduction_pct=power_red,
        ac6_speedup_pass=speedup_pass,
        ac6_map_pass=map_pass,
        ac6_overall_pass=ac6_pass,
        summary_text=summary_text,
    )


def generate_reports(
    summary: EngineComparisonSummary,
    output_dir: str | Path = "reports",
) -> Tuple[Path, Path]:
    """Write engine_comparison.json and engine_comparison.md."""
    out_p = Path(output_dir)
    if not out_p.is_absolute():
        out_p = REPO_ROOT / out_p
    out_p.mkdir(parents=True, exist_ok=True)

    json_path = out_p / "engine_comparison.json"
    md_path = out_p / "engine_comparison.md"

    # Write JSON report
    data_dict = asdict(summary)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2)

    # Write Markdown report
    if summary.status == "PENDING":
        md_lines = [
            "# SiteSentinel: TensorRT Engine Optimization Comparison",
            "",
            f"**Generated**: {summary.timestamp}  ",
            "**Status**: PENDING  ",
            "",
            "> [!IMPORTANT]",
            "> **No engine speed reports exist yet.**",
            "> All FPS, latency, VRAM, and power numbers are PENDING.",
            "> No hardware device name is listed because no raw log exists.",
            ">",
            "> To populate this report:",
            "> 1. Obtain a machine with PipeGen installed and a compatible GPU.",
            "> 2. Run `scripts/verify_hardware.sh` — it captures raw logs automatically.",
            "> 3. Ingest real logs using `tools/engine_report.py`.",
            "",
            "## Ledger References",
            "",
            "| Claim | Ledger ID | Status |",
            "|-------|-----------|--------|",
            "| FP32 FPS | ENGINE-FPS-FP32 | PENDING |",
            "| FP16 FPS | ENGINE-FPS-FP16 | PENDING |",
            "| INT8 FPS | ENGINE-FPS-INT8 | PENDING |",
            "| INT8 speedup vs FP16 | ENGINE-INT8-SPEEDUP | PENDING |",
            "| INT8 mAP drop | ENGINE-INT8-MAP-DROP | PENDING |",
            "| VRAM footprint | ENGINE-VRAM-INT8 | PENDING |",
            "| Hardware platform | HARDWARE-PLATFORM | PENDING |",
        ]
    else:
        res_str = f"{summary.input_resolution[0]}x{summary.input_resolution[1]}" if summary.input_resolution else "1080p"
        md_lines = [
            "# SiteSentinel: TensorRT Engine Optimization Comparison",
            "",
            f"**Date**: {summary.timestamp}  ",
            f"**Target Silicon**: `{summary.device}` ({summary.power_mode} profile)  ",
            f"**Input Stream**: `{res_str}`  ",
            f"**Status**: {summary.status}  ",
            f"**Data Provenance**: `{summary.provenance}`  ",
            "",
            "## 1. Summary",
            "",
            summary.summary_text,
            "",
            "## 2. Acceptance Criteria Verification",
            "",
            f"- **Speedup vs FP16**: **{summary.int8_speedup_vs_fp16}x** (Target: >= 1.25x) -> {'PASS' if summary.ac6_speedup_pass else 'FAIL'}",
            f"- **Quantization mAP Drop**: **{summary.int8_map_drop_vs_fp16}** (Target: <= 0.020) -> {'PASS' if summary.ac6_map_pass else 'FAIL'}",
            f"- **Overall Status**: {'PASS' if summary.ac6_overall_pass else 'FAIL'}",
            "",
        ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Engine Report Generator")
    parser.add_argument("--inputs", type=str, default="reports/engine_inputs.yaml", help="Path to engine inputs YAML")
    parser.add_argument("--out-dir", type=str, default="reports", help="Output directory for reports")
    args = parser.parse_args()

    data = load_engine_inputs(args.inputs)
    summary = compute_engine_comparison(data, validate_sources=True)
    json_path, md_path = generate_reports(summary, output_dir=args.out_dir)
    print(f"Engine comparison reports written to:\n  - {json_path}\n  - {md_path}")


if __name__ == "__main__":
    main()
