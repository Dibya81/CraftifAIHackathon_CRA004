import json
from pathlib import Path

import pytest

from tools.engine_report import (
    compute_engine_comparison,
    generate_reports,
    load_engine_inputs,
)


def test_load_engine_inputs_valid():
    data = load_engine_inputs("reports/engine_inputs.yaml")
    assert "models" in data
    assert "fp32" in data["models"]
    assert "fp16" in data["models"]
    assert "int8" in data["models"]


def test_load_engine_inputs_missing_file():
    with pytest.raises(FileNotFoundError):
        load_engine_inputs("nonexistent_inputs.yaml")


def test_compute_engine_comparison_ac6_pass():
    mock_data = {
        "device": "NVIDIA Jetson Orin Nano",
        "power_mode": "15W",
        "models": {
            "fp32": {
                "precision": "FP32",
                "framework": "PyTorch",
                "fps": 10.0,
                "inference_latency_ms": 100.0,
                "end_to_end_latency_ms": 105.0,
                "vram_mb": 800.0,
                "gpu_power_w": 15.0,
                "map_50": 0.82,
                "speedup_vs_baseline": 1.0,
            },
            "fp16": {
                "precision": "FP16",
                "framework": "TensorRT FP16",
                "fps": 20.0,
                "inference_latency_ms": 50.0,
                "end_to_end_latency_ms": 55.0,
                "vram_mb": 400.0,
                "gpu_power_w": 13.0,
                "map_50": 0.81,
                "speedup_vs_baseline": 2.0,
            },
            "int8": {
                "precision": "INT8",
                "framework": "TensorRT INT8",
                "fps": 26.0,  # 26.0 / 20.0 = 1.3x >= 1.25x
                "inference_latency_ms": 38.0,
                "end_to_end_latency_ms": 42.0,
                "vram_mb": 200.0,
                "gpu_power_w": 12.0,
                "map_50": 0.805,  # 0.81 - 0.805 = 0.005 <= 0.02
                "speedup_vs_baseline": 2.6,
            },
        },
    }

    summary = compute_engine_comparison(mock_data)
    assert summary.int8_speedup_vs_fp16 == 1.3
    assert summary.int8_map_drop_vs_fp16 == 0.005
    assert summary.vram_reduction_pct == 50.0
    assert summary.ac6_speedup_pass is True
    assert summary.ac6_map_pass is True
    assert summary.ac6_overall_pass is True


def test_compute_engine_comparison_ac6_fail():
    mock_data = {
        "device": "NVIDIA Jetson Orin Nano",
        "power_mode": "15W",
        "models": {
            "fp16": {
                "precision": "FP16",
                "framework": "TensorRT FP16",
                "fps": 20.0,
                "inference_latency_ms": 50.0,
                "end_to_end_latency_ms": 55.0,
                "vram_mb": 400.0,
                "gpu_power_w": 13.0,
                "map_50": 0.85,
            },
            "int8": {
                "precision": "INT8",
                "framework": "TensorRT INT8",
                "fps": 21.0,  # 21 / 20 = 1.05x < 1.25x (FAILS)
                "inference_latency_ms": 47.0,
                "end_to_end_latency_ms": 50.0,
                "vram_mb": 200.0,
                "gpu_power_w": 12.0,
                "map_50": 0.80,  # 0.85 - 0.80 = 0.05 > 0.02 (FAILS)
            },
        },
    }

    summary = compute_engine_comparison(mock_data)
    assert summary.ac6_speedup_pass is False
    assert summary.ac6_map_pass is False
    assert summary.ac6_overall_pass is False


def test_generate_engine_reports(tmp_path: Path):
    data = load_engine_inputs("reports/engine_inputs.yaml")
    summary = compute_engine_comparison(data)
    json_p, md_p = generate_reports(summary, output_dir=tmp_path)

    assert json_p.exists()
    assert md_p.exists()

    with open(json_p, "r") as f:
        json_data = json.load(f)
    assert json_data["ac6_overall_pass"] is True
    assert json_data["int8_speedup_vs_fp16"] == 1.27

    with open(md_p, "r") as f:
        md_text = f.read()
    assert "- **AC-6 Overall Status**: ✅ **PASS**" in md_text
    assert "Framework" in md_text
    assert "Zero-Copy NVMM Memory Pipeline" in md_text
