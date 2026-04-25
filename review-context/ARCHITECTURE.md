# Architecture

## Component Diagram

```
                         +------------------+
                         |   Reverse Proxy  |
                         |  (nginx / Caddy) |
                         +--------+---------+
                                  |
                    +-------------+-------------+
                    |                           |
             /api/* |                           | /*
                    v                           v
          +-----------------+         +------------------+
          |    FastAPI       |         |    Next.js        |
          |    Backend       |         |    Frontend       |
          |  (Python 3.12)   |         |  (App Router)     |
          +---------+-------+         +------------------+
                    |
          +---------+---------+
          |                   |
          v                   v
  +---------------+   +---------------+
  |  PostgreSQL   |   |  Banner       |
  |  (portal DB)  |   |  (Oracle)     |
  +---------------+   +---------------+
```

## Services

### Reverse Proxy (nginx or Caddy)

- Terminates TLS in production
- Routes `/api/*` to the FastAPI backend container
- Routes everything else to the Next.js frontend container
- Routes payment gateway callbacks (`/api/payments/callback/*`) directly to backend without auth middleware interference

### Next.js Frontend

- App Router with React Server Components by default, Client Components only where interactivity is required
- `next-auth` (Auth.js) manages session cookies, wrapping the JWT issued by FastAPI
- OpenAPI-generated TypeScript types for all API payloads (never hand-written)
- Server Components fetch data server-side for fast first-paint (public landing, offer acceptance, QR verification)
- Client Components handle interactive flows (course selection, chatbot widget, grade entry)
- Tailwind CSS with FNU brand tokens
- Standalone output mode for small Docker images

### FastAPI Backend

- All business logic, data access, and external integrations
- Pydantic v2 request/response models on every route
- Role-based access control via a shared FastAPI dependency
- JWT (HS256) issued on login, verified on every authenticated request
- SQLAlchemy 2.x async sessions for Postgres
- Alembic for migrations
- APScheduler for background jobs (payment reminders, KPI rollups)

### PostgreSQL

- Portal-owned data only: applications, sessions, chatbot logs, KPI inputs, payments, notifications, audit trail
- See `docs/DATABASE.md` for full schema
- Daily `pg_dump` backups in production

### Ellucian Banner (Oracle)

- System of record for students, programmes, courses, enrolments, fees, grades, staff
- Accessed exclusively through the `banner_client` module in the backend
- Read-heavy with selective writes (student creation, course registration, grade submission, invoice creation)
- Programme/course/fee data cached with 15-minute TTL
- Mock adapter available for local development and testing

## Data Flow

### Authentication

```
Browser → Next.js login page → POST /api/auth/login (via proxy)
  → FastAPI verifies credentials against `users` table
  → Returns JWT
  → next-auth stores JWT in httpOnly session cookie
  → Subsequent requests: next-auth attaches JWT to backend calls
```

### Public Application (unauthenticated)

```
Browser → Next.js SSR landing page (Server Component, fast first-paint)
  → User fills application form (Client Component, Zod validation)
  → POST /api/applications (public, no auth required)
  → FastAPI validates, stores in Postgres `applications` table
  → Notification queued (email confirmation)
```

### Course Registration (authenticated)

```
Browser → Next.js portal → GET /api/programme (Server Component)
  → FastAPI → banner_client.get_programmes() (cached)
  → User selects courses (Client Component)
  → Frontend checks prereqs/clashes via API calls
  → POST /api/registration/confirm
  → FastAPI (atomic): banner_client.register_course() + create invoice + update roster
  → Response: confirmation + invoice ID
```

### Payment

```
Browser → POST /api/payments/initiate
  → FastAPI creates payment_attempt, calls gateway API, returns redirect URL
  → Browser redirects to M-PAiSA / MyCash
  → Gateway calls POST /api/payments/callback/{provider} (signature-verified)
  → FastAPI updates payment_attempt status, writes to Banner invoice
  → Student sees updated balance on next page load
```

### AI Chatbot

```
Browser → Floating widget (Client Component) → POST /api/chat
  → FastAPI retrieves matching chatbot_knowledge entries (keyword search)
  → Composes system prompt with FAQ context + student data (if authenticated)
  → Calls OpenRouter LLM (anthropic/claude-sonnet-4)
  → Returns response; stores conversation turn
  → If escalation triggered: creates enquiry row, notifies staff
```

## Auth Model

- FastAPI issues a JWT (HS256) containing `user_id`, `role`, `exp`
- The JWT is passed to `next-auth` which wraps it in an httpOnly, Secure, SameSite=Lax session cookie
- The frontend `apiFetch` helper reads the JWT from the next-auth session and attaches it as a Bearer token on backend calls
- FastAPI middleware verifies the JWT on every authenticated request
- Sessions are tracked in the `sessions` table; logout revokes the session server-side
- Role-based access is enforced via a shared `require_role()` FastAPI dependency

## Deployment Topology

### Local Development (Docker Compose)

```
docker-compose.yml:
  - frontend:  Node 20, Next.js dev server, port 3000
  - backend:   Python 3.12, uvicorn, port 8000
  - postgres:  PostgreSQL 16, port 5432
  - proxy:     nginx, port 80 (routes /api/* → backend, /* → frontend)
```

### Production

```
  - frontend container: Next.js standalone build
  - backend container:  uvicorn behind gunicorn
  - PostgreSQL: managed instance with daily backups
  - Reverse proxy: nginx or Caddy with TLS (Let's Encrypt or FNU-provided cert)
  - DNS: portal.fnu.ac.fj (or as assigned by FNU IT)
```

### Container Images

- `Dockerfile.frontend`: multi-stage (install deps → build → standalone copy), ~150MB
- `Dockerfile.backend`: Python 3.12 slim + uv install, ~300MB

## Security

- HTTPS/TLS enforced at the proxy layer
- bcrypt for password hashing
- JWT secrets in environment variables, never in code or `NEXT_PUBLIC_*`
- Parameterised queries only (SQLAlchemy ORM)
- React auto-escaping + CSP headers for XSS prevention
- CSRF protection via next-auth
- Payment callbacks verified by gateway signature
- File uploads: MIME-type validation, size limits, stored outside web root
- Audit log on every admin action

## Performance Targets

- Public pages: <3s first contentful paint on simulated 3G (SSR)
- Authenticated pages: <3s p95 under 500 concurrent users
- Banner reads: cached with 15-minute TTL to reduce load
- Database: indexes on all foreign keys and common query patterns

## Public Deployment (Demonstration)

The MVP will be publicly accessible on the web for demonstration purposes. This requires production-grade security from day one.

### Deployment Options (evaluated in Part 16)

- **Option A**: Single VPS (e.g. DigitalOcean, Vultr, Linode) running Docker Compose behind Caddy (automatic TLS)
- **Option B**: Container platform (e.g. Railway, Render, Fly.io) with managed Postgres
- **Option C**: FNU-provisioned infrastructure behind their network

The choice is deferred to Part 16. The Docker Compose setup is designed to work on any option with minimal changes.

### Security Hardening for Public Exposure

All of the following are enforced before any public deployment:

**Transport**
- TLS 1.2+ only, enforced at the reverse proxy (Caddy auto-provisions Let's Encrypt certs)
- HSTS header with `max-age=31536000; includeSubDomains`
- HTTP redirects to HTTPS

**Headers (set by reverse proxy and Next.js middleware)**
- `Content-Security-Policy`: restrict script-src, style-src, connect-src to own origin; no inline scripts except Next.js nonce-based
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`: disable camera, microphone, geolocation unless explicitly needed

**Authentication and sessions**
- bcrypt (cost factor 12) for password hashing
- JWT with HS256, short-lived (60 min), rotatable secret
- Session cookies: `httpOnly`, `Secure`, `SameSite=Lax`
- Session revocation tracked server-side in `sessions` table
- Account lockout after 5 failed login attempts (15-min cooldown)
- Password reset tokens: single-use, 1-hour expiry, hashed in DB

**Input validation**
- Pydantic v2 on every backend route (request and response)
- Zod on every frontend form
- Parameterised queries only (SQLAlchemy ORM, no raw SQL interpolation)
- File uploads: MIME-type allowlist (PDF, JPG, PNG only), size limits, stored outside web root with randomised filenames

**Rate limiting**
- Backend rate limiting via `slowapi` or middleware: 100 req/min per IP on auth endpoints, 30 req/min on chatbot
- Reverse proxy rate limiting as a second layer

**CSRF**
- next-auth CSRF token on all state-changing requests from the frontend
- Payment gateway callbacks verified by provider-specific signature (not CSRF-protected, but signature-verified and idempotent)

**Secrets management**
- All secrets in environment variables, loaded via `python-dotenv` on backend, `next.config.ts` `serverRuntimeConfig` on frontend
- `.env` is git-ignored; `.env.example` committed as a safe template
- No secrets in `NEXT_PUBLIC_*` variables (client-visible)
- No secrets in Docker images (passed at runtime via env)
- API keys rotatable without code changes

**Logging and monitoring**
- Structured JSON logging on the backend (no secrets or PII in logs)
- Request ID on every request for traceability
- Audit log on every admin action (append-only table)
- Health check endpoints for uptime monitoring

**Dependency security**
- `pip-audit` / `uv audit` in CI for Python vulnerabilities
- `npm audit` in CI for Node.js vulnerabilities
- Dependabot or Renovate enabled on the GitHub repo
- Docker base images pinned to specific digests, rebuilt on security advisories

**Database**
- Postgres connections via TLS in production
- Separate DB user with minimal privileges (no SUPERUSER)
- Daily automated backups with tested restore procedure
- Connection pooling with max connection limits

**Error handling**
- Backend never exposes stack traces to clients (returns structured error payloads)
- Frontend global error boundary + Next.js `error.tsx` routes
- 500 errors logged server-side with request context, client sees generic message
