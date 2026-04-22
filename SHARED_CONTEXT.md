# Shared Context — FNU Web Portal MVP

Quick reference for file locations, utility functions, and environment variables. Keep this current as new parts are built. It is **not** a substitute for reading the actual source — treat it as an index.

---

## File Structure

```
FNU Web Portal MVP/
├── .env                          # Local overrides (git-ignored)
├── .env.example                  # Template — copy to .env
├── docker/
│   └── docker-compose.yml        # 4 services: postgres, backend, frontend, proxy
├── scripts/
│   ├── start.sh                  # docker compose up --build -d
│   └── stop.sh                   # docker compose down
├── docs/
│   ├── PLAN.md                   # 16-part build checklist
│   ├── ARCHITECTURE.md           # Component diagram, data flow, auth model
│   ├── API.md                    # Endpoint contracts (request/response shapes)
│   ├── BANNER_SURFACE.md         # Banner entity field reference and cache status
│   ├── TESTING.md                # Manual test plans per part
│   └── TROUBLESHOOTING.md        # Diagnosis flowcharts per part
├── backend/
│   ├── pyproject.toml            # uv project; ruff, mypy config
│   ├── src/backend/
│   │   ├── main.py               # FastAPI app factory; registers all routers
│   │   ├── auth.py               # JWT helpers + FastAPI dependencies
│   │   ├── config.py             # Pydantic Settings (reads .env)
│   │   ├── rate_limit.py         # slowapi Limiter singleton
│   │   ├── seed.py               # Idempotent dev-data seed (8 users)
│   │   ├── api/
│   │   │   ├── health.py         # GET /api/health
│   │   │   ├── auth.py           # POST /api/auth/login|logout|me|reset-password
│   │   │   ├── banner.py         # GET /api/banner/health
│   │   │   ├── applications.py   # POST/GET /api/applications; admin queue; offers
│   │   │   ├── registration.py   # GET /api/programme|timetable|grades|my-courses|invoices
│   │   │   │                     # POST /api/registration/confirm
│   │   │   │                     # GET /api/timetable.ics
│   │   │   └── payments.py       # POST /api/payments/initiate|callback/*|bank-confirm
│   │   │                         # GET /api/payments/reconciliation (json|csv)
│   │   │                         # GET /api/account; POST /api/account/plan
│   │   ├── payments/
│   │   │   ├── base.py           # PaymentAdapter ABC; InitiateRequest/Response; CallbackResult
│   │   │   ├── signature.py      # HMAC-SHA256 sign_payload / verify_signature (constant-time)
│   │   │   ├── stub_adapter.py   # StubPaymentAdapter + STUB_SECRET (dev/CI only)
│   │   │   ├── mpaisa_adapter.py # Live M-PAiSA (Vodafone) httpx client
│   │   │   ├── mycash_adapter.py # Live MyCash (Digicel) httpx client
│   │   │   ├── bank_transfer_adapter.py  # Manual-confirm adapter
│   │   │   ├── plan_engine.py    # generate_plan_schedule / apply_payment / mark_overdue
│   │   │   ├── factory.py        # get_payment_adapter / get_callback_secret
│   │   │   └── __init__.py       # Module exports
│   │   ├── banner/
│   │   │   ├── types.py          # Pydantic models for all Banner entities
│   │   │   ├── base.py           # Abstract BannerClient (14 methods)
│   │   │   ├── mock_adapter.py   # In-memory mock with FNU seed data
│   │   │   ├── live_adapter.py   # HTTPS client with circuit breaker
│   │   │   ├── cached_client.py  # TTL-caching decorator wrapper
│   │   │   ├── cache.py          # TTLCache (monotonic-clock, thread-safe)
│   │   │   ├── factory.py        # Singleton factory; blocks mock in production
│   │   │   └── __init__.py       # Exports: BannerClient, get_banner_client, reset_banner_client
│   │   ├── db/
│   │   │   ├── base.py           # SQLAlchemy DeclarativeBase
│   │   │   ├── models.py         # All ORM models (see DB Models section below)
│   │   │   ├── schemas.py        # Pydantic request/response schemas for auth
│   │   │   ├── session.py        # async_session_factory; get_session() dependency
│   │   │   └── migrations/
│   │   │       ├── env.py        # Alembic env (async)
│   │   │       └── versions/     # Migration files (excluded from ruff lint)
│   │   └── services/
│   │       ├── audit_service.py  # write_audit_log() — fire-and-forget DB write
│   │       └── notification_service.py  # send_notification() — stub, logs to DB
│   └── tests/
│       ├── test_health.py
│       ├── test_auth.py
│       ├── test_auth_api.py
│       ├── test_banner_mock.py
│       ├── test_banner_cache.py
│       ├── test_banner_factory.py
│       ├── test_applications.py
│       ├── test_registration.py
│       └── test_payments.py
└── frontend/
    ├── package.json              # Next.js 15, next-auth, zod, vitest, @testing-library
    ├── tsconfig.json             # paths: { "@/*": ["./*"] }
    ├── vitest.config.ts          # jsdom environment; "@" alias
    ├── vitest.setup.ts           # @testing-library/jest-dom matchers
    ├── middleware.ts             # Auth guard + security headers on every response
    ├── lib/
    │   ├── api-client.ts         # apiFetch<T>() + ApiError class
    │   ├── auth.ts               # next-auth authOptions (CredentialsProvider)
    │   └── session-provider.tsx  # <SessionProvider> wrapper for Client Components
    ├── components/
    │   ├── portal-nav.tsx        # Sidebar nav with active-link highlighting
    │   ├── portal-nav.test.tsx
    │   ├── outstanding-fees-banner.tsx  # Dismissable fee-balance alert
    │   └── outstanding-fees-banner.test.tsx
    └── app/
        ├── layout.tsx            # Root layout (fonts, metadata, SessionProvider)
        ├── globals.css           # Tailwind @theme tokens; .input-field component
        ├── page.tsx              # Public landing page (Server Component)
        ├── health-status.tsx     # Server Component: fetches /api/health via SSR
        ├── health-status.test.tsx
        ├── (public)/
        │   ├── login/page.tsx    # Credentials login form (Client Component)
        │   ├── apply/
        │   │   ├── page.tsx      # Metadata wrapper (Server Component)
        │   │   ├── application-form.tsx   # 5-step application wizard (Client)
        │   │   └── application-form.test.tsx
        │   └── offer/[token]/page.tsx     # Offer accept/decline page (Client)
        ├── (portal)/             # Authenticated student shell
        │   ├── layout.tsx        # Header + sidebar + OutstandingFeesBanner
        │   ├── dashboard/page.tsx
        │   ├── register/page.tsx         # Course selection with prereq/clash UI (Client)
        │   ├── timetable/page.tsx        # Weekly timetable + .ics export (Server Component)
        │   ├── courses/page.tsx          # Registered courses list (Server Component)
        │   ├── grades/page.tsx           # Grades + GPA summary (Server Component)
        │   ├── invoices/page.tsx         # Invoice list + PDF download (Server Component)
        │   └── pay/page.tsx              # Make-a-Payment page (Client Component)
        ├── (admin)/              # Staff/admin shell
        │   ├── layout.tsx
        │   ├── admin/page.tsx                        # Admin dashboard
        │   ├── admin/applications/
        │   │   ├── page.tsx                          # Application queue
        │   │   └── [id]/page.tsx                     # Application detail + actions
        │   └── admin/finance/page.tsx                # Reconciliation + bank-confirm UI
        └── (lecturer)/           # Lecturer shell
            ├── layout.tsx
            └── lecturer/page.tsx
```

---

## DB Models (`backend/src/backend/db/models.py`)

| Model | Table | Purpose |
|---|---|---|
| `User` | `users` | All user accounts; roles: student, staff, finance, manager, lecturer, vc, admin |
| `Session` | `sessions` | JWT JTI hashes; revocation store |
| `Application` | `applications` | New-student application records (JSONB payload) |
| `ApplicationDocument` | `application_documents` | Uploaded files; `application_id` is nullable |
| `Offer` | `offers` | Acceptance offers; SHA256 token, 7-day expiry |
| `PaymentAttempt` | `payment_attempts` | Gateway payment records |
| `PaymentPlan` | `payment_plans` | Instalment schedules (JSONB) |
| `ChatbotConversation` | `chatbot_conversations` | Session-keyed message history (JSONB) |
| `ChatbotKnowledge` | `chatbot_knowledge` | FAQ entries for RAG |
| `Enquiry` | `enquiries` | Escalated support tickets |
| `KpiDefinition` | `kpi_definitions` | KPI metadata |
| `KpiValue` | `kpi_values` | Recorded KPI data points |
| `Notification` | `notifications` | Outbound notification records |
| `AuditLog` | `audit_log` | Immutable action log (BigInteger PK) |

**Note:** Course registrations, timetables, and invoices are sourced from Banner (not stored locally). Banner is the system of record for academic data.

---

## Banner Types (`backend/src/backend/banner/types.py`)

| Type | Purpose |
|---|---|
| `Programme` | code, name, level, college, campus_codes, duration_years, total_credits |
| `Course` | code, name, credits, programme_codes, year_level, semester, prerequisites |
| `Prerequisite` | course_code, min_grade |
| `Offering` | id, course_code, semester, year, campus, lecturer, day, start_time, end_time, room, capacity, enrolled |
| `FeeItem` | code, description, amount_cents, currency, applies_to, fee_type |
| `FeeSchedule` | year, semester, items |
| `BannerStudent` | banner_id, first_name, last_name, email, phone, programme_code, campus, enrolment_status, gpa |
| `CompletedCourse` | course_code, course_name, grade, credits, semester, year |
| `Invoice` | invoice_id, banner_student_id, semester, year, items, total_cents, paid_cents, due_date, status |
| `ClassRoster` / `RosterEntry` | Roster for a class offering |
| `CreateStudentRequest/Response` | Banner student creation |
| `RegisterCourseRequest/Response` | Banner course registration |
| `SubmitGradeRequest/Response` | Grade submission |
| `CreateInvoiceRequest/Response` | Invoice creation |
| `BannerHealthResponse` | status, latency_ms |

**BannerClient abstract methods (14 total):**
- Reads: `get_programmes`, `get_courses`, `get_offerings`, `get_fee_schedule`, `get_student`, `get_invoices`, `get_class_roster`, `get_completed_courses`, `get_student_registrations`
- Writes: `create_student`, `register_course`, `submit_grade`, `create_invoice`
- Health: `health`

---

## Key Utility Functions

### Backend (`backend/src/backend/`)

| Function | Location | Signature / Purpose |
|---|---|---|
| `hash_password` | `auth.py` | `(password: str) -> str` — bcrypt rounds=12 |
| `verify_password` | `auth.py` | `(password: str, hashed: str) -> bool` |
| `create_access_token` | `auth.py` | `(user_id: str, role: str) -> tuple[str, str]` — returns (token, jti) |
| `decode_token` | `auth.py` | `(token: str) -> dict` — raises 401 on invalid/expired |
| `hash_jti` | `auth.py` | `(jti: str) -> str` — SHA256 hex for session table lookup |
| `get_current_user` | `auth.py` | FastAPI Depends — validates Bearer token + session, returns `User` |
| `require_role(*roles)` | `auth.py` | FastAPI Depends factory — returns `User` or raises 403 |
| `get_optional_user` | `auth.py` | FastAPI Depends — returns `User | None` (no 401 on missing token) |
| `get_banner_client` | `banner/__init__.py` | Returns singleton `BannerClient` (mock or live per config) |
| `reset_banner_client` | `banner/__init__.py` | Clears singleton — use in tests |
| `get_session` | `db/session.py` | FastAPI Depends — yields `AsyncSession` |
| `write_audit_log` | `services/audit_service.py` | `(*, actor_user_id, action, target_type, target_id, before, after, reason, ip_address)` — fire-and-forget |
| `send_notification` | `services/notification_service.py` | `(*, channel, recipient_email, recipient_phone, recipient_user_id, subject, body, template_code)` — stub, logs to DB |
| `check_prerequisites` | `api/registration.py` | `(course_code, prerequisites, completed) -> (bool, list[str])` |
| `detect_clashes` | `api/registration.py` | `(offerings: list[Offering]) -> list[dict]` — time overlap detection |
| `calculate_gpa` | `api/registration.py` | `(courses: list[CompletedCourse]) -> float` — weighted by credits |
| `calculate_semester_gpas` | `api/registration.py` | `(courses) -> dict[str, float]` — keyed "YYYY-S1" |
| `calculate_registration_fees` | `api/registration.py` | `(programme_code, num_courses, fee_items) -> list[FeeItem]` — partial-load pricing |
| `_invoice_html` | `api/registration.py` | `(inv: InvoiceOut) -> str` — HTML template for WeasyPrint PDF generation |

### Frontend (`frontend/`)

| Function / Export | Location | Purpose |
|---|---|---|
| `apiFetch<T>(path, options?)` | `lib/api-client.ts` | Authenticated fetch wrapper; throws `ApiError` on non-2xx |
| `ApiError` | `lib/api-client.ts` | `new ApiError(status, message)` — check `err instanceof ApiError` |
| `authOptions` | `lib/auth.ts` | next-auth config; CredentialsProvider calling `/api/auth/login` |
| `isPublicPath(pathname)` | `middleware.ts` | Returns true for paths that skip auth guard |
| `applySecurityHeaders(response)` | `middleware.ts` | Adds 7 security headers to every Next.js response |

---

## Routing Conventions

### Backend — all routes prefixed `/api`

| Prefix | Router file | Auth requirement |
|---|---|---|
| `/api/health` | `api/health.py` | None |
| `/api/auth/*` | `api/auth.py` | None (except `/me`, `/logout`) |
| `/api/banner/*` | `api/banner.py` | None |
| `/api/applications` (POST) | `api/applications.py` | None (public) |
| `/api/applications/documents` | `api/applications.py` | None (public) |
| `/api/admin/applications/*` | `api/applications.py` | `require_role("staff", "admin")` |
| `/api/admin/applications/bulk-action` | `api/applications.py` | `require_role("admin")` |
| `/api/offers/*` | `api/applications.py` | None (token-based) |
| `/api/programme` | `api/registration.py` | `require_role("student")` |
| `/api/registration/confirm` | `api/registration.py` | `require_role("student")`, rate 3/min |
| `/api/timetable` | `api/registration.py` | `require_role("student")` |
| `/api/timetable.ics` | `api/registration.py` | `require_role("student")` |
| `/api/grades` | `api/registration.py` | `require_role("student")` |
| `/api/my-courses` | `api/registration.py` | `require_role("student")` |
| `/api/invoices` | `api/registration.py` | `require_role("student")` |
| `/api/invoices/{id}` | `api/registration.py` | `require_role("student")` |
| `/api/payments/initiate` | `api/payments.py` | `require_role("student")`, rate 10/min |
| `/api/payments/callback/mpaisa` | `api/payments.py` | None (HMAC-verified, gateway-initiated) |
| `/api/payments/callback/mycash` | `api/payments.py` | None (HMAC-verified, gateway-initiated) |
| `/api/payments/bank-confirm` | `api/payments.py` | `require_role("finance","admin")` |
| `/api/payments/reconciliation` | `api/payments.py` | `require_role("finance","admin")`; `format=csv` streams CSV |
| `/api/account` | `api/payments.py` | `require_role("student")` — balance, history, plan |
| `/api/account/plan` | `api/payments.py` | `require_role("student")` — creates instalment plan |

**Note:** `registration_router` and `payments_router` are included without a prefix (routes define their own `/api/...` paths).

### Frontend — Next.js App Router groups

| Route group | Path prefix | Layout |
|---|---|---|
| `(public)` | `/login`, `/apply`, `/offer/*` | None (uses root layout) |
| `(portal)` | `/dashboard`, `/register`, `/timetable`, `/courses`, `/grades`, `/invoices`, `/pay`, `/id-card`, `/profile` | Portal shell (header + sidebar) |
| `(admin)` | `/admin/*` | Admin shell |
| `(lecturer)` | `/lecturer/*` | Lecturer shell |

**Public paths (middleware bypass):** `/`, `/login`, `/apply`, `/api/auth`, `/verify`, `/offer`

---

## Environment Variables

### Backend (read via `src/backend/config.py` — Pydantic Settings)

| Variable | Default | Required in prod | Purpose |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal` | Yes | PostgreSQL async connection |
| `JWT_SECRET` | `change-me` | Yes (≥32 chars) | HS256 JWT signing key |
| `JWT_ALGORITHM` | `HS256` | No | JWT algorithm |
| `JWT_EXPIRE_MINUTES` | `60` | No | Token lifetime |
| `ENVIRONMENT` | `development` | No | `development` or `production`; controls Swagger visibility and secret validation |
| `BANNER_MODE` | `mock` | Yes (`live`) | `mock` (blocked in production) or `live` |
| `BANNER_API_URL` | `` | Yes when live | Ellucian Banner REST base URL |
| `BANNER_API_KEY` | `` | Yes when live | Banner Bearer token |
| `BANNER_TIMEOUT_SECONDS` | `10.0` | No | Per-request timeout to Banner |
| `BANNER_CACHE_TTL_SECONDS` | `900` | No | TTL for programmes/courses/fees cache |
| `OPENROUTER_API_KEY` | `` | When chatbot live | AI chatbot LLM access |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost"]` | Yes | Allowed CORS origins |
| `PAYMENTS_MODE` | `stub` | Yes (`live`) | `stub` for dev/CI; `live` required in production. Production validator rejects `stub`. |
| `MPAISA_MERCHANT_ID` | `` | Yes when live | M-PAiSA merchant ID |
| `MPAISA_SECRET` | `` | Yes when live | M-PAiSA HMAC secret |
| `MPAISA_API_URL` | `https://sandbox.mpaisa.vodafone.com.fj/api` | No | M-PAiSA base URL |
| `MPAISA_CALLBACK_URL` | `http://localhost/api/payments/callback/mpaisa` | Yes | Public callback URL |
| `MYCASH_MERCHANT_ID` | `` | Yes when live | MyCash merchant ID |
| `MYCASH_SECRET` | `` | Yes when live | MyCash HMAC secret |
| `MYCASH_API_URL` | `https://sandbox.digicel.com.fj/mycash/api` | No | MyCash base URL |
| `MYCASH_CALLBACK_URL` | `http://localhost/api/payments/callback/mycash` | Yes | Public callback URL |
| `SMTP_HOST` | `sandbox.smtp.mailtrap.io` | Part 11 | SMTP server |
| `SMTP_PORT` | `587` | Part 11 | SMTP port |
| `SMTP_USER` | `` | Part 11 | SMTP credentials |
| `SMTP_PASS` | `` | Part 11 | SMTP credentials |
| `SMTP_FROM` | `noreply@portal.fnu.ac.fj` | Part 11 | Sender address |
| `SMS_PROVIDER` | `stub` | Part 11 | `stub` or `vodafone` |

### Frontend (Next.js env conventions)

| Variable | Where set | Purpose |
|---|---|---|
| `NEXTAUTH_SECRET` | `.env` / docker env | Session cookie encryption (≥32 chars in production) |
| `NEXTAUTH_URL` | `.env` / docker env | Canonical app URL (`http://localhost` in Docker, `http://localhost:3000` in dev) |
| `INTERNAL_API_URL` | Docker Compose env | Backend URL for SSR fetches inside Docker (`http://backend:8000`); **never** use `NEXT_PUBLIC_*` for SSR |
| `NEXT_PUBLIC_API_URL` | `.env` | Client-side API base URL (empty string in Docker because nginx proxies `/api`) |

---

## Auth Flow Summary

```
Browser → POST /api/auth/login → FastAPI returns { access_token, user }
next-auth CredentialsProvider stores access_token in JWT session cookie
Client Components call apiFetch() → attaches Bearer token from session
FastAPI get_current_user() → decodes JWT → checks sessions table (revocation) → returns User
require_role("student") → wraps get_current_user, adds role check
```

---

## Test Credentials (seed data)

| Role | Email | Password | Banner ID |
|---|---|---|---|
| student | `student@fnu.ac.fj` | `student123` | `S00012345` (BCOM, Nasinu) |
| student | `student2@fnu.ac.fj` | `student123` | `S00012346` (BNUR, Suva) |
| admin | `admin@fnu.ac.fj` | `admin123` | — |
| staff | `staff@fnu.ac.fj` | `staff123` | — |
| finance | `finance@fnu.ac.fj` | `finance123` | — |
| lecturer | `lecturer@fnu.ac.fj` | `lecturer123` | `L00010001` |
| manager | `manager@fnu.ac.fj` | `manager123` | — |
| vc | `vc@fnu.ac.fj` | `vc123456` | — |

---

## Mock Banner Data Summary

**Programmes:** BCOM, BSCI, BNUR, DIT, CEDU

**Courses (13):** ACC101, ACC201, MGT101, ECN101, MKT201, BIO101, CHM101, PHY101, NUR101, NUR201, IT101, IT102, EDU101

**Offerings (2026 S1, 13 total):** ACC101 Mon 09-11, ACC201 Mon 10-12 *(clashes with ACC101)*, MKT201 Mon 11-13 *(clashes with ACC201)*, MGT101 Tue 13-15, ECN101 Tue 14-16, BIO101 Wed 10-12, CHM101 Wed 14-16, NUR201 Wed 09-11, NUR101 Thu 08-10, EDU101 Thu 13-15, IT101 Fri 09-11, IT102 Fri 10-12 *(clashes with IT101)*, IT101 already listed

**Completed courses (mock):**
- `S00012345` (Apisai): ACC101 (B), MGT101 (A-), ECN101 (B+) — all in 2025
- `S00012346` (Litia): NUR101 (A), BIO101 (B+) — all in 2025

**Invoices:** INV-2026-S1-00001 (Apisai, FJ$3,780, partial), INV-2026-S1-00002 (Litia, FJ$4,100, paid)

---

## Common Commands

```bash
# Stack
./scripts/start.sh
./scripts/stop.sh

# Migrations
cd backend
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal \
  uv run alembic upgrade head

# Seed
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal \
  uv run python -m src.backend.seed

# Tests
cd backend && uv run pytest tests/ -v
cd frontend && npx vitest run

# Lint / type-check
cd backend && uv run ruff check src/ tests/
cd frontend && npx tsc --noEmit

# Build
cd frontend && npx next build
```

---

*Last updated: Part 8 complete (Payment Gateway: M-PAiSA/MyCash/Bank Transfer adapters, stub for dev, plan engine, reconciliation UI, finance confirmation). Part 9 (AI Chatbot) is next.*
