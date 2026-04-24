# Developer Guide — FNU Web Portal MVP

A walkthrough for a developer picking up this codebase for the first time. Pairs with [PLAN.md](PLAN.md) (the "what" and "why" at the product level), [ARCHITECTURE.md](ARCHITECTURE.md) (the formal architecture doc), and [SHARED_CONTEXT.md](../SHARED_CONTEXT.md) (the up-to-date index of files, routes, and env vars).

**Read this top-to-bottom once.** After that, it's a reference — jump to the section you need.

---

## 1. What you're looking at

FNU (Fiji National University) needed a modern student services portal — apply, enrol, pay, view timetable and grades, talk to an AI assistant, and give staff the tools to manage all of it — by **15 June 2026** (the first day of Semester 2 enrolment).

The portal is a **hybrid web app**:

- **Next.js 15 frontend** (TypeScript, App Router) handles all rendering: public pages (landing, apply, offer acceptance, QR verification), the authenticated student portal, staff admin, lecturer interface, and KPI dashboards.
- **FastAPI backend** (Python 3.12) owns the integrations: Ellucian Banner (the university's student system of record), payment gateways (M-PAiSA, MyCash, bank transfer), the AI chatbot (OpenRouter), PDF generation, scheduled jobs, and every write path.
- **PostgreSQL 16** stores portal-local data (applications, sessions, chatbot logs, KPIs, audit trail). Academic data lives in Banner.
- **nginx** reverse-proxies `/api/*` → backend, everything else → Next.js.

The two apps talk over HTTP. Types flow from the backend's OpenAPI schema into the frontend via `openapi-typescript` so there's a single source of truth for API shapes.

**Why hybrid?** Banner integration is much easier in Python (`python-oracledb`, Ethos). Next.js SSR hits the required "<3 s first paint on 3G" target on public pages. Having both lets a Python dev and a TypeScript dev work in parallel. See [AGENTS.md](../AGENTS.md) for the full rationale.

## 2. First 15 minutes — get it running

Prerequisites: Docker Desktop, Node 20+, Python 3.12+, `uv`.

```bash
git clone <repo-url>
cd "FNU Web Portal MVP"
cp .env.example .env          # defaults are fine for local dev
./scripts/start.sh            # builds + starts postgres/backend/frontend/proxy, migrates, seeds
```

Open **http://localhost**. You should see the public landing page. Log in with a seeded account (the full list is in [SHARED_CONTEXT.md → Test Credentials](../SHARED_CONTEXT.md#test-credentials-seed-data)):

- student → `student@fnu.ac.fj` / `student123`
- admin → `admin@fnu.ac.fj` / `admin123`
- lecturer → `lecturer@fnu.ac.fj` / `lecturer123`
- finance, staff, manager, vc — same pattern

Quick sanity checks:

```bash
curl http://localhost/api/health           # {"status":"ok", ...}
curl http://localhost/api/openapi.json | head  # OpenAPI schema (dev only)
open http://localhost:8000/api/docs        # Swagger UI (dev only)
```

Stop everything with `./scripts/stop.sh`.

### Developing inside the containers vs on the host

For quick iteration, developing **on the host** is smoother — the containers rebuild on every change otherwise.

```bash
# Backend (separate terminal)
cd backend
uv sync                                     # install deps into .venv
uv run alembic upgrade head                 # run migrations against local postgres
uv run python -m src.backend.seed           # seed 8 users + chatbot FAQs + KPI defs
uv run python -m src.backend.main           # hot-reload dev server on :8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                                 # hot-reload dev server on :3000
```

Both still talk to Postgres running in Docker. You'll need to tweak `NEXT_PUBLIC_API_URL` or `NEXTAUTH_URL` if you split host/container — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 3. The shape of the codebase

```
FNU Web Portal MVP/
├── .env.example            # dev template — copy to .env
├── .env.production.example # prod template — REPLACE-* values rejected at startup
├── AGENTS.md               # conventions + rationale (read after this guide)
├── SHARED_CONTEXT.md       # live index: files, routes, env vars, DB models
├── backend/                # FastAPI + SQLAlchemy + Alembic
├── frontend/               # Next.js 15 App Router + TypeScript
├── docker/                 # Dockerfiles + dev/prod compose + nginx configs
├── scripts/                # start/stop/backup/loadtest/smoke/secrets
├── docs/                   # PLAN, ARCHITECTURE, API, SECURITY, TESTING, guides
└── .github/
    ├── workflows/ci.yml    # lint + typecheck + unit tests + Docker build
    └── dependabot.yml
```

One-liner per top-level thing:

| Folder / file | What lives there |
|---|---|
| [AGENTS.md](../AGENTS.md) | The project constitution — colour palette, coding standards, testing standards, tech stack rationale. |
| [SHARED_CONTEXT.md](../SHARED_CONTEXT.md) | Index of *everything* you'll want to look up: file paths, DB tables, endpoint list, env vars. Kept current per part. |
| [backend/](../backend) | Python code. The heart of the system — every write goes through here. |
| [frontend/](../frontend) | TypeScript / React code. SSR-first; interactivity opted in. |
| [docker/](../docker) | Container definitions and reverse-proxy config (dev + prod). |
| [scripts/](../scripts) | Operational shell scripts, cross-platform start/stop. |
| [docs/](../docs) | All planning / architecture / ops / user documentation. |

## 4. The three flows to understand first

Reading code in the order you'd trace a real feature request is the fastest way to learn this codebase. Here are the three essential flows.

### 4.1 Flow A — a student logs in

1. User opens `/login` ([frontend/app/(public)/login/page.tsx](../frontend/app/(public)/login/page.tsx)). This is a **Client Component** (the `"use client"` directive at the top) because it needs form state and event handlers.
2. Submitting the form calls next-auth's `signIn("credentials", …)`.
3. next-auth's CredentialsProvider is wired in [frontend/lib/auth.ts](../frontend/lib/auth.ts) to `POST /api/auth/login`. The FastAPI handler ([backend/src/backend/api/auth.py](../backend/src/backend/api/auth.py)) verifies bcrypt, issues a JWT, and returns it plus a `User` payload.
4. next-auth stores the returned JWT in an **httpOnly, Secure, SameSite=Lax** session cookie. The raw JWT never touches the browser's JavaScript.
5. The middleware at [frontend/middleware.ts](../frontend/middleware.ts) runs on every request. It decodes the cookie via `getToken()`, sets security headers on every response, and redirects unauthenticated requests to `/login` (except for whitelisted public paths: `/`, `/login`, `/apply`, `/verify`, `/offer`, `/embed`, and `/api/auth/*`).
6. From Client Components, the frontend calls the backend via [lib/api-client.ts](../frontend/lib/api-client.ts)'s `apiFetch<T>()`, which grabs the token from the session and attaches it as `Authorization: Bearer …`.
7. FastAPI's `get_current_user` dependency ([backend/src/backend/auth.py](../backend/src/backend/auth.py)) decodes the JWT, checks that its JTI still exists in the `sessions` table (revocation), and returns the `User` ORM object. `require_role("student")` wraps that and raises 403 if the role doesn't match.

**Takeaways:**

- Auth is the backend's responsibility; next-auth is just wrapping it so the cookie layer is standard.
- Never hand-roll fetches from Client Components — use `apiFetch`.
- For **Server Components** you call the backend directly via `INTERNAL_API_URL` (Docker-internal) with `fetch()`, not `apiFetch` — see §6.3.

### 4.2 Flow B — a student registers for courses

1. Student visits `/register` ([frontend/app/(portal)/register/page.tsx](../frontend/app/(portal)/register/page.tsx)) — a Client Component because prereq checks and clash warnings are interactive.
2. On mount it fetches available courses via `apiFetch("/api/courses")`. The backend's `GET /api/courses` ([backend/src/backend/api/registration.py](../backend/src/backend/api/registration.py)) pulls from `banner_client.get_courses()` and filters by the student's programme + prereq status (using `check_prerequisites()` in the same file).
3. The user ticks courses. `detect_clashes()` runs client-side against the current selection, rendering warnings in the UI.
4. "Confirm registration" posts to `POST /api/registration/confirm`. The handler is **atomic**: it calls Banner's `register_course` for each selected offering, creates an invoice via `create_invoice`, and writes rows to the local DB. If any step fails, the rollback logic undoes the Banner writes (see `_rollback_banner_writes` in the handler).
5. Every Banner write goes through [backend/src/backend/banner/audited_client.py](../backend/src/backend/banner/audited_client.py) — it rate-limits with a token bucket and writes a row to `audit_log` for each successful call.
6. The response contains the new timetable + invoice PDF URL. The page re-renders.

**Takeaways:**

- Transactional flows that touch external systems (Banner) must be atomic — the callsite is responsible for rollback because Banner doesn't support cross-service transactions.
- Audit logging is automatic for Banner writes; for portal-level actions you call `write_audit_log(...)` explicitly (see §6.5).
- Single entry point for all Banner calls: `get_banner_client()`. Never `httpx.post("banner…")` directly anywhere else.

### 4.3 Flow C — staff approves an application

1. Staff visits `/admin/applications` ([frontend/app/(admin)/admin/applications/page.tsx](../frontend/app/(admin)/admin/applications/page.tsx)) — a Server Component that SSR-fetches the queue from `GET /api/admin/applications`.
2. Click a row → `/admin/applications/[id]/page.tsx`, also a Server Component for the initial render. Action buttons (Approve / Request documents / Decline) are in a small Client Component alongside.
3. Approve posts to `PUT /api/admin/applications/{id}/status` in [backend/src/backend/api/applications.py](../backend/src/backend/api/applications.py). This handler:
   - Checks `require_role("staff", "admin")`.
   - Updates the application status.
   - Generates an offer letter PDF via WeasyPrint.
   - Inserts a row into `offers` with a cryptographically random token (hashed in the DB).
   - Queues a notification via `send_template(...)` → the applicant's email.
   - Writes `audit_log`.
4. The applicant clicks the email link → `/offer/<token>` ([frontend/app/(public)/offer/[token]/page.tsx](../frontend/app/(public)/offer/[token]/page.tsx)), a Server Component rendering the offer PDF preview and accept/decline buttons.

**Takeaways:**

- Staff actions require an explicit reason in many places (overrides, rejections). The audit trail is not optional.
- Server Components are the default for read-only admin screens; Client Components are for interactive bits.
- Notifications go through a single service (§6.7) — individual handlers never SMTP directly.

## 5. Backend tour

### 5.1 Where to start reading

Start here, in this order:

1. [backend/src/backend/main.py](../backend/src/backend/main.py) — the FastAPI app factory. Shows every middleware, exception handler, and router that exists.
2. [backend/src/backend/config.py](../backend/src/backend/config.py) — Pydantic Settings; shows every environment variable the backend reads, and the production validator.
3. [backend/src/backend/auth.py](../backend/src/backend/auth.py) — auth helpers and dependencies. Every route uses `get_current_user` or `require_role`.
4. One full API module e.g. [backend/src/backend/api/registration.py](../backend/src/backend/api/registration.py) — to see the end-to-end shape of a FastAPI module.

### 5.2 App factory (`main.py`)

```python
def create_app() -> FastAPI:
    is_prod = settings.environment == "production"
    app = FastAPI(
        title="FNU Web Portal API",
        version="0.1.0",
        docs_url=None if is_prod else "/api/docs",        # Swagger off in prod
        openapi_url=None if is_prod else "/api/openapi.json",
        lifespan=lifespan,                                # starts the KPI scheduler
    )
    app.state.limiter = limiter                            # slowapi singleton
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, global_exception_handler)  # never leak stack traces
    app.add_middleware(CORSMiddleware, ...)
    app.add_middleware(ResponseTimeMiddleware)             # X-Response-Time-ms + log line
    # Includes 15+ routers, each under /api/...
    return app
```

**Design choices worth noticing:**

- **Swagger is off in production.** You'd be surprised how often internal APIs get scraped because the schema is public.
- **Global exception handler** returns `{"detail": "Internal server error"}` and logs the stack trace server-side. Clients never see internals.
- **Middleware order matters.** The response-time middleware is added last so it sees the final status code — Starlette applies middleware in reverse order. If you add new middleware, think about where it sits in that chain.

### 5.3 Routers (`api/`)

Every router is a self-contained `APIRouter()` that `main.py` mounts. Each file covers one bounded context — applications, payments, chatbot, etc. Quick map:

| Router file | Scope |
|---|---|
| [api/health.py](../backend/src/backend/api/health.py) | `/api/health` — subsystem status for uptime monitors. |
| [api/auth.py](../backend/src/backend/api/auth.py) | Login, logout, password reset, `/api/auth/me`. |
| [api/banner.py](../backend/src/backend/api/banner.py) | `/api/banner/health` — ping Banner. |
| [api/applications.py](../backend/src/backend/api/applications.py) | Public application submission + staff review + offers. |
| [api/registration.py](../backend/src/backend/api/registration.py) | Courses, registration confirm, timetable, grades, invoices. |
| [api/payments.py](../backend/src/backend/api/payments.py) | Gateway initiate, HMAC-verified callbacks, account/plan, reconciliation. |
| [api/profile.py](../backend/src/backend/api/profile.py) | Profile GET/PUT, photo upload. |
| [api/id_card.py](../backend/src/backend/api/id_card.py) | Digital student ID + signed QR verification. |
| [api/communications.py](../backend/src/backend/api/communications.py) | Templates + admin batch send. |
| [api/chatbot.py](../backend/src/backend/api/chatbot.py) | `/api/chat` + admin FAQ/log/analytics. |
| [api/admin_students.py](../backend/src/backend/api/admin_students.py) | Search + detail + manual overrides. |
| [api/admin_enquiries.py](../backend/src/backend/api/admin_enquiries.py) | Enquiry queue + assignment + resolution. |
| [api/lecturer/](../backend/src/backend/api/lecturer/) | Rosters, grade entry workflow, Banner write-through. |
| [api/kpi.py](../backend/src/backend/api/kpi.py) | KPI definitions, manual input, per-role dashboards. |

Typical shape of a router module:

```python
router = APIRouter(prefix="/api/applications", tags=["applications"])

class ApplicationIn(BaseModel):
    ...          # Pydantic request schema

class ApplicationOut(BaseModel):
    ...          # Pydantic response schema

@router.post("", response_model=ApplicationOut, status_code=201)
@limiter.limit("5/hour")                             # rate limit per IP
async def submit_application(
    payload: ApplicationIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    # 1. Validate beyond what Pydantic catches
    # 2. Persist (SQLAlchemy ORM; async session)
    # 3. Fire-and-forget audit log + notification
    # 4. Return the typed response
```

**Every endpoint has a Pydantic request and response model.** No raw `dict` returns. This is how the OpenAPI schema stays accurate and the frontend types stay generated.

### 5.4 Auth and RBAC (`auth.py`)

```python
async def get_current_user(...) -> User:
    """Decodes Bearer JWT, checks sessions table for revocation."""

def require_role(*roles: str):
    """FastAPI dependency factory. Usage: Depends(require_role('admin'))."""
```

Roles: `student`, `staff`, `finance`, `lecturer`, `manager`, `vc`, `admin`. Every protected route declares the roles it needs — there are no ad-hoc permission checks scattered through handler bodies. See [backend/AGENTS.md](../backend/AGENTS.md) if it exists, otherwise [docs/SECURITY.md](SECURITY.md).

**Password + JWT details:**

- bcrypt cost 12 (matches OWASP 2026 recommendation).
- JWT HS256 with a minimum-32-char secret (enforced by config validator in prod).
- JTI (JWT ID) stored as SHA-256 hash in the `sessions` table. Logout deletes the row; subsequent requests with that token 401.
- 60-minute token lifetime; account lockout after 5 failures for 15 minutes.

### 5.5 Database layer (`db/`)

```
db/
├── base.py              # SQLAlchemy DeclarativeBase
├── models.py            # All ORM models (one file; ~20 tables)
├── schemas.py           # Auth-related Pydantic models (shared request/response shapes)
├── session.py           # async_session_factory, get_session() dependency
└── migrations/          # Alembic, async env.py
    └── versions/        # Ordered migration files
```

We use **SQLAlchemy 2.x async** throughout. Handlers depend on `get_session()` which yields an `AsyncSession`. Use the ORM — no raw SQL. Parameterised queries only.

Migrations are managed with Alembic:

```bash
cd backend
uv run alembic revision -m "add something"    # creates a new migration under versions/
# Edit the generated file to define upgrade() and downgrade()
uv run alembic upgrade head                   # apply
uv run alembic downgrade -1                   # roll back one
```

The convention: **migrations are additive through MVP.** Destructive changes (column drops, renames) go through a two-step deploy (add new → dual-write → cut over → drop old) so rollback is safe. See [docs/DEPLOYMENT.md §10](DEPLOYMENT.md) for why.

Table summary lives in [SHARED_CONTEXT.md → DB Models](../SHARED_CONTEXT.md#db-models-backendsrcbackenddbmodelspy). Important ones to know up front:

- `users` — authentication + role
- `sessions` — active JWTs (hashed), revocation store
- `applications`, `offers` — admissions funnel
- `payment_attempts`, `payment_plans` — payments
- `audit_log` — the immutable action log; every admin action ends up here
- `chatbot_conversations`, `chatbot_knowledge` — chatbot state
- `kpi_definitions`, `kpi_values` — KPI dashboard storage
- `notification_templates`, `notifications` — outbound comms
- `lecturer_grades` — draft/submitted/finalised grade workflow (Part 13)

**Academic data (registered courses, timetables, invoice line items) is NOT stored locally** — it's sourced from Banner. The portal only stores its own artefacts.

### 5.6 Banner integration (`banner/`)

This is the single gateway to Ellucian Banner. Everything Banner-related lives here:

```
banner/
├── base.py              # Abstract BannerClient (14 methods)
├── types.py             # Pydantic models for every Banner entity
├── mock_adapter.py      # In-memory mock with realistic FNU seed data
├── live_adapter.py      # HTTPS client with circuit breaker + TLS verify
├── cache.py             # Thread-safe TTL cache
├── cached_client.py     # Wraps an adapter with caching on read methods
├── rate_limit.py        # Token bucket (20 calls/sec default)
├── audited_client.py    # Top-level wrapper: rate-limit + audit-log every write
└── factory.py           # get_banner_client() — singleton, returns the right stack
```

**Design:** adapter pattern layered with decorators. Reading the stack top-down:

```
AuditedBannerClient         # adds audit-log row on writes + actor ContextVar
  └─ rate_limit wrapper     # throttles every call via token bucket
       └─ CachedBannerClient # caches programmes/courses/fees for 15 min
            └─ {MockBannerAdapter | LiveBannerClient}
```

You always call `get_banner_client()`. In dev it returns the mock wrapped in the caching + audit layers; in production it returns the live client (via `BANNER_MODE=live`). The factory **refuses** to return a mock when `ENVIRONMENT=production`.

**When adding a new Banner call:**

1. Add the method to the abstract `BannerClient` in `base.py`.
2. Implement it on both `MockBannerAdapter` and `LiveBannerClient`. If it's a write, it automatically gets audit-logged by the top-level wrapper — just follow the existing pattern.
3. If it's a read you want to cache, decorate it in `cached_client.py`.
4. Seed realistic mock data in `mock_adapter.py` so everyone else can develop without live Banner.

### 5.7 Services (`services/`)

Shared business logic lifted out of routers:

| Module | What it owns |
|---|---|
| [services/audit_service.py](../backend/src/backend/services/audit_service.py) | `write_audit_log(...)` — fire-and-forget row insert. Never blocks the user response. |
| [services/notification_service.py](../backend/src/backend/services/notification_service.py) | `send_notification`, `send_template`, `render_template`. Dispatches via SMTP + SMS (or stub). |
| [services/chatbot_service.py](../backend/src/backend/services/chatbot_service.py) | FAQ retrieval, OpenRouter prompt composition, escalation trigger, PII masking. |
| [services/kpi_service.py](../backend/src/backend/services/kpi_service.py) | Auto-KPI computation, traffic-light helper, period resolver. |
| [services/id_card_service.py](../backend/src/backend/services/id_card_service.py) | `sign_id_card`, `verify_id_card` — HMAC-SHA256 QR payloads. |

The rule: **if you find yourself writing the same 10 lines in two routers, lift it into a service.** Services don't import from `api/` — the dependency flows one way.

### 5.8 Middleware + rate limiting

- [middleware/timing.py](../backend/src/backend/middleware/timing.py) — logs one structured line per request (`method`, `path`, `status`, `response_ms`) and sets `X-Response-Time-ms` on every response. In production this format is JSON for log shippers (set via `LOG_FORMAT=json`).
- [logging_config.py](../backend/src/backend/logging_config.py) — `JsonFormatter` + `configure_logging()`. Called from `main.py` at import time.
- [rate_limit.py](../backend/src/backend/rate_limit.py) — the slowapi `Limiter` singleton. Apply per-route with `@limiter.limit("10/min")` or globally via settings. Current limits are listed in [docs/SECURITY.md](SECURITY.md).

### 5.9 The scheduler

[scheduler.py](../backend/src/backend/scheduler.py) runs APScheduler in-process via FastAPI's `lifespan` context. Currently one job: recompute all auto KPIs every `KPI_COMPUTE_INTERVAL_MINUTES` (default 60). Set `KPI_SCHEDULER_ENABLED=false` in tests and CI so the loop doesn't start.

If load ever warrants it, upgrade to Celery + Redis — the scheduler touch points are isolated enough that it's a contained migration.

### 5.10 Tests (`tests/`)

Test modules match router modules one-for-one:

```
tests/test_auth.py              # auth.py helpers (hash_password, JWT encode/decode)
tests/test_auth_api.py          # /api/auth/* endpoints
tests/test_applications.py      # applications.py — happy path + validation + auth
tests/test_registration.py      # prereq, clash, GPA, full register→invoice cycle
tests/test_payments.py          # HMAC, idempotency, plan engine, reconciliation
...
tests/test_security.py          # cross-cutting: IDOR, unsigned callbacks, headers
tests/test_banner_audit.py      # AuditedBannerClient + token bucket
tests/test_logging_config.py    # JsonFormatter + configure_logging
tests/test_config_validators.py # production Settings validator
```

Running:

```bash
cd backend
KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest tests/ -q   # full suite
KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest tests/test_payments.py -v   # one file
```

Fixtures live in `tests/conftest.py` (if present) and individual test files. We use `pytest-asyncio` with `mode=auto` (configured in `pyproject.toml`) — async tests just `async def test_foo()`.

**Coverage target: 80%+.** Every endpoint has at least a happy-path and an auth-failure test; every role-scoped view has an access-control test.

## 6. Frontend tour

### 6.1 Where to start reading

1. [frontend/app/layout.tsx](../frontend/app/layout.tsx) — the root layout (fonts, metadata, `<SessionProvider>` wrapper).
2. [frontend/middleware.ts](../frontend/middleware.ts) — auth guard + security headers.
3. [frontend/lib/auth.ts](../frontend/lib/auth.ts) + [frontend/lib/api-client.ts](../frontend/lib/api-client.ts) — how sessions and API calls work.
4. One route group end-to-end, e.g. [frontend/app/(portal)/](../frontend/app/(portal)/) — to see the pattern.

### 6.2 App Router route groups

Next.js 15's App Router uses folder nesting + parenthesised "route groups" to share layouts without adding URL segments. The portal uses four groups:

```
app/
├── page.tsx                    # '/' — public landing
├── layout.tsx                  # root layout (no shell)
├── error.tsx / global-error.tsx / not-found.tsx
├── (public)/                   # no auth required; no portal shell
│   ├── login/page.tsx
│   ├── apply/page.tsx + application-form.tsx
│   └── offer/[token]/page.tsx
├── (portal)/                   # authenticated student shell (header + sidebar)
│   ├── layout.tsx              # renders nav + outstanding-fees banner + chatbot widget
│   ├── dashboard/page.tsx
│   ├── register/page.tsx
│   ├── timetable/page.tsx
│   ├── courses/page.tsx
│   ├── grades/page.tsx
│   ├── invoices/page.tsx
│   ├── pay/page.tsx
│   ├── profile/page.tsx
│   └── id-card/page.tsx
├── (admin)/                    # staff/finance/admin shell
│   └── admin/
│       ├── applications/
│       ├── finance/
│       ├── communications/
│       ├── students/
│       ├── enquiries/
│       ├── chatbot/            # knowledge, conversations, analytics
│       └── kpi/                # vc, dean, section-head, finance, me, targets
├── (lecturer)/                 # lecturer shell
│   └── lecturer/
│       ├── courses/[offeringId]/
│       └── grades/
└── embed/
    └── chatbot/page.tsx        # publicly embeddable chatbot surface (iframed)
```

Parens don't show in the URL — `(portal)/dashboard/page.tsx` serves `/dashboard`. They just let that subtree share `layout.tsx`.

### 6.3 Server Components vs Client Components

**Default: Server Components.** They render on the server, stream HTML to the browser, and ship zero JavaScript for that component. Use for read-only views: timetables, grades, courses, invoice lists, admin queues.

**Client Components** are opt-in via `"use client"` at the top of the file. Use only when you need state, effects, event handlers, or browser APIs. Typical places: the login form, the course selection flow (prereq + clash UI), the chatbot widget, the grade-entry grid.

Practical consequences:

- A **Server Component fetches data** using plain `fetch(...)` to the backend, which inside Docker resolves to `INTERNAL_API_URL` (`http://backend:8000`), and on the host dev server uses `NEXT_PUBLIC_API_URL`. Tokens propagate via the cookie, not via `apiFetch`.
- A **Client Component** uses `apiFetch<T>(...)` from [lib/api-client.ts](../frontend/lib/api-client.ts), which pulls the access token from the next-auth session and sets `Authorization: Bearer ...`.

Mixing: a Server Component page can render Client Components, and pass them data as props. The reverse is not allowed (a Client Component can't render a Server Component directly), but you *can* pass Server Components as `children`.

### 6.4 Auth wrapper

[lib/auth.ts](../frontend/lib/auth.ts) defines `authOptions` for next-auth:

- A single CredentialsProvider posts email/password to `/api/auth/login`.
- Callbacks stash the `access_token` and the `user` payload into the JWT cookie.
- [lib/session-provider.tsx](../frontend/lib/session-provider.tsx) wraps the app so Client Components can `useSession()`.

[middleware.ts](../frontend/middleware.ts) runs on every request:

```typescript
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isPublicPath(pathname) || pathname.startsWith("/_next")) {
    return applySecurityHeaders(NextResponse.next(), pathname);
  }
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }
  return applySecurityHeaders(NextResponse.next(), pathname);
}
```

It also handles the embed-specific CSP: `/embed/*` gets `Content-Security-Policy: frame-ancestors …` so it can be embedded in an iframe, while every other route gets `X-Frame-Options: DENY`.

### 6.5 Components + tests

Shared components in [frontend/components/](../frontend/components/):

- `portal-nav.tsx` — sidebar nav with active-link highlighting.
- `outstanding-fees-banner.tsx` — shown at the top of the portal shell when an overdue invoice exists.
- `ChatbotWidget.tsx` — the floating chat bubble used in the portal shell and on the embeddable surface.
- `kpi-dashboard.tsx` — shared dashboard component used by all five KPI views.

Tests sit next to components — `*.test.tsx`. Vitest + @testing-library:

```bash
cd frontend
npx vitest run            # all tests
npx vitest run ChatbotWidget      # filter by name
```

End-to-end tests use Playwright ([frontend/tests/e2e/](../frontend/tests/e2e/)). The axe-core accessibility smoke runs across five browser projects (chromium, firefox, webkit, mobile-chrome, mobile-safari):

```bash
cd frontend
npm run e2e:install         # one-time browser download (~500 MB)
npm run a11y                # axe spec
npm run e2e                 # full E2E
```

### 6.6 Type generation — the contract with the backend

We never hand-write API types. The pipeline:

1. FastAPI exposes the OpenAPI schema at `/api/openapi.json` (dev only).
2. `openapi-typescript` reads it and emits `frontend/lib/api-types.ts`.
3. Both sides reference the same shapes; schema drift = compile error.

```bash
cd frontend
npm run generate:types      # regenerate after any backend schema change
```

CI fails if committed types drift from what the backend emits. **Regenerate and commit whenever you add or change a backend response.**

### 6.7 Tailwind + brand tokens

Colours are defined once in [frontend/tailwind.config.ts](../frontend/tailwind.config.ts) using FNU brand tokens (see [AGENTS.md § Color Scheme](../AGENTS.md#color-scheme)). Consume via utility classes:

```tsx
<button className="bg-fnu-primary hover:bg-fnu-primary-dark text-white ...">
```

Changing the palette is a one-file edit.

## 7. Cross-cutting concerns

### 7.1 The audit log — your investigative backbone

Every significant action lands in the `audit_log` table. Banner writes are audit-logged automatically by `AuditedBannerClient`. Portal-side actions (application decisions, manual overrides, bulk actions, KPI target changes, batch comms, grade finalisation) call `write_audit_log(...)` directly:

```python
await write_audit_log(
    actor_user_id=current_user.id,
    action="application.approve",
    target_type="application",
    target_id=str(application.id),
    before={"status": application.status},
    after={"status": "offer_made"},
    reason=payload.reason,
    ip_address=request.client.host,
)
```

**Never ship a staff-facing write that skips this.** In an incident the audit log is the first place you look — see [docs/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md).

### 7.2 Rate limiting

`@limiter.limit("N/min")` decorates sensitive routes. Current coverage is summarised in [docs/SECURITY.md](SECURITY.md):

- Login 10/min, reset 3/min, reset-confirm 5/min
- Applications 5/hour per IP, document upload 20/hour per IP
- Chat 30/min authed / 10/min anon
- Payments initiate 10/min, registration confirm 3/min

Rate-limit decisions are on principle of least surprise: block obvious abuse, don't impede normal use.

### 7.3 Error handling

- Backend: a **single** global exception handler in `main.py` returns `{"detail": "Internal server error"}` and logs the stack trace. Routes use domain-specific HTTPExceptions (`400`, `404`, `409`) as needed; these pass through.
- Frontend: error boundaries at three levels — [app/error.tsx](../frontend/app/error.tsx) (per-segment), [app/global-error.tsx](../frontend/app/global-error.tsx) (root-level), [app/not-found.tsx](../frontend/app/not-found.tsx). Runtime errors in a Client Component trigger the nearest `error.tsx`.
- `apiFetch` throws a typed `ApiError` on non-2xx so callers can `catch (err) { if (err instanceof ApiError) ... }`.

### 7.4 Testing strategy

- Minimum **80% unit test coverage** on both backend (pytest) and frontend (Vitest).
- Every endpoint has a happy-path + an auth-failure test.
- Every role-scoped view has a wrong-role test (expects 403).
- End-to-end Playwright covers the core student journey: apply → offer → accept → register → pay → view timetable.
- Manual test plans for every part in [docs/TESTING.md](TESTING.md).

### 7.5 Environment variables

All env vars are enumerated in [SHARED_CONTEXT.md → Environment Variables](../SHARED_CONTEXT.md#environment-variables), with defaults and "required in prod" markers. Two principles:

- **Backend reads via `config.py`**. Settings are validated at startup — production rejects placeholders and short secrets. If you add a new secret, add it to `Settings`, add it to both `.env.example` and `.env.production.example`, and add a validator check if the value matters in prod.
- **Frontend: nothing sensitive goes in `NEXT_PUBLIC_*`** — those variables are baked into the client bundle. Only `NEXTAUTH_SECRET` and private API URLs are accepted server-side; never expose an API key through `NEXT_PUBLIC_...`.

### 7.6 Security basics (read [SECURITY.md](SECURITY.md) for the full version)

- bcrypt cost 12 passwords, HS256 JWT, httpOnly session cookie.
- Every state-changing request checks auth + role.
- File uploads: magic-byte MIME check + size limit + random filename + stored outside web root (for application docs) or as DB `LargeBinary` (for photos).
- All user-submitted values rendered as React text (auto-escaped) or explicitly `html.escape`'d (PDFs).
- CSP, HSTS (production), X-Frame-Options DENY (except `/embed/*`), X-Content-Type-Options.
- Production validator rejects placeholder secrets and insecure modes. Swagger is off in prod.

### 7.7 Deployment and operations

- Dev: `./scripts/start.sh` brings up the full stack locally.
- Production: `docker/docker-compose.prod.yml` + `docker/nginx.prod.conf` with Let's Encrypt, JSON logs, and no host port on Postgres. Full walkthrough in [docs/DEPLOYMENT.md](DEPLOYMENT.md).
- Incident response runbooks in [docs/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md).
- Day-to-day ops in [docs/OPS_RUNBOOK.md](OPS_RUNBOOK.md).

## 8. Appendix — common tasks

### 8.1 I need to add a new backend endpoint

1. Identify (or create) the appropriate router under `backend/src/backend/api/`.
2. Write Pydantic request + response models. Use `EmailStr`, `gt=0`, `min_length=...` — Pydantic should catch as much as possible.
3. Write the handler. Depend on `get_session()` for DB, and `require_role(...)` for auth. Rate-limit if it's sensitive.
4. Write audit log entries for state-changing actions.
5. Add tests: happy path, auth failure, validation failure.
6. Run `npm run generate:types` in the frontend to sync types.
7. Check CI passes — the contract check will fail if you forgot step 6.

### 8.2 I need to add a new frontend page

1. Create the folder under the right route group (`(portal)/`, `(admin)/`, etc.).
2. Default to a Server Component (`page.tsx`). Fetch data via plain `fetch` against `INTERNAL_API_URL` (SSR) — the cookie carries auth.
3. If you need interactivity, pull the interactive bits into a sibling `*.tsx` with `"use client"` and import it into the page.
4. Use `apiFetch<T>("/api/...")` from Client Components. The types come from `lib/api-types.ts`.
5. Cover critical state with Vitest unit tests next to the component.

### 8.3 I need to add a new DB table or column

1. `cd backend && uv run alembic revision -m "add <thing>"`.
2. Edit the new `versions/*.py` to write `upgrade()` and `downgrade()`. Prefer additive changes.
3. Add or update the ORM model in `db/models.py`. If Pydantic schemas need updating, edit `db/schemas.py` (auth) or the API's own schema classes.
4. `uv run alembic upgrade head` to apply locally.
5. Test round-trip: `downgrade -1 && upgrade head` against a disposable DB.
6. Update the table list in [SHARED_CONTEXT.md](../SHARED_CONTEXT.md).

### 8.4 I need to add a new role

1. Add the role string to the seed (`backend/src/backend/seed.py`) if you need a test account.
2. Create / update the relevant `require_role(...)` calls. No branching — prefer a new role over conditional logic in an existing handler.
3. Add tests: the new role succeeds on its own endpoints, 403s on others.
4. Update `docs/SECURITY.md` § Authorisation + [USER_GUIDE_STAFF.md](USER_GUIDE_STAFF.md) role table if relevant.

### 8.5 I need to add a new Banner call

See §5.6 — the pattern is add the method to `base.py`, implement on both `mock_adapter.py` and `live_adapter.py`, and update `BANNER_SURFACE.md`. Writes are audit-logged automatically by the wrapper stack.

### 8.6 I need to add a new notification

1. Add a template row to the seed (`backend/seed/notification_templates.json`). The `code` is the stable key your code uses.
2. Call `send_template(code="...", variables={...}, recipient_email=..., recipient_phone=...)` at the point in your handler where the notification fires.
3. Use fire-and-forget (don't `await` the background task — the user response shouldn't wait on outbound SMTP).

### 8.7 I'm debugging a flaky test

- Is the scheduler on? If you see tests hang or spurious state, make sure `KPI_SCHEDULER_ENABLED=false` is set.
- Is it async-related? `pytest-asyncio` mode is `auto`, so `async def test_...` works — but fixtures need `@pytest_asyncio.fixture` if they `yield`.
- Is a previous test leaking state into the singleton? `tests/test_banner_factory.py` uses a `reset_banner_client()` fixture — do the same if you're tweaking a singleton.

### 8.8 I'm about to deploy to production

Do **not** skip [docs/DEPLOYMENT.md](DEPLOYMENT.md). The short version:

```bash
cp .env.production.example .env.production
./scripts/generate_secrets.sh >> .env.production.generated
# manually copy generated values into .env.production
cd docker && docker compose -f docker-compose.prod.yml up -d --build
PORTAL_URL=https://portal.fnu.ac.fj ./scripts/smoke_test.sh
```

## 9. Where to go next

- [PLAN.md](PLAN.md) — why the project is organised into 16 parts, what each ships.
- [ARCHITECTURE.md](ARCHITECTURE.md) — formal architecture doc (component diagram, data flow, auth model).
- [API.md](API.md) — endpoint contracts (request/response shapes).
- [DATABASE.md](DATABASE.md) — schema detail beyond the table summary.
- [BANNER_SURFACE.md](BANNER_SURFACE.md) — every Banner field we consume.
- [SECURITY.md](SECURITY.md) — security posture, rate limits, accepted findings.
- [TESTING.md](TESTING.md) — manual test plans per part.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — diagnosis flowcharts when something's wrong.
- [AGENTS.md](../AGENTS.md) — coding standards and conventions.

Welcome aboard. When in doubt, follow the existing pattern — this codebase is deliberately consistent. If your change feels like it needs a new pattern, that's a good sign it deserves a short design discussion before you build it.

---

*Last updated: 2026-04 (Part 16).*
