#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Stopping FNU Web Portal..."
cd "$PROJECT_ROOT/docker"
docker compose down

echo "All services stopped."
