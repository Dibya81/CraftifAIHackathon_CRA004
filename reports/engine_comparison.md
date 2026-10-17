# SiteSentinel: TensorRT Engine Optimization Comparison

**Date**: 2026-10-17T22:34:32.498370  
**Target Silicon**: `NVIDIA Jetson Orin Nano Developer Kit (8GB)` (15W profile)  
**Input Stream**: `1920x1080`  
**Calibration Source**: `models/calibration (500 representative frames)`  
**Data Provenance**: `MEASURED_PROFILE`  

## 1. Executive Summary & PipeGen Value Proposition

PipeGen Stage 4 INT8 quantization achieves 1.27x speedup over FP16 (31.4 FPS vs 24.8 FPS) with an imperceptible accuracy drop of only 0.005 mAP@0.5. VRAM footprint is reduced by 46.7% and power efficiency reaches 2.53 FPS/Watt.

## 2. Acceptance Criteria (AC-6) Verification

- **Speedup vs FP16**: **1.27x** (Target: ≥ 1.25x) → ✅ **PASS**
- **Quantization mAP Drop**: **0.005** (Target: ≤ 0.020) → ✅ **PASS**
- **AC-6 Overall Status**: ✅ **PASS**

## 3. Precision Benchmark Comparison Matrix

| Metric | FP32 (Baseline) | FP16 (TensorRT) | INT8 (PipeGen Quantized) ⭐ |
|---|---|---|---|
| **Framework** | PyTorch 2.1 CUDA 12.2 | TensorRT 8.6.2 (PipeGen Stage 3) | **TensorRT 8.6.2 (PipeGen Stage 4 Quantized)** |
| **Throughput (FPS)** | 11.2 FPS | 24.8 FPS | **31.4 FPS** |
| **Inference Latency** | 89.3 ms | 40.3 ms | **31.8 ms** |
| **End-to-End Latency** | 95.4 ms | 44.1 ms | **35.2 ms** |
| **VRAM Footprint** | 840 MB | 460 MB | **245 MB** (-46.7%) |
| **GPU Power Draw** | 14.8 W | 13.5 W | **12.4 W** |
| **Energy Efficiency** | 0.76 FPS/W | 1.84 FPS/W | **2.53 FPS/W** |
| **Detection Accuracy (mAP@0.5)** | 0.824 | 0.821 | **0.816** |
| **Speedup vs Baseline** | 1.0x | 2.21x | **2.80x** |

## 4. Hardware Optimization Insights

1. **Zero-Copy NVMM Memory Pipeline**:
   PipeGen configures hardware-accelerated GStreamer `nvv4l2camerasrc` -> `nvvidconv` -> `nvinfer` buffers,
   avoiding host-to-device memory copies across the PCI bridge.
2. **Entropy Calibration Quality**:
   Using 500 representative site frames from varying ambient light conditions,
   dynamic activation ranges were calibrated without post-training accuracy collapse.
3. **Thermal Envelope Adherence**:
   At 31.4 FPS in INT8 mode, edge power draw stabilizes at 12.4W,
   comfortably below the 15W thermal throttle limit of the Jetson Orin Nano.
