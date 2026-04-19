# The FNU Web Portal

## Business Requirements

This project is building an integrated Student Services web portal for Fiji National University (FNU). Key features:

- A student-facing registration portal with full self-service capability (application, offer acceptance, course selection, timetable, grades, profile)
- An integrated payment gateway supporting Fiji mobile money providers (M-PAiSA and MyCash) with bank transfer fallback
- An AI-powered chatbot for student enquiry handling, with staff escalation pathway
- A staff administration panel for registry operations (application review, student records, communications, enquiry management)
- A role-based KPI dashboard for all levels of institutional leadership (VC/SLT, Dean, Section Head, Individual Staff, Finance)
- A lecturer-facing class roster and grade entry interface

The system must be operational by 15 June 2026 (first day of Semester 2 enrolment).

## Limitations

For the MVP:
- Single test Banner instance will be used (no production Banner writes)
- Authentication will use FNU student ID / password against a local dev user table seeded with synthetic test accounts; SSO with Banner / FNU AD integration is a later phase
- Payment gateway integration will use M-PAiSA and MyCash sandbox endpoints only — no live transactions
- SMS / email notifications will use sandbox accounts (Mailtrap, a local SMS mock) — no real sends
- AI chatbot will be trained on a fixed seeded FAQ set; dynamic training-data management UI comes later
- KPI dashboard will compute metrics from portal-local data only; Banner-sourced KPIs come in a later milestone
- Everything runs locally (in Docker) for development and is deployed to a staging environment for UAT

## Technical Decisions

### Architecture: Hybrid (Next.js frontend + FastAPI backend)

Two services, each playing to its strengths:

- **Next.js (App Router) TypeScript frontend** — handles rendering, routing, SSR, the public pages (application form, offer acceptance, QR verification) that need fast first-paint on mobile 3G, and the authenticated portal React tree. Calls the FastAPI backend for all data.
- **FastAPI Python backend** — owns the hard integrations: Ellucian Banner (via `python-oracledb` / Ethos APIs), the AI chatbot (OpenRouter + retrieval), payment gateways, PDF generation, background jobs, and all write paths.

### Why this split

- Banner integration is meaningfully easier in Python — `python-oracledb` is Oracle's first-party driver; the LLM and document-retrieval ecosystem is Python-first
- Next.js SSR hits the TOR's "<3s page load on 3G" target on public pages without fighting an SPA bundle
- End-to-end types: FastAPI emits an OpenAPI schema, `openapi-typescript` generates TS types consumed by the Next.js client — one source of truth
- Clean separation lets a Python dev and a TypeScript dev work in parallel

### Frontend stack

- Next.js 15+ (App Router), React 19+, TypeScript strict mode
- Tailwind CSS with FNU brand tokens
- TanStack Query for server state, Zod for client-side validation
- `next-auth` (Auth.js) for session cookie management, wrapping the FastAPI-issued JWT
- Playwright for E2E, Vitest for unit
- Mobile-first responsive design, WCAG 2.1 AA

### Backend stack

- Python 3.12+, FastAPI, Pydantic v2
- `uv` as the package manager
- PostgreSQL for portal-specific data (applications, sessions, chatbot logs, KPI inputs, audit trail), accessed via SQLAlchemy 2.x + Alembic
- `python-oracledb` for Banner reads and writes via Ethos APIs or direct DB connection
- OpenRouter for AI chatbot calls; `OPENROUTER_API_KEY` lives in `.env` in the project root
- Model: `anthropic/claude-sonnet-4` (configurable via env)
- WeasyPrint for offer letter and invoice PDFs (HTML/CSS templates render as PDF)
- APScheduler for in-process scheduled jobs (payment reminders, KPI rollups); upgrade to Celery + Redis if load warrants
- bcrypt for password hashing; JWT (HS256 with rotating secret) for session tokens
- pytest + pytest-asyncio for tests

### Shared infrastructure

- M-PAiSA and MyCash sandbox APIs for payment
- SMTP (Mailtrap sandbox in dev) for email, Vodafone Fiji SMS API (sandbox) for SMS
- Everything packaged into a Docker setup: `docker-compose` runs frontend, backend, and Postgres; production uses two containers behind a single reverse proxy (nginx or Caddy)
- Start and Stop scripts for Mac, PC, Linux in `scripts/`
- Role-based access control enforced on the backend (student, staff, finance, manager, lecturer, vc, admin)
- All secrets in environment variables; nothing committed

## Starting Point

This is a greenfield project. The repository layout will be:

```
FNU Web Portal/
  frontend/        # Next.js App Router (TypeScript)
    app/           # routes (public pages + authenticated portal + admin)
    components/    # shared React components
    lib/           # API client, auth helpers, generated types
    tests/         # Vitest + Playwright
  backend/         # FastAPI application
    src/backend/
      api/         # route handlers grouped by bounded context
      banner/      # the Banner client module (read/write gateway)
      db/          # SQLAlchemy models, Alembic migrations
      services/    # business logic (applications, payments, chatbot, kpi, notifications)
      main.py
    tests/
    seed/          # synthetic data for local dev
  scripts/         # start/stop scripts for Mac, PC, Linux
  docs/            # PLAN.md, DATABASE.md, README.md, ARCHITECTURE.md, API.md
  docker/          # Dockerfile.frontend, Dockerfile.backend, docker-compose.yml, nginx.conf
  .env             # secrets (git-ignored)
```

The frontend calls the backend at `/api/*` via the reverse proxy in production and via a configured `NEXT_PUBLIC_API_URL` in development.

## Color Scheme

FNU brand colours (to be confirmed with FNU brand guidelines — update on receipt of letterhead template):

- FNU Primary Blue: `#003A70` - headers, primary buttons, key sections
- FNU Accent Gold: `#FFB81C` - accent lines, highlights, traffic-light green alternatives
- Success Green: `#2E7D32` - KPI green indicators, confirmation states
- Warning Amber: `#F9A825` - KPI amber indicators, overdue warnings
- Danger Red: `#C62828` - KPI red indicators, errors, rejections
- Dark Text: `#0A1F33` - main headings, body text
- Gray Text: `#6B7280` - supporting text, labels, captions
- Background: `#F4F6F9` - page backgrounds, surface panels

Colour tokens are defined once in `frontend/tailwind.config.ts` and consumed via Tailwind classes.

## Coding standards

1. Use latest versions of libraries and idiomatic approaches as of today
2. Keep it simple — NEVER over-engineer, ALWAYS simplify, NO unnecessary defensive programming. No extra features — focus on scope in the TOR
3. Be concise. Keep README minimal. IMPORTANT: no emojis ever
4. When hitting issues, always identify root cause before trying a fix. Do not guess. Prove with evidence, then fix the root cause
5. All backend routes must enforce role-based access control via a shared dependency — never ad-hoc per route
6. All database writes to Banner go through the single `banner_client` module — no direct Oracle connections scattered through the code
7. All user-visible strings in the frontend live in a single i18n file (English only for MVP, but structured for future Fijian / Hindi)
8. Every FastAPI route has a corresponding Pydantic request and response model — no raw dicts
9. Frontend TypeScript types for API payloads are **generated** from the backend OpenAPI schema via `openapi-typescript`; never hand-written
10. Audit trail writes are non-blocking (fire-and-forget background task) — never block the user response
11. Server Components (Next.js) are the default; use Client Components only when interactivity is required
12. No secrets in `NEXT_PUBLIC_*` variables — anything sensitive stays on the server side of Next.js or in the backend

## Testing standards

- Minimum 80% unit test coverage across backend (pytest) and frontend (Vitest)
- Every API endpoint has at least one happy-path and one auth-failure integration test
- Every role-based view has an access control test (wrong role = 403)
- End-to-end Playwright tests for the core student journey: apply → offer → accept → register → pay → view timetable
- Contract tests: after a schema change, regenerate frontend types and verify the build still passes
- Load test (Locust) proving 500 concurrent users at <3s p95 page load before production sign-off

## Working documentation

All documents for planning and executing this project will be in the docs/ directory.
Please review the docs/PLAN.md document before proceeding.
