# Security — FNU Web Portal MVP

Consolidated reference for how the portal is hardened. Updated through Part 15.

---

## Transport

- HTTPS enforced at the reverse proxy in production (Let's Encrypt via the FNU-provided CA; DNS CAA records restrict issuance during Part 16 deployment).
- HSTS: `max-age=31536000; includeSubDomains; preload` on every response (nginx + Next.js middleware).
- `frame-ancestors 'none'` / `X-Frame-Options: DENY` on all routes **except** `/embed/*`, which uses `Content-Security-Policy: frame-ancestors <NEXT_PUBLIC_EMBED_ALLOWED_ORIGINS>`.
- Host hardening: `server_tokens off` (nginx), `TrustedHostMiddleware` on the FastAPI app in production.

## Authentication & session management

- Passwords: bcrypt, cost factor 12.
- JWTs: HS256, 60-min expiry, JTI stored as SHA-256 hash in `sessions` table; logout revokes server-side.
- next-auth issues an httpOnly/Secure/SameSite=Lax session cookie wrapping the JWT.
- Account lockout: 5 failed attempts triggers a 15-minute lockout (persisted in `users.locked_until`).
- Rate limits (slowapi):
  - `/api/auth/login` — 10/min
  - `/api/auth/reset-password` — 3/min
  - `/api/auth/reset-password/confirm` — 5/min
  - `/api/applications` — 5/hour per IP
  - `/api/applications/documents` — 20/hour per IP
  - `/api/chat` — 30/min authenticated, 10/min anonymous
  - `/api/payments/initiate` — 10/min per user
  - `/api/registration/confirm` — 3/min per user
- Password reset: no email enumeration (always returns the same success message).
- CSRF: next-auth manages CSRF tokens for Credentials callbacks; state-changing portal operations are authenticated via Bearer tokens from the session cookie on same-origin requests, and Server Actions run with next-auth's CSRF gate.

## Authorisation

- Single shared dependency: `require_role("role", …)` in [backend/src/backend/auth.py](../backend/src/backend/auth.py).
- Students scoped to own data via `user.banner_id` on every read.
- Admin routes refuse lower-privileged roles; backend tests codify this (`tests/test_security.py`).
- Manual overrides (prereq waiver, late registration, overload) require a reason ≥10 chars and always land in `audit_log`.

## Input validation & output safety

- Pydantic v2 on every FastAPI route — no raw dicts.
- `EmailStr` on email fields; length clamps on all free-text fields.
- File uploads: MIME allowlist + magic-byte check + 5 MB cap for application docs, 2 MB for profile photos.
- Profile photo processing: validates magic bytes, strips EXIF, resizes 400×400, stored as `LargeBinary` in `profile_photos`.
- PDF generation (invoice + lecturer roster): all interpolated values escaped via `html.escape` — prevents HTML injection in WeasyPrint output.
- Chatbot: user messages sanitised before inclusion in the LLM prompt; 2000-char message cap; 50-turn history cap; PII masked in admin-visible conversation logs.
- Banner data: inbound strings sanitised by `LiveBannerClient._sanitise_str*`; mock adapter returns known-safe data only.

## Banner integration

- `banner_client` is the single gateway — no direct Oracle/HTTP calls anywhere else in the code.
- All Banner writes pass through `AuditedBannerClient`:
  - `banner.register_course`, `banner.submit_grade`, `banner.create_invoice`, `banner.create_student` each write a row to `audit_log` with actor + target + payload.
  - Actor is injected via `set_banner_actor(user.id)` at the API call site (ContextVar).
- In-process token bucket (`BANNER_RATE_LIMIT_PER_SEC`, default 20/sec) throttles outbound calls to stay within Ellucian quotas.
- Circuit breaker: 5 consecutive failures opens the breaker for 60 s (`LiveBannerClient`).
- TLS verification enabled on every Banner call (`verify_ssl=True`).

## Payments

- Callback endpoints verify HMAC-SHA256 signatures using constant-time comparison.
- Idempotent: `gateway_reference` is the dedup key; replaying a callback yields a single state change.
- Production config validator rejects `PAYMENTS_MODE=stub` and requires all live merchant credentials.
- Reconciliation and bank-confirm endpoints are role-gated (`finance`, `admin`) and audit-logged.
- Payment amounts validated server-side with `gt=0` — no client-trust surface.

## Secrets

- All secrets in `.env` (git-ignored). `.env.example` uses safe placeholders.
- Production startup rejects:
  - `JWT_SECRET` ∈ {"change-me", "", <32 chars}
  - `ID_CARD_SECRET` ∈ {"id-card-change-me", "", <32 chars}
  - `PAYMENTS_MODE=stub`
  - `BANNER_MODE=mock`
  - Missing SMTP credentials when `NOTIFICATIONS_MODE=live`
- No secrets in `NEXT_PUBLIC_*` (client-exposed env vars limited to non-sensitive values like `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_EMBED_ALLOWED_ORIGINS`).
- Server-side Next.js fetches use `INTERNAL_API_URL` (not exposed to the browser).

## Logging & audit

- Fire-and-forget `write_audit_log()` on: login/logout, application status changes, manual overrides, enquiry transitions, grade draft/submit/finalise, payment bank-confirm, Banner writes, KPI manual input, KPI recompute trigger, finance CSV export, batch-communications.
- Global exception handler (main.py): unhandled errors log with stack trace server-side; client receives `{"detail": "Internal server error"}` only.
- Response-time middleware logs one structured `response_ms=` line per request for p50/p95/p99.
- Swagger/OpenAPI JSON served only in non-production (`ENVIRONMENT != production`).

## Container hardening

- Backend runs as non-root `app` user (`docker/Dockerfile.backend`).
- `.dockerignore` excludes `.venv`, `node_modules`, `.next`, `__pycache__`, `.git`.
- nginx hardening headers set at the proxy: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, HSTS, Permissions-Policy, Content-Security-Policy, X-Permitted-Cross-Domain-Policies.

## Verification

- Response headers + auth-bypass: `backend/tests/test_security.py`.
- Banner audit + rate limit: `backend/tests/test_banner_audit.py`.
- Cross-browser axe-core smoke: `frontend/tests/e2e/axe.spec.ts`.
- Runtime scans: `scripts/zap_baseline.sh` (OWASP ZAP baseline), `scripts/loadtest.sh` (Locust).
- Dependency audit: `uv pip list --outdated` (Python), `npm audit` (Node).

## Known deferred items

| Item | Reason | Target |
|---|---|---|
| Payment gateway TLS cert pinning | Depends on live M-PAiSA / MyCash merchant contracts | Part 16 deployment |
| Standalone embed bundle SRI hash | Needs release pipeline that hashes static files | Part 16 deployment |
| Browser matrix execution (WebKit/Firefox) | Playwright browser binaries must be installed per environment (`npm run e2e:install`) | Operator task |
| 500-user load test on dev hardware | PLAN.md target is for staging; dev defaults to 100 users / p95 < 5 s | Run with `USERS=500 P95_MS=3000 ./scripts/loadtest.sh` on staging |

## Incident response (MVP)

1. **Compromised JWT secret** — rotate `JWT_SECRET`, restart backend (all sessions invalidated), notify users to re-login. Past JWTs fail signature verification immediately.
2. **Compromised session** — `DELETE FROM sessions WHERE user_id = '<uuid>';` revokes all that user's tokens.
3. **Suspected breach** — rotate every secret in `.env`, redeploy, restore from the last known-good backup if DB integrity is in question (see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)).
4. **Rate-limit bypass** — tighten slowapi limits in `backend/src/backend/rate_limit.py` + the per-route decorator, redeploy. Consider moving to a Redis-backed limiter if process count >1.
