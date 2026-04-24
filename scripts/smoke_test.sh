#!/usr/bin/env bash
# Production smoke test. Run from a workstation after a deployment.
#
# Usage:
#   PORTAL_URL=https://portal.fnu.ac.fj ./scripts/smoke_test.sh
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed
#   2 — usage error

set -uo pipefail

PORTAL_URL="${PORTAL_URL:-http://localhost}"
TIMEOUT="${TIMEOUT:-10}"
EXIT=0
PASS=0
FAIL=0

red() { printf '\033[31m%s\033[0m' "$1"; }
green() { printf '\033[32m%s\033[0m' "$1"; }

check() {
    local label="$1"; shift
    if "$@"; then
        printf "  %s %s\n" "$(green OK)" "$label"
        PASS=$((PASS + 1))
    else
        printf "  %s %s\n" "$(red FAIL)" "$label"
        FAIL=$((FAIL + 1))
        EXIT=1
    fi
}

c() { curl -fsSL --max-time "$TIMEOUT" "$@"; }
h() { curl -fsSLI --max-time "$TIMEOUT" "$@"; }

echo "Smoke test against $PORTAL_URL"
echo

echo "-- TLS & availability --"
check "Portal reachable (HTTP 200)" bash -c "h '$PORTAL_URL/' | grep -qE '^HTTP/[0-9.]+ 200'"
if [[ "$PORTAL_URL" == https://* ]]; then
    check "TLS certificate valid >14 days" bash -c "
        end=\$(openssl s_client -servername $(echo '$PORTAL_URL' | awk -F/ '{print \$3}') -connect $(echo '$PORTAL_URL' | awk -F/ '{print \$3}'):443 </dev/null 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
        target=\$(date -u -d '+14 days' +%s 2>/dev/null || date -u -v+14d +%s)
        end_sec=\$(date -u -d \"\$end\" +%s 2>/dev/null || date -u -jf '%b %d %T %Y %Z' \"\$end\" +%s)
        [ \"\$end_sec\" -gt \"\$target\" ]
    "
fi

echo
echo "-- Security headers on root --"
HEADERS="$(h "$PORTAL_URL/" 2>/dev/null || true)"
check "X-Content-Type-Options: nosniff"       bash -c "echo \"\$HEADERS\" | grep -iq 'x-content-type-options: nosniff'"
check "X-Frame-Options: DENY"                 bash -c "echo \"\$HEADERS\" | grep -iq 'x-frame-options: deny'"
check "Referrer-Policy: strict-origin-when-cross-origin" bash -c "echo \"\$HEADERS\" | grep -iq 'referrer-policy: strict-origin-when-cross-origin'"
check "Permissions-Policy header"             bash -c "echo \"\$HEADERS\" | grep -iq 'permissions-policy:'"
check "Content-Security-Policy header"        bash -c "echo \"\$HEADERS\" | grep -iq 'content-security-policy:'"
if [[ "$PORTAL_URL" == https://* ]]; then
    check "Strict-Transport-Security header"  bash -c "echo \"\$HEADERS\" | grep -iq 'strict-transport-security:'"
fi

echo
echo "-- /embed/chatbot CSP --"
EMBED_HEADERS="$(h "$PORTAL_URL/embed/chatbot" 2>/dev/null || true)"
check "frame-ancestors on /embed/*"           bash -c "echo \"\$EMBED_HEADERS\" | grep -iq 'content-security-policy:.*frame-ancestors'"
check "X-Frame-Options absent on /embed/*"    bash -c "! echo \"\$EMBED_HEADERS\" | grep -iq 'x-frame-options:'"

echo
echo "-- Backend health --"
HEALTH="$(c "$PORTAL_URL/api/health" 2>/dev/null || true)"
check "/api/health returns 200"               test -n "$HEALTH"
check "status: ok"                             bash -c "echo \"\$HEALTH\" | grep -q '\"status\":\"ok\"'"
check "postgres: ok"                           bash -c "echo \"\$HEALTH\" | grep -q '\"postgres\":\"ok\"'"
check "response-time header present"           bash -c "h '$PORTAL_URL/api/health' | grep -iq 'x-response-time-ms:'"

echo
echo "-- Production-only gates --"
check "Swagger disabled (/api/docs returns 404)"  bash -c "[ \"\$(curl -s -o /dev/null -w '%{http_code}' --max-time $TIMEOUT '$PORTAL_URL/api/docs')\" = '404' ]"
check "OpenAPI schema disabled (/api/openapi.json returns 404)" bash -c "[ \"\$(curl -s -o /dev/null -w '%{http_code}' --max-time $TIMEOUT '$PORTAL_URL/api/openapi.json')\" = '404' ]"

echo
echo "-- Auth behaviour --"
check "Unauthenticated /api/auth/me returns 401" bash -c "[ \"\$(curl -s -o /dev/null -w '%{http_code}' --max-time $TIMEOUT '$PORTAL_URL/api/auth/me')\" = '401' ]"
check "Wrong-password login returns 401"         bash -c "[ \"\$(curl -s -o /dev/null -w '%{http_code}' --max-time $TIMEOUT -X POST -H 'Content-Type: application/json' -d '{\"email\":\"nobody@nobody.example\",\"password\":\"bad\"}' '$PORTAL_URL/api/auth/login')\" = '401' ]"
check "Unsigned payment callback rejected"       bash -c "code=\$(curl -s -o /dev/null -w '%{http_code}' --max-time $TIMEOUT -X POST -H 'Content-Type: application/json' -d '{}' '$PORTAL_URL/api/payments/callback/mpaisa'); [ \"\$code\" = '400' ] || [ \"\$code\" = '401' ] || [ \"\$code\" = '403' ]"

echo
echo "-- Public landing SSR --"
LANDING="$(c "$PORTAL_URL/" 2>/dev/null || true)"
check "Landing includes FNU branding"            bash -c "echo \"\$LANDING\" | grep -qi 'fnu\\|Fiji National University'"

echo
if [ "$FAIL" -eq 0 ]; then
    printf "\n%s %d/%d checks passed.\n" "$(green PASS)" "$PASS" "$((PASS + FAIL))"
else
    printf "\n%s %d/%d checks failed.\n" "$(red FAIL)" "$FAIL" "$((PASS + FAIL))"
fi

exit "$EXIT"
