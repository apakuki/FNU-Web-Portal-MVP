# FNU Web Portal — Troubleshooting Guide

Operations and maintenance flowcharts for diagnosing and resolving issues. Each section corresponds to a build part and covers problems discovered during development and testing, plus anticipated production issues.

Use this guide top-down: start at the symptom, follow the decision tree, apply the fix.

---

## Table of Contents

1. [General: Stack Startup and Docker](#1-general-stack-startup-and-docker)
2. [Part 2: Scaffolding — Services, Proxy, Health](#2-part-2-scaffolding--services-proxy-health)
3. [Part 3: Database and Authentication](#3-part-3-database-and-authentication)
4. [Part 4: Portal Shell, Login UI, Public Landing](#4-part-4-portal-shell-login-ui-public-landing)
5. [Part 5: Banner Integration Layer](#5-part-5-banner-integration-layer)
6. [Part 6: Application Flow](#6-part-6-application-flow)
7. [Part 7: Registration, Timetable, Invoicing](#7-part-7-registration-timetable-invoicing)
8. [Part 8: Payment Gateway](#8-part-8-payment-gateway)
9. [Part 9–10: AI Chatbot](#9-parts-910-ai-chatbot)
10. [Part 11: Profile, Student ID, Notifications](#10-part-11-profile-student-id-notifications)
11. [Part 12–13: Staff Admin and Lecturer](#11-parts-1213-staff-admin-and-lecturer)
12. [Part 14: KPI Dashboard](#12-part-14-kpi-dashboard)
13. [Part 15–16: Hardening and Deployment](#13-parts-1516-hardening-and-deployment)

---

## 1. General: Stack Startup and Docker

### 1.1 `./scripts/start.sh` fails immediately

```
Symptom: "Error: Docker is not installed" or "Error: Docker is not running"
│
├─ Is Docker Desktop installed?
│  ├─ NO → Install Docker Desktop from https://www.docker.com/products/docker-desktop
│  └─ YES
│     │
│     ├─ Is Docker Desktop running? (check menu bar / system tray)
│     │  ├─ NO → Start Docker Desktop, wait for "Docker Desktop is running" status
│     │  └─ YES
│     │     │
│     │     └─ Run: docker info
│     │        ├─ ERROR → Docker daemon not ready yet. Wait 30s, retry.
│     │        └─ OK → Re-run ./scripts/start.sh
```

### 1.2 `docker compose up` fails during build

```
Symptom: Build error during docker compose up --build
│
├─ "COPY public/ ..." fails (frontend Dockerfile)
│  └─ FIX: Ensure frontend/public/ directory exists
│     └─ touch frontend/public/.gitkeep
│
├─ "uv sync" fails with "can't find packages" (backend Dockerfile)
│  └─ FIX: Check backend/pyproject.toml has:
│     [tool.hatch.build.targets.wheel]
│     packages = ["src/backend"]
│
├─ ".venv" copied into image causes platform mismatch (macOS → Linux)
│  └─ FIX: Ensure .dockerignore at PROJECT ROOT (not docker/) contains:
│     .venv
│     node_modules
│     .next
│     __pycache__
│     .git
│
├─ "npm install" or "npm run build" fails in frontend container
│  └─ Check: Is node_modules in .dockerignore? (it should be)
│  └─ Check: Does frontend/package.json have valid dependencies?
│  └─ Try: Delete frontend/node_modules locally, rebuild
│
└─ Generic build failure
   └─ Run: docker compose build --no-cache
   └─ Check: Is there enough disk space? docker system df
   └─ Try: docker system prune -a (removes unused images)
```

### 1.3 Containers start but one exits immediately

```
Symptom: docker ps shows fewer than 4 containers
│
├─ Which container exited?
│  └─ Run: docker compose ps -a
│     │
│     ├─ postgres exited
│     │  └─ Run: docker compose logs postgres
│     │  └─ Common: Port 5432 already in use
│     │     └─ FIX: Stop local postgres: brew services stop postgresql
│     │     └─ OR: lsof -i :5432 → kill the process
│     │
│     ├─ backend exited
│     │  └─ Run: docker compose logs backend
│     │  └─ Common: "ModuleNotFoundError" → .venv platform mismatch (see 1.2)
│     │  └─ Common: Can't connect to postgres → postgres not healthy yet
│     │     └─ FIX: backend depends_on postgres with service_healthy condition (already configured)
│     │     └─ Check: docker compose logs postgres for readiness
│     │
│     ├─ frontend exited
│     │  └─ Run: docker compose logs frontend
│     │  └─ Common: INTERNAL_API_URL not set → check docker-compose.yml environment
│     │  └─ Common: Build error → see 1.2
│     │
│     └─ proxy (nginx) exited
│        └─ Run: docker compose logs proxy
│        └─ Common: upstream "backend" not found → backend container is down
│           └─ FIX: Fix backend first (see above), then restart proxy
│        └─ Common: nginx.conf syntax error
│           └─ FIX: docker exec <proxy> nginx -t (test config)
```

### 1.4 Port conflicts

```
Symptom: "port is already allocated" during docker compose up
│
├─ Which port?
│  ├─ 80   → A web server or previous container is using port 80
│  ├─ 3000 → A local npm dev server is running
│  ├─ 5432 → A local PostgreSQL is running
│  └─ 8000 → A local backend dev server is running
│
└─ FIX for any port:
   ├─ Find process: lsof -i :<PORT>
   ├─ Kill it: kill <PID>
   └─ OR stop previous containers: ./scripts/stop.sh
```

---

## 2. Part 2: Scaffolding — Services, Proxy, Health

### 2.1 `/api/health` returns error or is unreachable

```
Symptom: curl http://localhost/api/health fails
│
├─ Is the proxy running?
│  └─ curl -s -o /dev/null -w "%{http_code}" http://localhost
│     ├─ Connection refused → proxy container is down (see 1.3)
│     └─ 502 Bad Gateway → backend is down or unreachable from proxy
│        └─ FIX: Check backend container: docker compose logs backend
│
├─ Does backend respond directly?
│  └─ curl http://localhost:8000/api/health
│     ├─ Connection refused → backend container is down (see 1.3)
│     ├─ 200 but proxy gives 502 → nginx can't reach backend
│     │  └─ Check: Are backend and proxy on the same Docker network?
│     │  └─ Run: docker network ls / docker network inspect
│     └─ 500 → Backend error
│        └─ Run: docker compose logs backend
│        └─ Common: Postgres connection failed
│           └─ Check postgres is healthy: docker compose ps
│           └─ Check DATABASE_URL in docker-compose.yml
│              └─ Must use service name "postgres" not "localhost"
│
├─ Does frontend respond directly?
│  └─ curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
│     ├─ Connection refused → frontend container is down (see 1.3)
│     └─ 200 → Frontend is fine, issue is proxy routing
```

### 2.2 Home page loads but shows "Backend unavailable"

```
Symptom: Landing page renders but health status shows "Backend unavailable"
│
├─ Is the health API working via proxy?
│  └─ curl http://localhost/api/health
│     ├─ Returns JSON with status: ok → Issue is SSR fetch inside Docker
│     │  └─ Check: INTERNAL_API_URL is set to "http://backend:8000" in docker-compose.yml
│     │  └─ IMPORTANT: Do NOT use NEXT_PUBLIC_API_URL for server-side fetches
│     │     (NEXT_PUBLIC_ vars are baked in at build time, not available at runtime)
│     └─ Fails → See 2.1
```

### 2.3 Automated tests fail

```
Symptom: Backend or frontend tests fail
│
├─ Backend tests (uv run pytest tests/ -v)
│  ├─ Import errors → Run from backend/ directory
│  ├─ "Multiple elements with text: ok" → Use getAllByText not getByText
│  └─ Ruff/mypy lint failures
│     └─ Auto-generated migration files → Add to extend-exclude in pyproject.toml:
│        [tool.ruff]
│        extend-exclude = ["src/backend/db/migrations/versions"]
│
├─ Frontend tests (npx vitest run)
│  ├─ Import errors → Check vitest.config.ts alias: "@" → resolve(__dirname, ".")
│  ├─ "window is not defined" after tests pass
│     └─ This is a jsdom teardown race, not a real failure
│     └─ FIX: Add afterEach(() => { cleanup(); }) to affected test files
│  └─ Module mock issues
│     └─ vi.mock() must be called before imports in the same file
```

### 2.4 CI pipeline fails on GitHub

```
Symptom: GitHub Actions CI job fails
│
├─ Which job failed?
│  ├─ backend lint → Fix ruff/mypy issues locally, push
│  ├─ frontend lint → Fix eslint/tsc issues locally, push
│  ├─ contract check → Regenerate types: cd frontend && npm run generate:types
│  │  └─ Commit updated api-types.ts
│  └─ Docker build → See section 1.2
```

---

## 3. Part 3: Database and Authentication

### 3.1 Alembic migration fails

```
Symptom: alembic upgrade head fails
│
├─ "ModuleNotFoundError: No module named 'src'"
│  └─ FIX: Check backend/src/backend/db/migrations/env.py has:
│     sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
│     at the top of the file
│
├─ "relation already exists"
│  └─ Tables were created outside of Alembic (manual SQL or prior failed run)
│  └─ FIX: Reset the database:
│     docker compose down -v   (WARNING: destroys data)
│     docker compose up -d
│     Wait for postgres, then run alembic upgrade head again
│
├─ "could not connect to server"
│  └─ Is DATABASE_URL correct?
│     ├─ Running locally: DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal
│     ├─ Running in Docker: Use postgres (service name) not localhost
│     └─ Is postgres running and healthy? docker compose ps
│
├─ "target database is not up to date"
│  └─ FIX: alembic stamp head (mark current state), then run new migrations
│
└─ Alembic version file has lint errors
   └─ Expected — auto-generated files are excluded from ruff:
      [tool.ruff]
      extend-exclude = ["src/backend/db/migrations/versions"]
```

### 3.2 Seed command fails

```
Symptom: python -m src.backend.seed fails
│
├─ "relation 'users' does not exist"
│  └─ Migrations not applied yet
│  └─ FIX: Run alembic upgrade head first
│
├─ Duplicate key violation
│  └─ Seed is idempotent — this should not happen
│  └─ If it does: the seed script should check for existing users before insert
│
├─ "ModuleNotFoundError"
│  └─ Run from the backend/ directory
│  └─ Ensure DATABASE_URL is set (export or inline)
│
└─ Seed succeeds but all users show "exists"
   └─ This is normal on subsequent runs (idempotent)
```

### 3.3 Login via API returns 401

```
Symptom: POST /api/auth/login returns 401 "Invalid credentials"
│
├─ Are the credentials correct?
│  └─ Test accounts:
│     student@fnu.ac.fj / student123
│     admin@fnu.ac.fj   / admin123
│     staff@fnu.ac.fj   / staff123
│     finance@fnu.ac.fj / finance123
│     lecturer@fnu.ac.fj/ lecturer123
│     manager@fnu.ac.fj / manager123
│     vc@fnu.ac.fj      / vc123456  (note: different password pattern)
│     student2@fnu.ac.fj/ student123
│
├─ Was the seed run?
│  └─ Run the seed command and check output
│
├─ Account locked out? (5 failed attempts in 15 minutes)
│  └─ Check: docker exec docker-postgres-1 psql -U fnu -d fnu_portal \
│     -c "SELECT email, failed_login_attempts, locked_until FROM users WHERE email='student@fnu.ac.fj';"
│  └─ FIX: Reset lockout:
│     docker exec docker-postgres-1 psql -U fnu -d fnu_portal \
│     -c "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE email='student@fnu.ac.fj';"
│
└─ Request format wrong?
   └─ Must be JSON with Content-Type header:
      curl -X POST -H "Content-Type: application/json" \
        -d '{"email":"student@fnu.ac.fj","password":"student123"}' \
        http://localhost/api/auth/login
```

### 3.4 JWT token rejected on /me

```
Symptom: GET /api/auth/me returns 401 with valid-looking token
│
├─ Is the token expired?
│  └─ Default expiry: 60 minutes (JWT_EXPIRE_MINUTES in config.py)
│  └─ FIX: Login again to get a fresh token
│
├─ Was the session revoked? (logout was called)
│  └─ The JTI is hashed and checked against the sessions table
│  └─ FIX: Login again to get a new session
│
├─ Is JWT_SECRET consistent?
│  └─ Check .env file: JWT_SECRET must be the same value used to issue and verify
│  └─ If running in Docker: check docker-compose.yml env_file points to ../.env
│
└─ Is the Authorization header correct?
   └─ Must be: Authorization: Bearer <token>
   └─ No extra spaces, no "bearer" (case sensitive for some clients)
```

### 3.5 Audit log empty after login

```
Symptom: No auth.login entries in audit_log table
│
├─ Is the audit_log table created?
│  └─ Check: docker exec docker-postgres-1 psql -U fnu -d fnu_portal -c "\dt audit_log"
│
├─ Audit writes are fire-and-forget (asyncio.create_task)
│  └─ If the backend crashes immediately after login, the task may not complete
│  └─ Check backend logs for errors: docker compose logs backend
│
└─ Query correctly?
   └─ SELECT action, target_type, occurred_at FROM audit_log ORDER BY occurred_at DESC LIMIT 5;
```

---

## 4. Part 4: Portal Shell, Login UI, Public Landing

### 4.1 Login form shows error but credentials are correct

```
Symptom: Browser login shows "Invalid email or password" with correct credentials
│
├─ Does the API login work directly?
│  └─ curl -X POST -H "Content-Type: application/json" \
│       -d '{"email":"student@fnu.ac.fj","password":"student123"}' \
│       http://localhost/api/auth/login
│     ├─ 200 → Issue is in next-auth configuration
│     │  └─ Check frontend/lib/auth.ts:
│     │     - INTERNAL_API_URL must resolve inside Docker (http://backend:8000)
│     │     - The CredentialsProvider authorize() function must return user object, not null
│     │  └─ Check browser DevTools > Network tab for the actual error response
│     └─ 401 → API-level issue (see section 3.3)
│
├─ Is NEXTAUTH_SECRET set?
│  └─ Check .env: NEXTAUTH_SECRET=<some-value>
│  └─ This must be set for next-auth to encrypt session cookies
│
└─ Is NEXTAUTH_URL set correctly?
   └─ For Docker: NEXTAUTH_URL=http://localhost
   └─ For local dev: NEXTAUTH_URL=http://localhost:3000
```

### 4.2 After login, redirected back to /login (infinite loop)

```
Symptom: Login succeeds (API returns 200) but browser keeps redirecting to /login
│
├─ Is the session cookie being set?
│  └─ Browser DevTools > Application > Cookies
│  └─ Look for "next-auth.session-token" cookie
│     ├─ Missing → next-auth callback not returning user correctly
│     │  └─ Check lib/auth.ts jwt() and session() callbacks
│     └─ Present → Middleware may not be reading it correctly
│        └─ Check middleware.ts: getToken() needs NEXTAUTH_SECRET
│
├─ Is the callbackUrl valid?
│  └─ Check URL: /login?callbackUrl=...
│  └─ The callbackUrl must be a relative path (e.g., /dashboard)
│
└─ Cookie domain mismatch?
   └─ Ensure NEXTAUTH_URL matches the domain you're accessing
```

### 4.3 Sidebar not visible on desktop

```
Symptom: On desktop (>1024px), the sidebar is missing
│
├─ Is the viewport actually >1024px?
│  └─ Check: browser DevTools responsive mode
│
├─ Check the aside element's classes:
│  └─ Must include: lg:static lg:translate-x-0
│  └─ Without these, sidebar is always off-screen
│
└─ CSS not loading?
   └─ Check browser DevTools > Console for CSS errors
   └─ Verify Tailwind is compiled: check for globals.css in page source
```

### 4.4 Mobile hamburger menu doesn't work

```
Symptom: Hamburger icon visible but sidebar doesn't open on tap
│
├─ Is the component a Client Component?
│  └─ Layout must have "use client" directive at top
│  └─ Without it, useState won't work (Server Components can't have state)
│
├─ Check: onClick handler toggles sidebarOpen state
│  └─ Browser DevTools > React DevTools > inspect state
│
└─ Overlay not appearing?
   └─ Check z-index values: overlay z-30, sidebar z-40
   └─ A parent with overflow:hidden could clip the sidebar
```

### 4.5 Outstanding fees banner showing when it shouldn't (or vice versa)

```
Symptom: Banner appears with no balance, or doesn't appear when there is a balance
│
├─ Check the balanceCents prop passed to OutstandingFeesBanner
│  └─ Currently hardcoded to null in portal layout (shows nothing)
│  └─ Will be connected to real data in Part 11
│
├─ Banner logic:
│  └─ null → hidden (correct)
│  └─ 0 → hidden (correct)
│  └─ negative → hidden (correct)
│  └─ positive → visible with formatted FJD amount
│
└─ If connected to real data and showing wrong amount:
   └─ Check: Is balanceCents in cents (not dollars)?
   └─ 150000 cents = $1,500.00 FJD
```

### 4.6 Admin/lecturer layout not loading

```
Symptom: Navigating to /admin or /lecturer shows 404 or wrong layout
│
├─ Do the route group directories exist?
│  └─ frontend/app/(admin)/admin/page.tsx
│  └─ frontend/app/(lecturer)/lecturer/page.tsx
│  └─ Note: Route groups use parentheses (admin) but the URL path is /admin
│
├─ Is the layout file present?
│  └─ frontend/app/(admin)/layout.tsx
│  └─ frontend/app/(lecturer)/layout.tsx
│
└─ Are you authenticated?
   └─ /admin and /lecturer are protected routes
   └─ You'll be redirected to /login if not authenticated
   └─ Any role can access any route currently (role enforcement comes in later parts)
```

### 4.7 Next.js build fails

```
Symptom: npx next build fails
│
├─ "useSearchParams() without Suspense boundary"
│  └─ FIX: Wrap component using useSearchParams in <Suspense>
│  └─ See login page for the pattern: LoginPage wraps LoginForm in Suspense
│
├─ TypeScript errors
│  └─ Run: npx tsc --noEmit to see all errors
│  └─ Common: Missing types for session user → cast as any or define interface
│
├─ "Module not found" for @/ imports
│  └─ Check tsconfig.json has paths: { "@/*": ["./*"] }
│
└─ Out of memory during build
   └─ Increase Node memory: NODE_OPTIONS=--max-old-space-size=4096 npx next build
```

### 4.8 Focus outlines not visible (accessibility)

```
Symptom: Tab navigation works but no visible focus indicator
│
├─ Are focus-visible classes applied?
│  └─ Interactive elements should have: focus-visible:ring-2 focus-visible:ring-fnu-blue
│  └─ Or: focus:outline-none focus-visible:ring-2
│
├─ Browser-specific:
│  └─ Safari may not show :focus-visible by default
│  └─ Test in Chrome first, then cross-browser
│
└─ Tailwind CSS not including focus utilities?
   └─ Check globals.css @theme block is loaded
```

---

## 5. Part 5: Banner Integration Layer

### 5.1 Banner connection fails

```
Symptom: /api/banner/health returns {"status": "unavailable"}
│
├─ Is BANNER_MODE set correctly in .env?
│  ├─ "mock" → Should always return ok. If failing:
│  │  └─ Check backend logs: docker compose logs backend
│  │  └─ Verify banner module loads: uv run python -c "from src.backend.banner import get_banner_client"
│  └─ "live" → Real Banner credentials required
│     │
│     ├─ Are credentials configured in .env?
│     │  └─ BANNER_API_URL (e.g. https://banner.fnu.ac.fj/api)
│     │  └─ BANNER_API_KEY (Bearer token)
│     │
│     ├─ Can the backend reach Banner's network?
│     │  └─ From inside Docker: docker exec docker-backend-1 curl -k $BANNER_API_URL/health
│     │  └─ DNS/firewall issue? Banner may require VPN or IP whitelisting
│     │
│     ├─ Is the circuit breaker open?
│     │  └─ After 5 consecutive failures, calls fail fast for 60 seconds
│     │  └─ Check backend logs for "circuit breaker opened"
│     │  └─ Fix: resolve connectivity issue, then wait 60s for circuit to half-open
│     │
│     └─ Are credentials valid?
│        └─ Test: curl -H "Authorization: Bearer $BANNER_API_KEY" $BANNER_API_URL/health
│        └─ Contact FNU IT if credentials are rejected
│
└─ Check /api/health — reports banner status alongside postgres
```

### 5.2 Cache returning stale data

```
Symptom: Programme or course data is outdated after Banner update
│
├─ Cache TTL is 15 minutes (BANNER_CACHE_TTL_SECONDS=900)
│  └─ Wait 15 minutes or restart the backend to clear cache
│
├─ Force cache invalidation:
│  └─ Restart backend: docker compose restart backend
│
├─ Reduce TTL for development:
│  └─ Set BANNER_CACHE_TTL_SECONDS=30 in .env
│
└─ What is cached vs not cached?
   ├─ Cached: programmes, courses, fee schedules
   └─ Not cached: students, invoices, offerings, rosters
```

### 5.3 Backend fails to start with BANNER_MODE error

```
Symptom: ValueError "BANNER_MODE=mock is not allowed in production"
│
├─ In production, BANNER_MODE must be "live"
│  └─ Set BANNER_MODE=live in .env
│  └─ Set BANNER_API_URL and BANNER_API_KEY
│
└─ Symptom: ValueError "BANNER_API_URL and BANNER_API_KEY must be set"
   └─ BANNER_MODE=live requires both URL and key
   └─ Check .env has non-empty values for both
```

### 5.4 Banner request timeout

```
Symptom: Slow Banner responses or TimeoutError in logs
│
├─ Default timeout is 10 seconds (BANNER_TIMEOUT_SECONDS)
│  └─ Increase if Banner is legitimately slow: BANNER_TIMEOUT_SECONDS=30
│
├─ Check Banner server health directly
│  └─ curl -w "time_total: %{time_total}\n" $BANNER_API_URL/health
│
└─ If timeouts are frequent, circuit breaker will activate after 5 failures
   └─ Check logs: "Banner circuit breaker opened after 5 failures"
   └─ All requests will fail fast for 60 seconds, then retry
```

---

## 6. Part 6: Application Flow

### 6.1 Application form submission fails

```
Symptom: POST /api/applications returns 400, 422, or 500
│
├─ 422 Unprocessable Entity → Pydantic validation error
│  └─ Check response body for field-level errors
│  └─ Common issues:
│     ├─ Missing applicant_email → required field
│     ├─ Invalid email format → must be a valid email (EmailStr)
│     ├─ Empty prior_qualifications → at least 1 required (min_length=1)
│     ├─ Missing personal_details → all fields required
│     ├─ Name too long → max 100 characters
│     └─ Invalid date_of_birth → must be YYYY-MM-DD format
│
├─ 429 Too Many Requests → Rate limited (5 applications/hour per IP)
│  └─ Wait and retry later
│  └─ Check: slowapi rate limiter on POST /api/applications
│
├─ 500 Internal Server Error → Backend bug
│  └─ Check: docker compose logs backend
│  └─ Common: database connection issue
│     └─ Is postgres running? docker compose ps
│     └─ Are migrations applied? alembic upgrade head
│
└─ Application number format: APP-YYYY-NNNNNN (auto-generated)
```

### 6.2 Document upload fails

```
Symptom: POST /api/applications/documents returns 400
│
├─ "not allowed" in error → MIME type rejected
│  └─ Only allowed: application/pdf, image/jpeg, image/png
│  └─ FIX: Convert document to PDF, JPG, or PNG before uploading
│
├─ "does not match" in error → Magic byte mismatch
│  └─ File claims to be PDF/JPG/PNG but content doesn't match
│  └─ Common: renamed .txt or .exe file to .pdf
│  └─ FIX: Use a genuine PDF/image file, not a renamed file
│
├─ "5MB" in error → File too large
│  └─ Maximum file size: 5 MB (MAX_FILE_SIZE = 5 * 1024 * 1024)
│  └─ FIX: Compress or resize the document
│  └─ Note: nginx also limits at 10MB (client_max_body_size)
│
├─ 429 Too Many Requests → Rate limited (20 uploads/hour per IP)
│  └─ Wait and retry
│
└─ Invalid document_type → Must be one of the recognised types
   └─ Valid types: transcript, id_document, passport_photo, other
```

### 6.3 Admin application queue not loading

```
Symptom: /admin/applications shows error or empty
│
├─ Authentication issue?
│  └─ Must be logged in as staff or admin role
│  └─ Check: user role in database
│     SELECT email, role FROM users WHERE email='staff@fnu.ac.fj';
│
├─ API returning error?
│  └─ Check browser DevTools > Network > /api/admin/applications
│  └─ 401 → Token expired, re-login
│  └─ 403 → Insufficient role (need staff or admin)
│  └─ 500 → Backend error, check docker compose logs backend
│
├─ Status filter not working?
│  └─ Check: query parameter format ?status=submitted
│  └─ Valid values: submitted, under_review, awaiting_documents,
│     approved, conditionally_approved, rejected
│
└─ Pagination issue?
   └─ Default: 20 per page
   └─ Check total count in response header
```

### 6.4 Status update / approval fails

```
Symptom: PUT /api/admin/applications/{id}/status returns error
│
├─ 400 Bad Request → Validation issue
│  └─ Is a reason provided for reject/awaiting_documents?
│     └─ These statuses REQUIRE a reason field
│  └─ Is the status value valid?
│     └─ Valid: submitted, under_review, awaiting_documents,
│        approved, conditionally_approved, rejected
│
├─ 404 Not Found → Application ID doesn't exist
│  └─ Check the ID in the URL matches an existing application
│  └─ docker exec docker-postgres-1 psql -U fnu -d fnu_portal \
│     -c "SELECT id, application_number FROM applications;"
│
├─ 403 Forbidden → Role not authorised
│  └─ Status updates require staff or admin role
│  └─ Bulk actions require admin role only
│
└─ Offer not created after approval?
   └─ Offers are auto-created on approve/conditionally_approved
   └─ Check: SELECT * FROM offers ORDER BY created_at DESC LIMIT 1;
   └─ Token is hashed in DB — the raw token is in the API response
```

### 6.5 Offer page not loading or expired

```
Symptom: /offer/<token> shows error or "expired"
│
├─ "Offer has expired" → Token is older than 7 days
│  └─ OFFER_TOKEN_EXPIRY_DAYS = 7
│  └─ Check: SELECT expires_at FROM offers WHERE id='...';
│  └─ Applicant must contact admissions for a new offer
│
├─ "Already responded" → Offer was already accepted or declined
│  └─ Offers are single-use
│  └─ Check: SELECT accepted_at, declined_at FROM offers WHERE id='...';
│
├─ 404 → Token not found or invalid
│  └─ Token is SHA256 hashed in DB for security
│  └─ The URL token must match the original generated token exactly
│  └─ Tokens are 48-byte URL-safe random strings (secrets.token_urlsafe(48))
│
└─ Page loads but buttons don't work?
   └─ Check browser DevTools > Console for JavaScript errors
   └─ Check Network tab for POST /api/offers/<token>/accept response
```

### 6.6 Offer PDF not generating

```
Symptom: Offer letter PDF endpoint returns error
│
├─ Is WeasyPrint installed in the backend container?
│  └─ Check Dockerfile.backend installs system dependencies (libpango, libcairo)
│
├─ Template rendering error?
│  └─ Check backend logs for Jinja2/HTML template errors
│
└─ FNU letterhead image missing?
   └─ Check the template references a valid image path
```

### 6.7 Notifications not logged after application events

```
Symptom: No notification records created after submission/approval
│
├─ Notification service is currently a stub (logs to DB only)
│  └─ No actual emails/SMS sent in this part
│  └─ Check: SELECT * FROM notifications ORDER BY created_at DESC LIMIT 5;
│
├─ Database error during notification write?
│  └─ Notifications are fire-and-forget (asyncio.create_task)
│  └─ Errors won't block the main request
│  └─ Check backend logs for notification errors
│
└─ Notification table missing?
   └─ Run: alembic upgrade head
   └─ Check: \dt notifications in psql
```

---

## 7. Part 7: Registration, Timetable, Invoicing

### 7.1 Prerequisite validation incorrectly blocking

```
Symptom: Student can't register for a course they should be eligible for
│
├─ Check prerequisite rules in Banner/mock data
│  └─ GET /api/courses should show prereq requirements per course
│
├─ Has the student completed/been exempted from prerequisites?
│  └─ Check student's completed courses via /api/grades
│
└─ Prereq waiver needed?
   └─ Staff can override via admin panel (Part 12)
   └─ Override is audit-logged with mandatory reason
```

### 7.2 Timetable clash not detected

```
Symptom: Student registers for overlapping courses without warning
│
├─ Are course offerings time data correct in Banner/mock?
│  └─ Check offering start/end times, days of week
│
├─ Clash detector logic:
│  └─ Compares day + time ranges for all selected courses
│  └─ Must account for same-day overlaps only
│
└─ Is the clash check running before confirmation?
   └─ POST /api/registration/confirm should validate before committing
```

### 7.3 Invoice PDF not itemised

```
Symptom: Invoice shows lump sum instead of per-course breakdown
│
├─ Check fee schedule data from Banner/mock
│  └─ Each course should have an individual fee
│
└─ Invoice generator should iterate registered courses and list each fee line
```

---

## 8. Part 8: Payment Gateway

### 8.1 Payment initiation fails

```
Symptom: POST /api/payments/initiate returns error
│
├─ Which gateway?
│  ├─ M-PAiSA → Check MPAISA_MERCHANT_ID and MPAISA_API_KEY in .env
│  ├─ MyCash → Check MYCASH_MERCHANT_ID and MYCASH_API_KEY in .env
│  └─ Bank Transfer → No gateway needed, manual confirmation by finance
│
├─ Is the gateway in stub mode?
│  └─ Stub mode simulates full lifecycle without real gateway
│  └─ Check: PAYMENT_MODE in .env (stub vs live)
│
└─ Is the invoice valid?
   └─ Payment must reference an existing unpaid invoice
```

### 8.2 Payment callback not received

```
Symptom: Payment completed on gateway but portal still shows "pending"
│
├─ Is the callback URL reachable from the gateway?
│  └─ For sandbox: callback URL must be publicly accessible
│  └─ For local dev: use ngrok or similar tunnel
│
├─ Is the callback route excluded from next-auth middleware?
│  └─ /api/payments/callback/* should NOT require authentication
│  └─ Check middleware.ts PUBLIC_PATHS
│
├─ Signature verification failing?
│  └─ Check backend logs for signature mismatch errors
│  └─ Verify merchant secret matches gateway configuration
│
└─ Idempotency:
   └─ Same callback replayed twice should result in one state change
   └─ If duplicate, check payment_attempts table for duplicate rows
```

### 8.3 Payment plan reminders not firing

```
Symptom: Students not receiving payment reminders
│
├─ Is APScheduler running?
│  └─ Check backend logs for scheduler startup messages
│
├─ Are notification senders configured?
│  └─ Email: SMTP settings in .env
│  └─ SMS: Vodafone API settings in .env
│
└─ Check notification queue:
   └─ SELECT * FROM notifications WHERE status='pending' ORDER BY created_at DESC LIMIT 10;
```

---

## 9. Parts 9–10: AI Chatbot

### 9.1 Chatbot returns no response

```
Symptom: POST /api/chat returns empty or error
│
├─ Is OPENROUTER_API_KEY set in .env?
│  └─ Must be a valid OpenRouter API key
│  └─ Test: curl https://openrouter.ai/api/v1/models -H "Authorization: Bearer $KEY"
│
├─ Is the API key valid and has credits?
│  └─ Check OpenRouter dashboard for usage/billing
│
├─ Can backend reach OpenRouter?
│  └─ docker exec <backend> curl -s https://openrouter.ai/api/v1/models
│  └─ DNS/firewall issue if connection fails
│
└─ Is chatbot_knowledge seeded?
   └─ Run seed to load FAQ entries
   └─ SELECT count(*) FROM chatbot_knowledge;
```

### 9.2 Chatbot answers are wrong or generic

```
Symptom: Chatbot doesn't use FAQ data, gives generic LLM responses
│
├─ Is knowledge retrieval working?
│  └─ Check backend logs for "matched knowledge" entries
│  └─ Verify FAQ entries exist for the topic being asked about
│
├─ System prompt includes FAQ context?
│  └─ Debug by checking the composed prompt in backend logs
│
└─ Add or update FAQ entries:
   └─ Admin UI: /admin/chatbot/knowledge
   └─ Or seed: seed/chatbot_faq.json
```

### 9.3 Escalation not creating enquiry

```
Symptom: "I want to speak to a human" doesn't create an enquiry
│
├─ Check escalation trigger keywords in chatbot logic
│
├─ Is the enquiries table present?
│  └─ \dt enquiries in psql
│
└─ Check backend logs for errors during enquiry creation
```

---

## 10. Part 11: Profile, Student ID, Notifications

### 10.1 Photo upload fails

```
Symptom: POST /api/profile/photo returns error
│
├─ File too large? (max 2MB)
│  └─ Resize before uploading
│
├─ Wrong format?
│  └─ Allowed: JPG, PNG
│
├─ nginx body size limit?
│  └─ Check nginx.conf: client_max_body_size 10m;
│
└─ Storage permissions?
   └─ Check backend has write access to photo storage directory
```

### 10.2 Student ID QR code not scanning

```
Symptom: QR code on digital student ID can't be scanned
│
├─ Is the QR payload correctly signed?
│  └─ Check backend QR generation logic
│
├─ Does /verify/[qr] route work?
│  └─ Open the QR URL directly in browser
│  └─ Should show student photo, name, programme, validity
│
└─ QR image quality:
   └─ Ensure sufficient contrast and size
   └─ Test with multiple scanner apps
```

### 10.3 Email/SMS notifications not sending

```
Symptom: Notifications queued but not delivered
│
├─ Email:
│  ├─ Dev: Using Mailtrap? Check Mailtrap inbox.
│  ├─ Prod: Check SMTP settings (host, port, credentials)
│  └─ Check: SELECT * FROM notifications WHERE type='email' AND status='failed';
│
├─ SMS:
│  ├─ Is Vodafone SMS API configured?
│  ├─ Are SMS API credentials valid?
│  └─ Check: SELECT * FROM notifications WHERE type='sms' AND status='failed';
│
└─ Notification service running?
   └─ Check backend logs for notification sender errors
```

---

## 11. Parts 12–13: Staff Admin and Lecturer

### 11.1 Staff can't access admin panel

```
Symptom: User with staff/admin role sees 403 on admin routes
│
├─ Check user role in database:
│  └─ SELECT email, role FROM users WHERE email='<email>';
│
├─ Is require_role() dependency applied to the endpoint?
│  └─ Check backend route decorator
│
└─ Frontend middleware only checks authentication, not role (currently)
   └─ Role-based frontend gating is implemented per-route in later parts
```

### 11.2 Lecturer grade submission fails

```
Symptom: POST /api/lecturer/grades returns error
│
├─ Is the grade workflow state correct?
│  └─ Must be: draft → submit-for-review → finalised
│  └─ Can't go backwards without admin override
│
├─ Does the lecturer own the course?
│  └─ Check class roster assignment
│
└─ Banner write failing?
   └─ Check BANNER_MODE — mock should always succeed
   └─ For live: check Banner API connectivity (see section 5.1)
```

---

## 12. Part 14: KPI Dashboard

### 12.1 KPI values showing zero or stale

```
Symptom: KPI dashboard shows all zeros or outdated values
│
├─ Is the KPI computation worker running?
│  └─ Check APScheduler logs in backend
│
├─ Is there transactional data to compute from?
│  └─ KPIs derive from registrations, payments, chatbot interactions
│  └─ Empty tables → zero KPIs
│
└─ Manual KPI input:
   └─ Section heads enter values via admin UI
   └─ Check kpi_values table: SELECT * FROM kpi_values ORDER BY period DESC LIMIT 10;
```

### 12.2 Wrong role sees wrong dashboard

```
Symptom: VC dashboard visible to non-VC user, or vice versa
│
├─ Check role-based access on both backend and frontend
│  └─ Backend: require_role() on each dashboard endpoint
│  └─ Frontend: role check in the dashboard page component
│
└─ Session expired and re-authenticated as different role?
   └─ Sign out and sign in again
```

---

## 13. Parts 15–16: Hardening and Deployment

### 13.1 HTTPS/TLS certificate issues

```
Symptom: Browser shows "Not Secure" or certificate error in production
│
├─ Is the TLS certificate valid?
│  └─ Let's Encrypt: certbot renew
│  └─ FNU-provided: check expiry date
│
├─ Is nginx configured for HTTPS?
│  └─ Check nginx.conf for ssl_certificate and ssl_certificate_key directives
│  └─ Port 443 must be exposed
│
└─ HTTP → HTTPS redirect configured?
   └─ Add: return 301 https://$host$request_uri; in port-80 server block
```

### 13.2 Production performance issues

```
Symptom: Pages load slowly (>3s) in production
│
├─ Is it the backend or frontend?
│  └─ Check: curl -w "time_total: %{time_total}" http://localhost/api/health
│  └─ If API is fast but page is slow → frontend bundle issue
│
├─ Frontend optimisation:
│  └─ Verify Server Components used where possible (no unnecessary "use client")
│  └─ Check bundle size: npx next build shows per-route sizes
│  └─ Enable standalone output: output: "standalone" in next.config.ts
│
├─ Backend optimisation:
│  └─ Add database indexes for slow queries
│  └─ Enable programme/fee cache (15-min TTL)
│  └─ Check: response-time logging middleware
│
└─ Infrastructure:
   └─ Is Postgres on fast storage (SSD)?
   └─ Is the server geographically close to Fiji?
   └─ Consider CDN for static assets
```

### 13.3 Database backup and restore

```
Symptom: Need to restore from backup
│
├─ Create manual backup:
│  └─ docker exec docker-postgres-1 pg_dump -U fnu fnu_portal > backup_$(date +%Y%m%d).sql
│
├─ Restore from backup:
│  └─ docker exec -i docker-postgres-1 psql -U fnu -d fnu_portal < backup_file.sql
│
├─ Automated daily backups:
│  └─ Configured via cron job (Part 15)
│  └─ Check: crontab -l for backup schedule
│
└─ Test restore procedure:
   └─ Restore into a fresh database, verify data integrity
   └─ Run: alembic current to verify schema version matches
```

### 13.4 Production rollback

```
Symptom: Deployed version has critical bug, need to rollback
│
├─ Container-based rollback:
│  └─ Re-tag previous Docker images
│  └─ docker compose pull && docker compose up -d
│
├─ Database rollback:
│  └─ alembic downgrade -1 (one revision back)
│  └─ WARNING: May cause data loss if migration added columns with data
│  └─ Prefer: restore from backup instead
│
└─ Git-based rollback:
   └─ git revert <commit> (creates new commit, preserves history)
   └─ Rebuild and redeploy
```

---

## Security Troubleshooting

### S.1 Backend fails to start with "JWT_SECRET must be set"

```
Symptom: Backend container exits with ValueError about JWT_SECRET
│
├─ This error only occurs when ENVIRONMENT=production
│  └─ FIX: Set JWT_SECRET to a cryptographically random 64+ character string in .env
│     └─ Generate: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
│
└─ For local development: set ENVIRONMENT=development (or omit — it defaults to development)
```

### S.2 Rate limiting blocking legitimate users

```
Symptom: Users get 429 "Too Many Requests" on login
│
├─ Is the user behind a shared IP (corporate NAT, university network)?
│  └─ Rate limiting is per IP — many users sharing one IP can trigger limits
│  └─ FIX: Increase the limit in auth.py or use X-Forwarded-For for rate key
│
├─ Is the user's account locked out?
│  └─ Check: SELECT email, failed_login_attempts, locked_until FROM users WHERE email='...';
│  └─ FIX: UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE email='...';
│
└─ Is the rate limit itself too low?
   └─ Login: 10/minute per IP (configurable in auth.py @limiter.limit)
   └─ Reset-password: 3/minute per IP
```

### S.3 Security headers missing from responses

```
Symptom: Security scan reports missing headers
│
├─ Are you testing via the nginx proxy (port 80)?
│  └─ Headers are set by both nginx AND Next.js middleware
│  └─ Direct backend access (port 8000) only has the global exception handler, not nginx headers
│
├─ Check nginx.conf has the add_header directives
│  └─ Verify: curl -D - http://localhost -o /dev/null
│
└─ Check Next.js middleware is applying headers
   └─ File: frontend/middleware.ts — applySecurityHeaders function
```

### S.4 CSP blocking legitimate resources

```
Symptom: Browser console shows "Refused to load" errors related to Content-Security-Policy
│
├─ Which resource is blocked?
│  ├─ Script from CDN → Add the CDN domain to script-src in nginx.conf CSP header
│  ├─ Font from external source → Add to font-src
│  ├─ Image from external source → Add domain to img-src
│  └─ API call to external service → Add to connect-src
│
├─ Next.js uses inline scripts for hydration
│  └─ 'unsafe-inline' is included in script-src for this reason
│  └─ In future: switch to nonce-based CSP for stricter protection
│
└─ After changing CSP: test all pages to verify nothing else breaks
```

### S.5 Swagger/OpenAPI docs not loading

```
Symptom: http://localhost:8000/api/docs returns 404
│
├─ Is ENVIRONMENT set to "production"?
│  └─ Docs are intentionally disabled in production
│  └─ For debugging: temporarily set ENVIRONMENT=development and restart
│
└─ For local development: ENVIRONMENT should be "development" or unset
```

---

## Quick Reference: Common Commands

| Task | Command |
|---|---|
| Start stack | `./scripts/start.sh` |
| Stop stack | `./scripts/stop.sh` |
| View logs (all) | `cd docker && docker compose logs -f` |
| View logs (one service) | `cd docker && docker compose logs -f backend` |
| Restart one service | `cd docker && docker compose restart backend` |
| Check container status | `cd docker && docker compose ps` |
| Run migrations | `cd backend && DATABASE_URL=... uv run alembic upgrade head` |
| Run seed | `cd backend && DATABASE_URL=... uv run python -m src.backend.seed` |
| Backend tests | `cd backend && uv run pytest tests/ -v` |
| Frontend tests | `cd frontend && npx vitest run` |
| TypeScript check | `cd frontend && npx tsc --noEmit` |
| Check health | `curl http://localhost/api/health` |
| Check Banner health | `curl http://localhost/api/banner/health` |
| Connect to DB | `docker exec -it docker-postgres-1 psql -U fnu -d fnu_portal` |
| Reset DB (destructive) | `cd docker && docker compose down -v && docker compose up -d` |
| Rebuild without cache | `cd docker && docker compose build --no-cache` |
| Check port usage | `lsof -i :<PORT>` |
| Unlock user account | `psql: UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE email='...';` |

---

## Quick Reference: Test Credentials

| Role | Email | Password |
|---|---|---|
| Student | `student@fnu.ac.fj` | `student123` |
| Student 2 | `student2@fnu.ac.fj` | `student123` |
| Admin | `admin@fnu.ac.fj` | `admin123` |
| Staff | `staff@fnu.ac.fj` | `staff123` |
| Finance | `finance@fnu.ac.fj` | `finance123` |
| Lecturer | `lecturer@fnu.ac.fj` | `lecturer123` |
| Manager | `manager@fnu.ac.fj` | `manager123` |
| VC | `vc@fnu.ac.fj` | `vc123456` |

---

## Quick Reference: Key Environment Variables

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | Backend | PostgreSQL connection string |
| `JWT_SECRET` | Backend | JWT signing secret (must be 32+ chars in production) |
| `JWT_EXPIRE_MINUTES` | Backend | Token lifetime (default: 60) |
| `ENVIRONMENT` | Backend | `development` or `production` (controls docs, secret validation) |
| `BANNER_MODE` | Backend | `mock` or `live` (mock blocked in production) |
| `BANNER_API_URL` | Backend | Banner REST API base URL (required when live) |
| `BANNER_API_KEY` | Backend | Banner API bearer token (required when live) |
| `BANNER_TIMEOUT_SECONDS` | Backend | Per-request timeout (default: 10) |
| `BANNER_CACHE_TTL_SECONDS` | Backend | Cache TTL for programmes/courses/fees (default: 900) |
| `OPENROUTER_API_KEY` | Backend | AI chatbot LLM access |
| `CORS_ORIGINS` | Backend | Allowed CORS origins |
| `INTERNAL_API_URL` | Frontend (runtime) | Backend URL for SSR fetches |
| `NEXTAUTH_SECRET` | Frontend | Session encryption secret |
| `NEXTAUTH_URL` | Frontend | Canonical app URL |
