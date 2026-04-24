#!/usr/bin/env bash
# Locust load test — configurable threshold.
# PLAN.md target: 500 users, p95 < 3s; defaults here are dev-friendly.
#
# Env:
#   USERS           (default: 100)
#   SPAWN_RATE      (default: 20 users/sec)
#   RUN_TIME        (default: 2m)
#   HOST            (default: http://localhost)
#   P95_MS          (default: 5000 — fail if p95 exceeds this)
#
# For PLAN.md sign-off run:
#   USERS=500 P95_MS=3000 RUN_TIME=5m ./scripts/loadtest.sh

set -euo pipefail

USERS="${USERS:-100}"
SPAWN_RATE="${SPAWN_RATE:-20}"
RUN_TIME="${RUN_TIME:-2m}"
HOST="${HOST:-http://localhost}"
P95_MS="${P95_MS:-5000}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCUSTFILE="${SCRIPT_DIR}/locustfile.py"

echo "[loadtest] host=${HOST} users=${USERS} rate=${SPAWN_RATE}/s time=${RUN_TIME} p95_limit=${P95_MS}ms"

if ! command -v locust >/dev/null 2>&1; then
  echo "[loadtest] locust not installed — pip install locust"
  exit 2
fi

CSV_PREFIX="${SCRIPT_DIR}/../reports/locust-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$(dirname "$CSV_PREFIX")"

locust \
  -f "$LOCUSTFILE" \
  --host "$HOST" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME" \
  --headless \
  --csv "$CSV_PREFIX"

STATS_CSV="${CSV_PREFIX}_stats.csv"
if [[ ! -f "$STATS_CSV" ]]; then
  echo "[loadtest] stats csv missing at ${STATS_CSV}"
  exit 3
fi

# Aggregated row is named "Aggregated"; extract its p95.
AGG_P95=$(awk -F',' '$2=="Aggregated"{gsub(/"/,""); print $18}' "$STATS_CSV")
echo "[loadtest] aggregated p95=${AGG_P95}ms limit=${P95_MS}ms"

if [[ -z "$AGG_P95" ]]; then
  echo "[loadtest] could not parse p95 — inspect ${STATS_CSV}"
  exit 4
fi

if (( $(echo "$AGG_P95 > $P95_MS" | bc -l) )); then
  echo "[loadtest] FAIL — p95 ${AGG_P95}ms exceeds ${P95_MS}ms"
  exit 1
fi

echo "[loadtest] PASS"
