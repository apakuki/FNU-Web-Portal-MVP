# FNU Web Portal

Integrated Student Services portal for Fiji National University: student registration, payment gateway, AI chatbot, staff admin, KPI dashboard, and lecturer interface.

Architecture: Next.js (App Router, TypeScript) frontend + FastAPI (Python) backend, deployed as two containers behind a reverse proxy.

## Structure

```
FNU Web Portal/
  frontend/    Next.js App Router (TypeScript)
  backend/     FastAPI application (Python, uv)
  scripts/     start/stop scripts for Mac, Linux, Windows
  docker/      Dockerfile.frontend, Dockerfile.backend, docker-compose.yml, nginx.conf
  docs/        PLAN.md, DATABASE.md, ARCHITECTURE.md, API.md
  .env         secrets (git-ignored)
```

## Prerequisites

- Docker and Docker Compose
- Node 20+ (for frontend development outside Docker)
- Python 3.12+ and `uv` (for backend development outside Docker)
- An OpenRouter API key in `.env` as `OPENROUTER_API_KEY`
- For Banner integration beyond the mock adapter: Ellucian Banner API credentials

## Running locally

Start the full stack (frontend, backend, Postgres, proxy):

```bash
./scripts/start.sh          # Mac / Linux
scripts\start.bat           # Windows
```

Stop:

```bash
./scripts/stop.sh           # Mac / Linux
scripts\stop.bat            # Windows
```

The portal is served at `http://localhost`. `/api/*` routes to the backend, everything else to Next.js.

## Frontend development

```bash
cd frontend
npm install
npm run dev             # Next.js dev server with HMR
npm run build           # production build
npm run test            # Vitest unit tests
npm run e2e             # Playwright
npm run generate:types  # regenerate TS types from backend OpenAPI
```

## Backend development

Install dependencies with uv:

```bash
cd backend
uv sync
```

Run migrations:

```bash
uv run alembic upgrade head
```

Seed synthetic data:

```bash
uv run python -m src.backend.seed
```

Run tests:

```bash
uv run pytest
```

Run the server directly (without Docker):

```bash
uv run python -m src.backend.main
```

## Type contract

The frontend never hand-writes API types. They are generated from the backend OpenAPI schema:

```bash
cd frontend
npm run generate:types
```

CI fails if committed types drift from the backend. Regenerate and commit after any backend schema change.

## Planning

See `docs/PLAN.md` for the full part-by-part build plan.
See `docs/DATABASE.md` for the schema.
See `AGENTS.md` for project conventions.
