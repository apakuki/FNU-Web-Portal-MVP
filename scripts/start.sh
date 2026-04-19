#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker Desktop first."
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "Starting FNU Web Portal..."
docker compose -f "$PROJECT_ROOT/docker/docker-compose.yml" --project-directory "$PROJECT_ROOT" up --build -d

echo ""
echo "FNU Web Portal is starting up."
echo "  Portal:  http://localhost"
echo "  API:     http://localhost/api/health"
echo "  API docs: http://localhost:8000/api/docs"
echo ""
echo "Run ./scripts/stop.sh to stop all services."
