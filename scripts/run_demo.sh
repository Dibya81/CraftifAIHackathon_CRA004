#!/usr/bin/env bash
# ==============================================================================
# SiteSentinel: One-Command Live Demonstration Runner
# Supervises: MQTT Broker, FastAPI Backend, WebSocket Feed, and Dashboard.
#
# Usage:
#   ./scripts/run_demo.sh            # Run with simulated multi-scenario feed (default)
#   ./scripts/run_demo.sh --sim      # Run with continuous simulation
#   ./scripts/run_demo.sh --pipegen  # Run with exported PipeGen DeepStream pipeline
#   ./scripts/run_demo.sh --file <path_to_clip>
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

MODE="sim"
PORT=8000
DASH_PORT=5173
INPUT_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --sim)
      MODE="sim"
      shift
      ;;
    --pipegen)
      MODE="pipegen"
      shift
      ;;
    --file)
      MODE="file"
      INPUT_FILE="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --dash-port)
      DASH_PORT="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: ./scripts/run_demo.sh [--sim | --pipegen | --file <video>] [--port 8000] [--dash-port 5173]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

PYTHON="${ROOT_DIR}/.venv/bin/python"
if [ ! -f "${PYTHON}" ]; then
  PYTHON="python3"
fi

PIDS=()

cleanup() {
  echo ""
  echo "🛑 Shutting down SiteSentinel demonstration services..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  # Clean up background process group
  kill -- -$$ 2>/dev/null || true
  echo "✓ All demonstration services stopped."
}

trap cleanup EXIT INT TERM

echo "======================================================================"
echo "🛡️  Starting SiteSentinel Demo (Mode: ${MODE})"
echo "======================================================================"

# 1. Check or start MQTT Broker
if nc -z localhost 1883 2>/dev/null; then
  echo "✓ MQTT Broker is already listening on port 1883."
elif command -v docker &>/dev/null && docker info &>/dev/null; then
  echo "▶ Starting Mosquitto MQTT broker via docker compose..."
  docker compose -f infra/docker-compose.yml up -d 2>/dev/null || true
  sleep 1
else
  echo "⚠️  Note: Local MQTT broker not detected on port 1883."
  echo "   (Simulator and backend will use resilient socket reconnection)"
fi

# 2. Start FastAPI Backend & WebSocket Service
echo "▶ Starting SiteSentinel FastAPI server on port ${PORT}..."
"${PYTHON}" -m uvicorn sentinel.api:app --host 0.0.0.0 --port "${PORT}" --log-level warning &
BACKEND_PID=$!
PIDS+=("${BACKEND_PID}")

# Wait for backend to become ready
echo "Waiting for API readiness..."
for i in {1..30}; do
  if curl -s "http://localhost:${PORT}/api/health" >/dev/null; then
    echo "✓ Backend API is ready."
    break
  fi
  sleep 0.5
done

# 3. Start React Dashboard
echo "▶ Starting SiteSentinel Dashboard on port ${DASH_PORT}..."
( npm --prefix dashboard run dev -- --port "${DASH_PORT}" --host >/dev/null 2>&1 ) &
DASH_PID=$!
PIDS+=("${DASH_PID}")

# 4. Start Pipeline / Detection Stream
if [ "${MODE}" == "sim" ]; then
  echo "▶ Starting continuous synthetic simulation stream (25 FPS)..."
  (
    while true; do
      for scenario in compliant no_helmet restricted_entry danger_dwell crowd flicker; do
        "${PYTHON}" tools/simulate.py --scenario "${scenario}" --duration 12 --fps 25 --no-mqtt >/dev/null 2>&1 || true
      done
    done
  ) &
  SIM_PID=$!
  PIDS+=("${SIM_PID}")
elif [ "${MODE}" == "pipegen" ]; then
  if [ -f "pipegen/export/run.sh" ]; then
    echo "▶ Launching PipeGen DeepStream pipeline..."
    ( cd pipegen/export && ./run.sh ) &
    PIPE_PID=$!
    PIDS+=("${PIPE_PID}")
  else
    echo "⚠️  pipegen/export/run.sh not found. Falling back to simulation mode."
    "${PYTHON}" tools/simulate.py --scenario compliant --duration 30 --fps 25 &
    PIDS+=($!)
  fi
elif [ "${MODE}" == "file" ]; then
  echo "▶ Processing video input: ${INPUT_FILE}..."
  "${PYTHON}" tools/simulate.py --scenario crowd --duration 30 --fps 25 --out-video "${INPUT_FILE}" &
  PIDS+=($!)
fi

echo ""
echo "======================================================================"
echo "🎉 SiteSentinel Live System Online!"
echo ""
echo "   📊 Web Dashboard:       http://localhost:${DASH_PORT}"
echo "   📡 REST API & Docs:      http://localhost:${PORT}/docs"
echo "   ⚡ System Engine Report: http://localhost:${PORT}/api/system/engine-report"
echo ""
echo "Press Ctrl+C to stop all services."
echo "======================================================================"

# Wait for child processes
wait
