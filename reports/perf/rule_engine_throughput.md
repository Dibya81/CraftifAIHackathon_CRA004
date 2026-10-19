# SiteSentinel Performance Benchmark Report (2026-10-19)

## Test Environment
- Host: Darwin arm64
- Python: 3.11.15
- Profiling mode: REAL CPU Profiling

## TC-26 Rule Engine Throughput (20 Persons, 25 FPS)
- **Frames Evaluated**: 500
- **Simultaneous Persons**: 20
- **Detections per Frame**: 60
- **Average Step Time**: 0.896 ms (Target < 6.0 ms)
- **p99 Step Time**: 0.963 ms (Target < 5.0 ms)
- **Max Step Time**: 1.083 ms
- **Equivalent FPS**: 1116.7 FPS
- **Core Utilization at 25 FPS**: 2.24% (Target < 15%)
- **Result**: PASS
