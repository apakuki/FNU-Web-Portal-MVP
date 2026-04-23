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
cd "$PROJECT_ROOT/docker"
docker compose up --build -d

# Wait for the backend container to report healthy, then migrate + seed.
# Both commands are idempotent — Alembic no-ops when the DB is already at
# head and the seeder skips rows that already exist.
echo "Waiting for backend health..."
for _ in $(seq 1 60); do
    status="$(docker compose ps backend --format '{{.Health}}' 2>/dev/null || true)"
    if [ "$status" = "healthy" ]; then break; fi
    sleep 1
done

echo "Applying database migrations..."
docker compose exec -T backend alembic upgrade head

echo "Seeding reference data..."
docker compose exec -T backend python -m src.backend.seed

echo ""
echo "FNU Web Portal is ready."
echo "  Portal:  http://localhost"
echo "  API:     http://localhost/api/health"
echo "  API docs: http://localhost:8000/api/docs"
echo ""
echo "Run ./scripts/stop.sh to stop all services."
