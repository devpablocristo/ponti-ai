#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="${ROOT_DIR}/scripts/k6_api_benchmark.js"

export K6_BASE_URL="${K6_BASE_URL:-http://localhost:8090}"
export K6_SERVICE_KEY="${K6_SERVICE_KEY:-servicekey123}"
export K6_USER_ID="${K6_USER_ID:-k6-user}"
export K6_PROJECT_ID="${K6_PROJECT_ID:-1}"
export BENCH_DURATION="${BENCH_DURATION:-45s}"
export BENCH_VUS="${BENCH_VUS:-6}"

if command -v k6 >/dev/null 2>&1; then
  echo "[k6] running with local binary"
  exec k6 run "${SCRIPT_PATH}"
fi

if command -v docker >/dev/null 2>&1; then
  echo "[k6] local binary not found, running via docker (host network)"
  exec docker run --rm --network host \
    -v "${ROOT_DIR}/scripts:/scripts:ro" \
    -e K6_BASE_URL \
    -e K6_SERVICE_KEY \
    -e K6_USER_ID \
    -e K6_PROJECT_ID \
    -e BENCH_DURATION \
    -e BENCH_VUS \
    grafana/k6 run /scripts/k6_api_benchmark.js
fi

echo "k6 and docker are not available. Install one to run benchmarks."
exit 2
