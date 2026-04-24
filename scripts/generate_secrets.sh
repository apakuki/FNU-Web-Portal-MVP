#!/usr/bin/env bash
# Generate cryptographically random secrets for a production deployment.
# Emits KEY=VALUE lines you can append to .env.production.
#
# Usage:
#   ./scripts/generate_secrets.sh
#   ./scripts/generate_secrets.sh >> .env.production.generated
#
# The secrets are 64 hex chars (=256 bits of entropy). Rotate and re-run after
# any suspected compromise — see docs/INCIDENT_RESPONSE.md.

set -euo pipefail

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required but not found on PATH." >&2
    exit 1
fi

gen() { openssl rand -hex 32; }

cat <<EOF
# Generated $(date -u +"%Y-%m-%dT%H:%M:%SZ") — copy into .env.production.
JWT_SECRET=$(gen)
NEXTAUTH_SECRET=$(gen)
ID_CARD_SECRET=$(gen)
POSTGRES_PASSWORD=$(gen)
# Application role password for the unprivileged DB user (see DEPLOYMENT.md §4.1).
FNU_APP_DB_PASSWORD=$(gen)
EOF
