# Detailed Project Plan for FNU Web Portal MVP

This plan breaks the FNU Student Services Modernisation Programme (per the Terms of Reference) into manageable, independently buildable parts. Each part has detailed substeps as checklists, testing requirements, and success criteria.

The architecture is a **hybrid**: Next.js (App Router, TypeScript) frontend and FastAPI (Python) backend, deployed as two containers behind a reverse proxy. See `AGENTS.md` for the rationale.

The plan is sequenced so each part produces a deployable, testable increment. Where parts can be built in parallel by separate developers, it is noted under **Parallelism**.

Testing is first-class: aim for 80% minimum unit test coverage across all code, plus integration tests, end-to-end Playwright tests for the critical student journey, and load testing before production sign-off.

---

## Part 1: Plan, Architecture and Foundation Docs

Enrich this document, produce the technical architecture document (TOR deliverable D1), and create the AGENTS.md files for each codebase. Get user sign-off before building.

### Substeps

- [x] Review the Terms of Reference and confirm scope boundaries
- [x] Create detailed substeps, tests, and success criteria for all parts of this plan
- [x] Create docs/ARCHITECTURE.md covering: component diagram (Next.js / FastAPI / Postgres / Banner), data flow, Banner integration surface, auth model (JWT issued by FastAPI, wrapped in a next-auth session cookie), deployment topology (two containers + reverse proxy)
- [x] Create docs/API.md with endpoint contracts (request/response shape per route)
- [x] Create frontend/AGENTS.md, backend/AGENTS.md, scripts/AGENTS.md placeholders
- [x] Capture top 3 risks and mitigations (Banner API access timing, payment gateway sandbox credentials, Fiji-timezone standup coverage)
- [ ] Get user and FNU PM approval on the enriched plan and architecture

### Tests

- Manual review of documentation completeness
- Architecture doc walkthrough with FNU IT contact

### Success Criteria

- PLAN.md contains detailed checklists for all parts
- ARCHITECTURE.md approved by FNU IT contact
- AGENTS.md files exist for frontend, backend, and scripts
- TOR deliverable D1 signed off

### Parallelism

Not parallelisable — gates all subsequent work.

---

## Part 2: Scaffolding — Docker, Backend and Frontend skeletons, CI

Set up Docker infrastructure, FastAPI backend skeleton, Next.js frontend skeleton, PostgreSQL via docker-compose, a reverse proxy gluing frontend and backend, the OpenAPI → TypeScript type generation pipeline, and start/stop scripts. Prove the full stack comes up and a typed API call round-trips end to end.

### Substeps

- [x] Create `docker/Dockerfile.backend` (Python 3.12, uv, FastAPI)
- [x] Create `docker/Dockerfile.frontend` (Node 20, Next.js production build, standalone output)
- [x] Create `docker/docker-compose.yml` with services: `backend`, `frontend`, `postgres`, `proxy` (nginx or Caddy)
- [x] Configure the proxy: route `/api/*` to backend, everything else to Next.js
- [x] Initialise FastAPI in `backend/` with `/api/health` and CORS configured for local dev
- [x] Initialise Next.js App Router in `frontend/` with a placeholder home page that fetches `/api/health` and renders its status
- [x] Configure `next.config.ts` for standalone output and image optimisation
- [x] Configure Tailwind with FNU brand tokens from AGENTS.md
- [x] Wire Alembic for migrations; create initial empty migration
- [x] Set up the OpenAPI → TypeScript pipeline: `openapi-typescript` generates `frontend/lib/api-types.ts` from `backend` OpenAPI schema; add an `npm run generate:types` script and a CI check that fails if committed types drift from the backend
- [x] Create start scripts for Mac, Linux, Windows in `scripts/`
- [x] Create stop scripts for all platforms
- [x] Add GitHub Actions CI workflow: backend (ruff, mypy, pytest), frontend (eslint, tsc, vitest), contract check (regenerate types, fail on drift), Docker build for both images
- [x] Verify Docker Compose up end-to-end locally: home page loads, fetches `/api/health`, renders "ok"

### Security Hardening (Retroactive)

- [x] Backend container runs as non-root user (USER app in Dockerfile)
- [x] `.dockerignore` excludes `.venv`, `node_modules`, `.next`, `__pycache__`, `.git` from build context
- [x] nginx security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, HSTS, Permissions-Policy, CSP
- [x] nginx `server_tokens off` to hide version information
- [x] CORS restricted to specific origins (not wildcard)
- [x] CORS `allow_methods` restricted to used HTTP verbs only (not `["*"]`)
- [x] `.env` git-ignored; `.env.example` committed with safe placeholder values
- [x] Frontend security headers set in Next.js middleware (HSTS, Permissions-Policy, X-DNS-Prefetch-Control)

### Tests

- Backend: unit tests for health route and settings loader (>=80% coverage)
- Frontend: Vitest test rendering the home page with a mocked health response
- Integration: `docker compose up` succeeds; curl `http://localhost/` returns 200; curl `http://localhost/api/health` returns 200
- E2E: Playwright opens the home page, sees "ok" rendered from the live backend call
- CI pipeline runs green on a fresh push

### Success Criteria

- `./scripts/start.sh` brings the full stack up locally (frontend, backend, Postgres, proxy)
- Next.js home page loads and displays a value fetched from FastAPI
- /api/health returns 200 via the reverse proxy
- Postgres container is reachable from backend
- OpenAPI → TypeScript type generation works; a type change on the backend surfaces as a compile error in the frontend
- CI is green

### Parallelism

Not parallelisable — foundation for all later parts.

---

## Part 3: Database and Authentication

Implement the Postgres schema from docs/DATABASE.md, build JWT-based authentication on the backend, wire next-auth on the frontend to wrap it in a session cookie, enforce role-based access control, and seed synthetic users.

### Substeps

- [x] Write Alembic migrations for all portal tables (users, sessions, applications, application_documents, offers, payment_attempts, payment_plans, chatbot_conversations, chatbot_knowledge, enquiries, kpi_definitions, kpi_values, notifications, audit_log)
- [x] Build SQLAlchemy models and Pydantic schemas for every table
- [x] Implement password hashing (bcrypt) and JWT issue/verify helpers in the backend
- [x] Implement `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, `/api/auth/reset-password`
- [x] Implement role-based FastAPI dependency (`require_role("student")`, etc.)
- [x] Configure next-auth with a Credentials provider that calls `/api/auth/login`; store the returned JWT in an httpOnly session cookie
- [x] Build a shared frontend `apiFetch` helper that attaches the session token to backend calls
- [x] Build Next.js middleware that protects authenticated routes and redirects unauthenticated users to the login page
- [x] Implement password reset flow (token issued backend-side, email sent via stubbed sender)
- [x] Build seed command loading synthetic students, staff, admin, lecturer, finance users
- [x] Implement audit_log write helper (async, fire-and-forget) and use it from login/logout

### Security Hardening (Retroactive)

- [x] Password hashing: bcrypt with cost factor 12
- [x] JWT: HS256 with configurable secret; production startup validator rejects weak/default secrets
- [x] Session tracking: JTI hashed (SHA-256) in sessions table; logout revokes server-side
- [x] Account lockout: 5 failed attempts / 15 min, tracked in database (persistent across restarts)
- [x] Rate limiting: slowapi on login (10/min), reset-password (3/min), reset-confirm (5/min)
- [x] Global exception handler: catches unhandled errors, returns generic message, logs details server-side
- [x] Swagger/OpenAPI docs: disabled in production (ENVIRONMENT=production)
- [x] Input validation: EmailStr on email fields, length constraints on passwords and tokens
- [x] Parameterised queries only (SQLAlchemy ORM — no raw SQL)
- [x] Audit log on every login/logout with actor, IP address, timestamp
- [x] Password reset: no email enumeration (always returns success message)

### Tests

- Backend unit tests for auth helpers, password hashing, JWT encode/decode (>=80% coverage)
- Backend integration tests: login happy path, wrong password, expired token, revoked session
- Role-based access tests: each role gets 200 on their own route, 403 on others
- Migration up/down round-trip test
- Frontend unit tests for next-auth config, `apiFetch`, middleware redirect logic
- E2E: unauthenticated visit to `/dashboard` redirects to `/login`; successful login lands on `/dashboard`

### Success Criteria

- All tables exist in Postgres after migration
- Seed command produces one user per role
- next-auth session cookie issued on login, cleared on logout
- Role-based dependency blocks unauthorised access on the backend
- Protected routes are gated on the frontend
- All admin actions in this part land in audit_log
- TOR 2.1.1 (Student Authentication) backend + frontend complete

### Parallelism

After Part 3 ships, Parts 4, 5, 6, 7, 8 can be built by separate developers in parallel, each behind their own feature branch.

---

## Part 4: Portal Shell, Login UI, and Public Landing

Build the Next.js App Router structure for the public landing (SSR for speed), the login page, and the authenticated student portal shell. Ship the dashboard landing with empty widgets that Parts 6–11 will fill.

### Substeps

- [x] Define the route structure: `app/(public)/` for unauthenticated pages (landing, apply, offer/[token], verify/[qr]), `app/(portal)/` for authenticated student pages, `app/(admin)/` for staff/admin pages, `app/(lecturer)/` for lecturer pages
- [x] Build the public landing page (Server Component) with FNU branding, links to apply and login
- [x] Build login page as a Client Component wrapping next-auth's `signIn`
- [x] Build the authenticated portal layout: top nav, side nav, outstanding-fees banner slot
- [x] Build the dashboard landing with placeholder widgets: Course Registration, My Timetable, My Courses, My Grades, Make a Payment, Student ID
- [x] Build logout flow
- [x] Build admin route group layout and placeholder dashboard
- [x] Build lecturer route group layout and placeholder dashboard
- [x] Ensure WCAG 2.1 AA on public landing, login, and shell (keyboard nav, focus visible, colour contrast, aria labels)
- [x] Ensure mobile responsiveness (min 44px tap targets, hamburger sidebar on mobile)
- [ ] Measure and meet the <3s-on-3G first-paint target on the public landing using Lighthouse

### Security Hardening (Retroactive)

- [x] Route protection: Next.js middleware redirects unauthenticated users to /login
- [x] Session cookies: httpOnly, Secure, SameSite=Lax (via next-auth)
- [x] Security headers on every response via Next.js middleware
- [x] No secrets in NEXT_PUBLIC_ variables
- [x] Server Components used by default (no client-side token exposure)
- [x] INTERNAL_API_URL used for SSR fetches (not exposed to client)
- [x] Accessible focus-visible indicators on all interactive elements

### Tests

- Vitest unit tests for layout components, outstanding-fees banner logic, nav (>=80% coverage)
- Integration test: login flow renders, calls backend, redirects to dashboard, logout returns to login
- E2E Playwright: full login cycle on Chromium and WebKit
- Accessibility test: axe-core passes on landing, login, dashboard
- Mobile viewport test: shell renders correctly at 375px
- Lighthouse (simulated 3G): public landing under 3s FCP

### Success Criteria

- Login required to access any authenticated portal page (enforced in Next.js middleware + backend)
- Correct credentials route to dashboard; invalid credentials show error
- Shell renders on mobile and desktop without layout break
- Accessibility checks pass
- Public landing hits the 3s-on-3G target
- Frontend tests pass with >=80% unit coverage

### Parallelism

Front-end shell can proceed in parallel with Part 3's auth backend once endpoint contracts are agreed via OpenAPI.

---

## Part 5: Banner Integration Layer

Build the `banner_client` module — the single gateway to Ellucian Banner. Ship read-only first (programmes, courses, fee schedules), then writes (student creation, course registration, grade submission). Cache programme structure with 15-minute TTL.

### Substeps

- [ ] Procure and test Banner API credentials (blocking — FNU to provide end of Week 1)
- [x] Build `banner_client` package with typed read functions: `get_programmes`, `get_courses`, `get_offerings`, `get_fee_schedule`, `get_student`, `get_invoices`, `get_class_roster`
- [x] Build write functions: `create_student`, `register_course`, `submit_grade`, `create_invoice`
- [x] Implement in-memory cache with 15-minute TTL for programmes, courses, fee schedules
- [x] Build a Banner mock adapter for local dev and tests (honours the same interface, returns seeded data)
- [x] Implement `/api/banner/health` returning connectivity status
- [x] Document every Banner field the portal consumes in docs/BANNER_SURFACE.md

### Security Hardening

- [x] Store Banner API credentials in `.env`, never in code or logs
- [x] Use TLS for all Banner connections (verify SSL certificates)
- [x] Sanitise all data received from Banner before storing or rendering (prevent stored XSS)
- [x] Implement request timeout (10s) and circuit breaker on Banner calls to prevent cascading failures
- [ ] Rate limit Banner API calls to stay within Ellucian quotas
- [ ] Log all Banner write operations to audit_log (before and after values)
- [x] Ensure mock adapter never leaks into production (`BANNER_MODE` validated at startup)

### Tests

- Unit tests against the mock adapter for every function (>=80% coverage)
- Integration tests against Banner sandbox for at least one read and one write per entity
- Cache tests: TTL expiry, cache miss, invalidation
- Failure-mode tests: Banner down, timeout, malformed response

### Success Criteria

- `banner_client` exposes all read/write functions needed by later parts
- Mock adapter lets every other part develop without live Banner
- Cache demonstrably reduces Banner calls under load
- Banner writes are verified by direct Banner check (per TOR acceptance 5.1)

### Parallelism

Can proceed in parallel with Parts 4, 6, 7, 8 — other parts consume the mock adapter until credentials arrive.

---

## Part 6: New-Student Application Flow

Deliver TOR 2.1.2 and 2.1.3: online application form, document upload, status tracking, notifications, staff review, offer letter PDF generation, offer accept/decline.

### Substeps

- [x] Build `POST /api/applications` (public) with Pydantic validation of personal details, prior qualifications, programme preference, campus preference
- [x] Build document upload endpoint (PDF/JPG/PNG, 5MB max, MIME-type check)
- [x] Build staff endpoints: `GET /api/admin/applications` (with status filters), `GET /api/admin/applications/{id}`, `PUT /api/admin/applications/{id}/status`
- [x] Build the public application form as a Next.js Server Component (form shell) + Client Component (interactive fields with Zod validation), posting via Server Actions to the backend
- [x] Build staff review UI under `app/(admin)/applications/`: queue with filters, detail view, approve / request docs / reject with mandatory reason
- [x] Build bulk-action endpoint (e.g. approve-all matching filter)
- [ ] Build offer letter PDF generator in the backend using WeasyPrint (HTML template with FNU letterhead → PDF)
- [x] Build offer acceptance page at `app/(public)/offer/[token]/` — server-renders the offer content from the backend, shows accept/decline buttons
- [x] Wire notifications on every status change (email via stub sender, SMS via stub)
- [x] Support conditional offers for school leavers

### Security Hardening

- [x] Validate and sanitise all application form inputs server-side (Pydantic + custom validators)
- [x] File upload security: MIME-type allowlist (PDF/JPG/PNG only), magic-byte validation (not just extension), 5MB size limit enforced at proxy and backend, randomised filenames, store outside web root
- [x] Rate limit application submissions (5/hour per IP) to prevent spam
- [x] Offer acceptance tokens: cryptographically random (secrets.token_urlsafe), single-use, 7-day expiry, hashed in DB
- [x] Staff review endpoints: require_role("staff", "admin") — never publicly accessible
- [x] Bulk actions: require_role("admin") with mandatory audit log entry per affected record
- [ ] PDF generation: sanitise all interpolated values to prevent HTML injection in templates
- [ ] Public application form: CSRF protection via next-auth token

### Tests

- Backend unit tests for form validation, document MIME/size, PDF generator (>=80% coverage)
- Backend integration tests: full application → review → approve → offer issued → accept flow
- Frontend unit tests for form validation messages, queue filters
- E2E Playwright: apply as prospective student, review as staff, accept offer
- Tests: reject with no reason → 400; document >5MB → 400
- Visual regression on the generated offer PDF (golden file)

### Success Criteria

- TOR 2.1.2 and 2.1.3 complete
- Application number auto-assigned and unique
- Every status change fires a notification
- Offer PDF renders with FNU letterhead
- Audit log captures every approve/reject with actor and reason
- Public application form loads in <3s on 3G (SSR benefit)

### Parallelism

Independent of Parts 5, 7, 8. Depends on Part 3 (auth) and Part 4 (frontend shell).

---

## Part 7: Course Registration, Timetable, Invoicing

Deliver TOR 2.1.4, 2.1.5, 2.1.7, 2.1.8, 2.1.9: programme display, course selection with prereq validation, timetable clash detection, confirmation, automatic invoice, timetable view with .ics export, my courses, my grades.

### Substeps

- [x] Build `GET /api/programme` returning approved programme with structure (core + elective) from Banner
- [x] Build `GET /api/courses` listing selectable courses filtered by programme rules, semester availability, prereq status
- [x] Implement prereq validator — evaluates completed/exempted courses against each candidate course; returns reason-blocked where applicable
- [x] Implement timetable clash detector over offerings
- [x] Implement credit-point tracker vs programme requirements
- [x] Build `POST /api/registration/confirm` — atomic: Banner register, invoice create, student_id activate, roster write
- [x] Build `GET /api/invoices`, `GET /api/invoices/{id}.pdf` (WeasyPrint, itemised course-level breakdown)
- [x] Build `GET /api/timetable` and `/api/timetable.ics` export
- [x] Build `GET /api/grades` with cumulative and semester GPA
- [x] Build `GET /api/my-courses` — registered courses with Moodle link, assessment schedule, lecturer contact
- [x] Build Next.js pages for each: `app/(portal)/register/`, `app/(portal)/timetable/`, `app/(portal)/courses/`, `app/(portal)/grades/`, `app/(portal)/invoices/`
- [x] Use Server Components for read-only views (timetable, courses, grades) to avoid shipping JS for data that doesn't change client-side
- [x] Use Client Components for the course-selection flow (interactive prereq checks, clash warnings, confirm step)
- [x] Partial-load pricing: invoice is sum of course fees, not programme flat fee

### Security Hardening

- [x] Registration confirm is atomic — partial failures must roll back (no orphaned Banner writes)
- [x] All registration endpoints enforce require_role("student") — students can only register themselves
- [x] Invoice PDF generation: sanitise all interpolated values; validate invoice belongs to requesting user
- [x] Timetable/grades endpoints: scope queries to authenticated user's ID (prevent IDOR)
- [x] .ics export: validate output contains no PII beyond what the student should see
- [x] Rate limit registration confirm (3/minute per user) to prevent accidental double-registration

### Tests

- Backend unit tests: prereq validator, clash detector, GPA calculator, fee calculator (>=80% coverage)
- Backend integration tests: full register → invoice → retrieve invoice PDF cycle
- Frontend unit tests for course-selection state, clash-warning UI
- E2E Playwright: student picks courses, sees clash warning, resolves, confirms, sees invoice
- Banner write verification: after confirm, a direct Banner query shows the registration

### Success Criteria

- TOR 2.1.4, 2.1.5, 2.1.7, 2.1.8, 2.1.9 complete
- Prereq validation blocks correctly with clear explanation
- Clash detection catches overlapping offerings
- Invoice generated automatically on confirm, itemised by course
- .ics export imports cleanly into Google Calendar and Apple Calendar

### Parallelism

Depends on Part 5 (Banner client). Independent of Parts 6, 8, 9, 10, 11.

---

## Part 8: Payment Gateway Integration

Deliver TOR 2.2: M-PAiSA + MyCash integration, bank transfer fallback, payment plan engine, reconciliation interface.

### Substeps

- [ ] Procure M-PAiSA and MyCash sandbox merchant accounts (blocking — FNU-initiated, developer-integrated)
- [x] Build `payments` service in the backend with provider adapters: `MpaisaAdapter`, `MycashAdapter`, `BankTransferAdapter` (plus `StubPaymentAdapter` for dev/CI)
- [x] Build `POST /api/payments/initiate` — returns gateway redirect URL + portal-side attempt record
- [x] Build `POST /api/payments/callback/mpaisa` and `/api/payments/callback/mycash` — signature-verified, idempotent (the reverse proxy must route these without next-auth in the way)
- [x] Build `POST /api/payments/bank-confirm` (finance role) for manual bank-transfer confirmation
- [x] Build payment plan engine: schedule generator, overdue marking, reminder triggers (scheduler job deferred to Part 11 notifications)
- [x] Build reconciliation endpoints and finance UI under `app/(admin)/finance/`: payments received, daily report, CSV export, method breakdown
- [ ] Wire notifications: 3-day reminder, overdue, de-registration warning (requires APScheduler — deferred to Part 11)
- [x] Build student-facing "Make a Payment" page at `app/(portal)/pay/` — Client Component with method picker, amount or full balance, retry on failure
- [x] Build finance bank-transfer confirmation UI

### Security Hardening

- [x] Payment callback endpoints: verify gateway-specific HMAC signature on every callback; reject unsigned/invalid
- [x] Callback endpoints: exclude from CSRF/auth middleware (they are gateway-initiated), but verify by signature
- [x] Idempotency: same callback replayed must produce exactly one state change (use gateway_reference as dedup key)
- [x] Payment initiation: validate amount ≤ invoice balance; prevent negative or zero amounts (Pydantic `gt=0`)
- [x] Store gateway credentials (MPAISA_SECRET, MYCASH_SECRET) in `.env` only, never log them
- [x] Rate limit payment initiation (10/minute per user) via slowapi
- [x] Reconciliation endpoints: require_role("finance", "admin") — never student-accessible
- [x] Bank-confirm endpoint: require_role("finance", "admin") with mandatory audit log
- [x] All payment amounts validated server-side — never trust client-submitted amounts
- [x] Production config validator rejects `PAYMENTS_MODE=stub` and requires live merchant credentials
- [ ] TLS cert pinning on gateway API calls (deferred — depends on live merchant contracts)

### Tests

- Backend unit tests for each adapter, signature verification, idempotency, schedule generator (>=80% coverage)
- Integration tests against M-PAiSA / MyCash sandbox
- Callback replay test: same callback twice → one state change
- E2E: initiate → redirect → callback → status updated
- Reconciliation report produces matching totals vs payment_attempts table
- Load test: 100 concurrent payment initiations without deadlock

### Success Criteria

- TOR 2.2 complete
- At least 1 confirmed live sandbox test per gateway (per TOR acceptance 5.1)
- Failed/timed-out transactions handled with clear error and retry
- Reconciliation report exports clean CSV/Excel
- Payment plan reminders fire at configured intervals

### Parallelism

Depends on Part 3 (auth) and Part 7 (invoices exist). Independent of Parts 6, 9, 10, 11.

---

## Part 9: AI Chatbot — Connectivity and FAQ-Augmented Q&A

Deliver TOR 2.3.1 and 2.3.2 backend: OpenRouter integration, FAQ-augmented LLM responses, escalation pathway, admin API for managing training data and query logs.

### Substeps

- [x] Set up OpenRouter client in backend; load `OPENROUTER_API_KEY` from `.env` via python-dotenv
- [x] Build `POST /api/chat` endpoint: accept message, retrieve matching `chatbot_knowledge` entries (keyword search for MVP; embedding search noted as future enhancement), compose system prompt, call LLM, return reply
- [x] Implement authenticated mode: when student is logged in, the LLM receives their account balance, registered courses (via Banner), so it can answer "what's my balance" style questions
- [x] Implement escalation: when confidence low or user asks for human, flag conversation `escalated`, create `enquiries` row, notify staff
- [x] Build `/api/admin/chatbot/knowledge` CRUD for FAQ entries and document uploads
- [x] Build `/api/admin/chatbot/conversations` — searchable, filterable log
- [x] Build `/api/admin/chatbot/analytics` — totals, resolution rate, top categories, escalation rate
- [x] Seed initial FAQ from `seed/chatbot_faq.json` covering entry requirements, deadlines, fees, graduation

### Security Hardening

- [x] OPENROUTER_API_KEY stored in `.env`, never logged, never included in error responses
- [x] Sanitise all user messages before including in LLM prompt (prevent prompt injection)
- [x] Limit message length (2000 chars max) and conversation history depth (50 turns) to prevent token abuse
- [x] Rate limit chat endpoint: 30 req/min per user (authenticated), 10 req/min per IP (unauthenticated)
- [x] Authenticated mode: only inject the requesting student's data into the prompt (never other students')
- [x] Strip PII from chatbot conversation logs visible in admin UI (mask student IDs, email addresses)
- [x] Admin knowledge CRUD: require_role("admin") — prevent privilege escalation via FAQ manipulation
- [x] Validate FAQ content for script injection before storing (sanitise HTML)

### Tests

- Backend unit tests for prompt composition, knowledge retrieval, escalation trigger logic (>=80% coverage)
- Integration test: "2+2" health-check query returns "4"
- Integration test: "What are the entry requirements for Bachelor of Nursing?" hits FAQ, returns FAQ answer
- Integration test: authenticated student asks "what's my balance" — LLM response includes correct balance
- Escalation test: "I want to speak to a human" creates enquiry row
- TOR 20-query acceptance set: validate minimum 20 predefined queries return sensible answers

### Success Criteria

- TOR 2.3.1 and 2.3.2 backend complete
- 20/20 predefined test queries return acceptable answers
- Escalation pathway logs queries and creates enquiries
- Admin can add/edit/delete FAQ without deploying code
- API key loaded securely from `.env`, never logged

### Parallelism

Depends on Part 3 (auth). Independent of Parts 6, 7, 8, 10, 11.

---

## Part 10: Chatbot UI — Floating Widget, Admin Screens

Deliver TOR 2.3 frontend: embedded floating chatbot widget, conversation UI, plus the admin chatbot screens (training data, query log, analytics).

### Substeps

- [x] Build floating widget as a Client Component rendered in the authenticated portal layout — bottom-right, minimised by default, expand on click
- [x] Build conversation UI: message list, input, send, typing indicator, escalation banner
- [x] Wire to `/api/chat` (batched JSON — backend returns full reply plus sources; streaming deferred)
- [x] Build admin training-data UI at `app/(admin)/admin/chatbot/knowledge/`: list, add, edit, soft-delete FAQ
- [x] Build admin query log UI at `app/(admin)/admin/chatbot/conversations/`: searchable, filterable, detail modal with full message history
- [x] Build admin analytics UI at `app/(admin)/admin/chatbot/analytics/`: total queries, resolution rate, top categories, escalation rate
- [x] Ship a standalone embeddable widget — dedicated `/embed/chatbot` route plus `public/embed/chatbot.js` bootstrapper that injects an iframe; a third-party site embeds with a single `<script>` tag

### Security Hardening

- [x] Embeddable widget: middleware sets `Content-Security-Policy: frame-ancestors <allowed>` on `/embed/*` and removes `X-Frame-Options` only there (all other routes keep `X-Frame-Options: DENY`). Allowed origins controlled by `NEXT_PUBLIC_EMBED_ALLOWED_ORIGINS`
- [x] Chat input/reply: rendered as React text (auto-escaped); backend rejects FAQ entries containing `<script>`/`javascript:`/`onerror=`/`onload=` markers
- [x] Widget: portal mode passes `Authorization: Bearer` header from the next-auth session; embed mode is anonymous — no token exposure cross-origin
- [ ] Standalone bundle: Subresource Integrity (SRI) hash in the `<script>` tag (deferred — requires release pipeline that hashes the static file; documented as prod-deployment task)

### Tests

- Vitest unit tests for widget, conversation, admin screens (>=80% coverage)
- E2E: open widget, ask question, receive reply, escalate
- E2E: admin adds FAQ, student's subsequent question is answered using new FAQ
- Mobile: widget is usable at 375px, doesn't block core content
- Embed test: the standalone bundle loads on a static HTML page outside the portal

### Success Criteria

- TOR 2.3 complete (backend + frontend)
- Widget embeddable on external site (single script tag)
- Admin screens functional without touching code

### Parallelism

Depends on Part 9 (chatbot backend). Independent of Parts 6, 7, 8, 11.

---

## Part 11: Profile, Student ID, Notifications

Deliver TOR 2.1.6, 2.1.10: My Account (balance, payment history, instalment schedule), profile view/edit, profile photo upload, digital student ID card with QR, plus the cross-cutting SMS/email notification system (TOR D9).

### Substeps

- [x] Build `GET /api/account` — current balance, payment history, instalment schedule with status indicators (delivered Part 8)
- [x] Build outstanding-fees banner logic in the portal shell (render when overdue exists)
- [x] Build `GET /api/profile`, `PUT /api/profile` — address, phone, email, emergency contact
- [x] Build `POST /api/profile/photo` — 2MB max, resized to 400x400 on the backend, stored securely
- [x] Build digital student ID card view at `app/(portal)/id-card/` with signed QR payload
- [x] Build `/verify/[qr_payload]/` public Server Component route returning student photo, name, programme, validity
- [x] Build notification service in the backend: queue → sender → status writeback
- [x] Implement email sender (SMTP via Mailtrap in dev, SendGrid/Mailgun in prod)
- [x] Implement SMS sender (Vodafone Fiji SMS API or mock)
- [x] Seed `notification_templates` with: payment reminder, registration confirmation, de-registration warning, deadline, offer issued, application status changes
- [x] Build admin UI at `app/(admin)/communications/` for sending batch SMS/email to filtered student groups (TOR 2.4.3)

### Security Hardening

- [x] Photo upload: validate magic bytes (not just extension/MIME), strip EXIF data (GPS, device info), resize server-side
- [x] Photo storage: bytes held in the DB (`profile_photos.image_data`, `LargeBinary`), served via auth-gated `/api/profile/photo/me` endpoint — never on the filesystem
- [x] Profile update: users can only update their own profile (scope to authenticated user's ID)
- [x] QR payload: cryptographically signed (HMAC-SHA256) — verification page validates signature before displaying info
- [x] QR verification page (/verify/[qr]): display only non-sensitive info (name, programme, validity) — no grades, balance, or contact info
- [x] Notification templates: sanitise all variable interpolation to prevent injection in email/SMS bodies (CR/LF stripped, 500-char clamp, non-identifier keys rejected)
- [x] Batch communications: require_role("admin", "staff") with audit log of sender, recipient count, and content hash
- [x] SMTP/SMS credentials: stored in `.env`, never logged

### Tests

- Backend unit tests: balance calculator, photo resizer, QR signer, template renderer (>=80% coverage)
- Integration: notification enqueue → mock provider → status updated
- E2E: student uploads photo, views ID card; scans QR → verify page loads server-rendered
- Batch-send test: filter group, preview count, send, every recipient gets a row in notifications

### Success Criteria

- TOR 2.1.6, 2.1.10, D9 complete
- Outstanding fees banner shows on overdue
- QR verification page loads public info only (no sensitive data), server-rendered for instant load
- Batch send completes with full send-history log

### Parallelism

Depends on Part 3 and Part 5. Independent of Parts 6, 8, 9, 10.

---

## Part 12: Staff Administration Panel

Deliver TOR 2.4: application management (already largely in Part 6, finish remaining pieces), student record management, enquiry management. Communications is delivered in Part 11.

### Substeps

- [x] Build student search API (by ID, name, programme, campus, enrolment status) and UI at `app/(admin)/students/`
- [x] Build student detail view: personal, programme, courses, payments, grades, letters, notes
- [x] Build manual override endpoints: prereq waiver, late registration, overload — mandatory reason, audit logged
- [x] Build enquiry management UI at `app/(admin)/enquiries/`: log, assignment, status transitions (open → in_progress → resolved), student feedback prompt on resolution
- [x] Build processing-time dashboard cards (receipt timestamp → decision timestamp)
- [x] Wire audit_log writes on every override and status change

### Security Hardening

- [x] All admin endpoints: require_role("staff", "admin") enforced via shared dependency
- [x] Student search: parameterised queries only (ORM); sanitise search input to prevent injection
- [x] Manual overrides (prereq waiver, late registration): require mandatory reason field; audit log captures before/after state, actor, timestamp, IP
- [x] Student detail view: scoped to admin role — students cannot view other students' records
- [x] Enquiry management: assignment changes audit-logged; resolution notes cannot be edited after submission
- [ ] Export endpoints (CSV/Excel): require_role("admin", "staff"); log every export with actor and filter criteria (deferred — exports land in Part 14 alongside the KPI dashboard)

### Tests

- Backend unit tests for search, override authorisation, audit log invariants (>=80% coverage)
- Integration test: staff overrides prereq → audit_log entry exists with actor, reason, before/after
- E2E: staff opens enquiry, assigns, resolves, student rates
- Tests: override without reason → 400

### Success Criteria

- TOR 2.4 complete
- All admin actions logged in audit_log
- Search returns results in <500ms for the seeded dataset

### Parallelism

Depends on Part 6 (applications), Part 7 (registrations), Part 11 (communications). Largely independent of Parts 8, 13.

---

## Part 13: Lecturer Interface

Deliver TOR 2.6: class rosters and grade entry.

### Substeps

- [ ] Build `GET /api/lecturer/rosters` — courses the authenticated lecturer teaches, with roster per course (name, ID, programme, status)
- [ ] Build roster export to CSV / Excel / PDF (backend generates)
- [ ] Build `POST /api/lecturer/grades` — per course per assessment period, with draft / submit-for-review / finalised workflow; timestamp captured for KPI
- [ ] Build lecturer frontend under `app/(lecturer)/`: course list, roster table, grade entry grid with autosave (Client Component)
- [ ] Grades write through to Banner via `banner_client.submit_grade`

### Security Hardening

- [ ] All lecturer endpoints: require_role("lecturer") — lecturers can only access their own courses
- [ ] Roster access: scoped to courses assigned to the authenticated lecturer (prevent IDOR)
- [ ] Grade submission: validate grades are within allowed range; require workflow state transition (draft → submitted → finalised)
- [ ] Grade finalisation: irreversible without admin override; audit log captures every grade change with before/after values
- [ ] Export endpoints: require_role("lecturer") scoped to own courses; log exports

### Tests

- Backend unit tests for roster query, grade workflow state machine (>=80% coverage)
- Integration: draft → submit → finalise; each transition logged
- E2E: lecturer logs in, sees rosters, enters grades, finalises, student sees updated grade on "My Grades"
- Banner write verification: grade appears in Banner

### Success Criteria

- TOR 2.6 complete
- Grade finalisation triggers "My Grades" update in real time (or next refresh)
- Roster export opens cleanly in Excel

### Parallelism

Depends on Part 5 (Banner client). Independent of Parts 6, 8, 9, 10, 11, 12.

---

## Part 14: KPI Dashboard

Deliver TOR 2.5: role-based dashboards (VC/SLT, Dean, Section Head, Individual Staff, Finance) with auto-generated and manual KPIs, drill-down, date-range filters, traffic-light indicators.

### Substeps

- [ ] Build KPI computation workers (APScheduler jobs): consume transactional data (registrations, payments, timestamps, chatbot), populate `kpi_values`
- [ ] Build manual-input UI for section heads (target: under 5 min/day per person)
- [ ] Build KPI target configuration UI for system administrators
- [ ] Build VC/SLT dashboard at `app/(admin)/dashboard/vc/` — Server Component for the heavy data fetch, Client Component for the drill-down and filters
- [ ] Build Dean/Manager view at `app/(admin)/dashboard/dean/`: college/function performance table, programme viability trend
- [ ] Build Section Head view at `app/(admin)/dashboard/section-head/`: team workload, individual staff table, manual input forms
- [ ] Build Individual Staff view at `app/(admin)/dashboard/me/`: own KPIs, targets, trend
- [ ] Build Finance view at `app/(admin)/dashboard/finance/`: revenue breakdown, plan compliance, aged receivables, daily reconciliation, CSV/Excel export
- [ ] Build drill-down: institution → college → function → individual
- [ ] Build date-range filters: current semester, previous, YTD, custom

### Security Hardening

- [ ] Role-based dashboard access enforced at both backend (require_role) and frontend (middleware + component-level checks)
- [ ] VC/SLT dashboard: require_role("vc", "admin"); Dean: require_role("manager", "admin"); etc.
- [ ] Drill-down data scoped to the authenticated user's organisational unit (deans cannot see other colleges)
- [ ] Manual KPI inputs: validate data ranges; audit log captures every manual entry with actor and timestamp
- [ ] Finance dashboard: require_role("finance", "admin"); export endpoints audit-logged
- [ ] Date-range filters: validate input ranges server-side (prevent excessively wide queries that could cause DoS)

### Tests

- Backend unit tests: KPI computation functions, aggregation, drill-down resolver (>=80% coverage)
- Integration: simulate transactions → KPI values update correctly
- Role-based access tests: each view only visible to its role (enforced in middleware + backend)
- Snapshot tests for dashboard layouts

### Success Criteria

- TOR 2.5 complete
- All six views render with accurate data for the seeded dataset
- KPI targets configurable without code changes
- Drill-down works end-to-end

### Parallelism

Depends on Parts 6, 7, 8 (transactional data exists) and Part 11 (notifications for some KPIs). Largely independent of Parts 10, 13.

---

## Part 15: Non-Functional Hardening

Deliver TOR 2.7: security, performance, accessibility, browser compatibility.

### Substeps

- [ ] Security audit: verify HTTPS/TLS enforced at the proxy, bcrypt everywhere, no secrets in `NEXT_PUBLIC_*` or logs, SQL injection prevention (parameterised queries only), XSS prevention (React escapes + CSP headers set by Next.js middleware), CSRF tokens on state-changing requests (next-auth handles this)
- [ ] Performance: add response-time logging middleware on backend, set up p95/p99 monitoring, cache programme/fee lookups, add DB indexes identified by slow-query analysis
- [ ] Tune Next.js: verify Server Components where applicable, trim client bundles, enable `output: "standalone"` for small images
- [ ] Accessibility sweep: run axe-core across all pages, fix findings, verify keyboard navigation, screen-reader compatibility on core student flows
- [ ] Browser matrix test: Chrome, Firefox, Safari, Edge (latest 2 each); Android 10+ Chrome; iOS 15+ Safari
- [ ] Mobile responsiveness audit: every student page at 375px, 414px, 768px
- [ ] Error handling: backend returns user-friendly error payloads, never stack traces; frontend has a global error boundary and Next.js `error.tsx` routes
- [ ] Automated daily Postgres backups (pg_dump cron; document restore procedure)
- [ ] 24/7 readiness: health-check dashboard, alerting hooks on backend and frontend
- [ ] Run OWASP ZAP automated scan against staging; remediate all high/critical findings
- [ ] Verify all security headers present (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
- [ ] Verify rate limiting active on auth, chat, and payment endpoints
- [ ] Verify global exception handler catches all unhandled errors (no stack traces to clients)
- [ ] Verify Swagger/OpenAPI docs disabled in production
- [ ] Verify backend container runs as non-root user
- [ ] Verify all secrets loaded from environment variables (grep for hardcoded values)
- [ ] Dependency audit: `uv audit` (Python) and `npm audit` (Node.js); zero known vulnerabilities
- [ ] Verify Docker base images are current; no known CVEs in base layers
- [ ] Penetration test: IDOR on student-scoped endpoints, CSRF on state-changing endpoints, auth bypass attempts
- [ ] Verify audit_log coverage: every admin action, every financial transaction, every grade change

### Tests

- Security scan: run OWASP ZAP baseline; zero high-severity findings
- Load test (Locust): 500 concurrent users, p95 < 3s on 3G-throttled profile (measured through the reverse proxy, not direct to backend)
- Accessibility: axe-core on all pages returns zero critical issues
- Browser matrix: Playwright runs green across Chromium, Firefox, WebKit
- Backup restore drill: restore from last night's backup into a fresh DB, verify data integrity

### Success Criteria

- TOR 2.7 and TOR acceptance 5.2 complete
- Load test report passes 500 concurrent users < 3s p95
- WCAG 2.1 AA verified on core student flows
- No critical or high bugs outstanding

### Parallelism

Not parallelisable — this is the hardening pass across everything already built.

---

## Part 16: UAT, Deployment, Documentation, Post-Launch Support

Deliver TOR deliverables D10–D16: test report, UAT support, production deployment, source code repo, technical docs, user guides, post-launch support.

### Substeps

- [ ] Produce test report and bug log (D10)
- [ ] Facilitate UAT with FNU staff on-site or extended remote (D11, Week 7)
- [ ] Triage UAT bugs, fix blockers, defer non-blockers with sign-off
- [ ] Production deployment (D12): provision two containers (frontend, backend) behind the reverse proxy, Postgres with daily backup, DNS, HTTPS cert via Let's Encrypt or FNU-provided, monitoring, first production user tested
- [ ] Finalise source repo (D13): README, commit history clean
- [ ] Finalise technical documentation (D14): architecture, API (OpenAPI spec auto-published), ops runbook
- [ ] Produce user guides (D15): student guide, staff guide, video walkthroughs
- [ ] Stand up post-launch support (D16): on-call for critical issues, Weeks 9–10

### Security Hardening

- [ ] Production secrets: generate cryptographically random JWT_SECRET and NEXTAUTH_SECRET (64+ chars each)
- [ ] Production database: separate DB user with minimal privileges (no SUPERUSER, no CREATE DATABASE)
- [ ] Production Postgres: TLS-encrypted connections, restrict to application container IPs only
- [ ] DNS: configure CAA records to restrict certificate issuance to authorised CAs
- [ ] Enable Dependabot / Renovate on GitHub repo for automated dependency security alerts
- [ ] Document incident response procedure: who to call, how to rotate compromised secrets, how to revoke sessions
- [ ] Verify production `.env` contains no default/placeholder values (jwt_secret != "change-me")
- [ ] Enable structured JSON logging in production (no PII in log entries)
- [ ] Set up uptime monitoring with alerting (health endpoint polling every 60s)

### Tests

- User guides tested with at least one non-technical FNU staff member
- Deployment smoke test on production: login, register a test course, make a sandbox payment, log out
- Rollback drill: verify the rollback procedure works (swap containers back to previous image tag)

### Success Criteria

- System in production and accessible to students by Monday 15 June 2026 (hard deadline)
- All TOR deliverables D1–D16 signed off
- Payment gateway processes live transactions (min 1 confirmed live test per gateway)
- AI chatbot correctly answers minimum 20 predefined test queries
- KPI dashboard displays accurate data from portal transactions
- No critical/high bugs outstanding

### Parallelism

Not parallelisable — this is the final mile.

---

## Top Risks and Mitigations

### Risk 1: Banner API Access Timing

**Risk**: FNU provides Banner API credentials late, blocking Parts 5, 7, 13, and any live integration testing.

**Likelihood**: High. Banner credential provisioning depends on FNU IT and Ellucian coordination.

**Impact**: High. Without credentials, live Banner integration cannot be tested.

**Mitigation**: The `banner_client` module ships with a mock adapter from day one (Part 5). All other parts develop and test against the mock. The mock honours the same interface, so switching to live credentials requires only a config change (`BANNER_MODE=live`). Integration tests against the real Banner sandbox are gated behind the credential arrival but do not block feature development.

### Risk 2: Payment Gateway Sandbox Credentials

**Risk**: M-PAiSA and MyCash sandbox merchant accounts are FNU-initiated. Delays in procurement block live sandbox testing of the payment flow.

**Likelihood**: Medium. Requires FNU to engage with Vodafone (M-PAiSA) and Digicel (MyCash).

**Impact**: Medium. Payment UI and backend logic can be built against stub adapters, but end-to-end gateway testing cannot happen without sandbox credentials.

**Mitigation**: Payment adapters are built with a stub mode that simulates the full initiate/callback lifecycle. The stub returns realistic responses (including failure scenarios) so the payment plan engine, reconciliation reports, and student-facing UI can be fully developed and tested. Once sandbox credentials arrive, integration tests are run against the real sandbox to verify signature verification and callback handling.

### Risk 3: FNU Brand Assets and Letterhead

**Risk**: Final brand colours, logo, and letterhead template are not yet confirmed. Building UI and PDF templates against provisional colours risks rework.

**Impact**: Low-medium. Colour changes are centralised in Tailwind config; letterhead affects PDF templates.

**Mitigation**: All colour tokens are defined once in `frontend/tailwind.config.ts` and consumed via Tailwind utility classes. Changing the palette is a single-file update. PDF templates (offer letters, invoices) use an HTML/CSS template with a placeholder letterhead image that can be swapped without code changes. Request brand assets by end of Week 2 to avoid rework during UAT.
