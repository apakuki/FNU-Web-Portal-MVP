#!/usr/bin/env bash
# Lightweight uptime monitor for the FNU portal.
#
# Intended to run from cron (every 1 minute) on a separate host. Pages the
# on-call alias after two consecutive failures. For richer monitoring, use a
# third-party service (UptimeRobot, StatusCake, Pingdom) instead.
#
# Usage:
#   PORTAL_URL=https://portal.fnu.ac.fj \
#   ALERT_EMAIL=ops@fnu.ac.fj \
#   STATE_DIR=/var/lib/fnu-uptime \
#     ./scripts/uptime_monitor.sh

set -uo pipefail

PORTAL_URL="${PORTAL_URL:-http://localhost}"
ALERT_EMAIL="${ALERT_EMAIL:-ops@fnu.ac.fj}"
STATE_DIR="${STATE_DIR:-/tmp/fnu-uptime}"
TIMEOUT="${TIMEOUT:-10}"
FAIL_THRESHOLD="${FAIL_THRESHOLD:-2}"

mkdir -p "$STATE_DIR"
FAIL_FILE="$STATE_DIR/fail_count"
ALERTED_FILE="$STATE_DIR/alerted"

health="$(curl -fsSL --max-time "$TIMEOUT" "$PORTAL_URL/api/health" 2>&1 || true)"
status_ok="$(echo "$health" | grep -c '"status":"ok"' || true)"

if [ "$status_ok" = "1" ]; then
    # Clear state on recovery; send recovery alert if we had paged.
    if [ -f "$ALERTED_FILE" ]; then
        printf 'Subject: [FNU PORTAL] Recovered\n\nPortal %s is healthy again at %s UTC.\n' \
            "$PORTAL_URL" "$(date -u)" | sendmail -t "$ALERT_EMAIL" 2>/dev/null || true
        rm -f "$ALERTED_FILE"
    fi
    echo 0 > "$FAIL_FILE"
    exit 0
fi

# Failure path
prev="$(cat "$FAIL_FILE" 2>/dev/null || echo 0)"
count=$((prev + 1))
echo "$count" > "$FAIL_FILE"

echo "[$(date -u)] Health check failed (#$count). Response: $health" >&2

if [ "$count" -ge "$FAIL_THRESHOLD" ] && [ ! -f "$ALERTED_FILE" ]; then
    printf 'Subject: [FNU PORTAL] Down - %d consecutive failures\n\nPortal %s is failing /api/health since %s.\n\nLatest response:\n%s\n\nRunbook: docs/INCIDENT_RESPONSE.md\n' \
        "$count" "$PORTAL_URL" "$(date -u)" "$health" | sendmail -t "$ALERT_EMAIL" 2>/dev/null || true
    touch "$ALERTED_FILE"
fi

exit 1
