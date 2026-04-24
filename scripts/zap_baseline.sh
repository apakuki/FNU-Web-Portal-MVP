#!/usr/bin/env bash
# OWASP ZAP baseline passive scan against the local stack.
# Requires Docker. Start the stack first (./scripts/start.sh).
#
# Usage:
#   ./scripts/zap_baseline.sh              # scan http://localhost
#   TARGET=http://staging.fnu ./scripts/zap_baseline.sh
#
# Report lands at reports/zap-baseline-<timestamp>.html.
# Non-zero exit on high-severity findings.

set -euo pipefail

TARGET="${TARGET:-http://host.docker.internal}"
REPORT_DIR="${REPORT_DIR:-reports}"
mkdir -p "$REPORT_DIR"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$REPORT_DIR/zap-baseline-${TS}.html"

echo "[zap] target=${TARGET}"
echo "[zap] report=${REPORT}"

docker run --rm \
  -v "$(pwd)/${REPORT_DIR}:/zap/wrk:rw" \
  --network host \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
    -t "$TARGET" \
    -r "zap-baseline-${TS}.html" \
    -I
