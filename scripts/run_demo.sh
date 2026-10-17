#!/usr/bin/env bash
# One-command demo: broker, PipeGen pipeline, rule engine, API, dashboard.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f infra/docker-compose.yml up -d
( cd pipegen/export && ./run.sh ) &              # PipeGen-generated DeepStream app
python -m uvicorn src.sentinel.api:app --port 8000 &
# TODO: start rule engine process, then dashboard (npm --prefix dashboard run dev)
wait
