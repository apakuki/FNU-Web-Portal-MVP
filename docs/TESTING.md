# Manual Test Plans

Step-by-step verification instructions for each part of the build plan. Run these after completing each part to confirm everything works before moving on.

---

## Part 2: Scaffolding

### Prerequisites

- Docker Desktop running
- Project cloned and `.env` file in project root

### Steps

**1. Start the stack**

```bash
./scripts/start.sh
```

Wait until all four containers show "Started" (postgres, backend, frontend, proxy).

**2. Verify the API health endpoint**

```bash
curl -s http://localhost/api/health | python3 -m json.tool
```

Expected:

```json
{
    "status": "ok",
    "postgres": "ok",
    "banner": "mock"
}
```

**3. Verify the home page**

Open http://localhost in a browser. You should see:

- "FNU Student Portal" heading in blue
- "Fiji National University Student Services" subtext
- A green panel showing API: ok, Postgres: ok, Banner: mock

**4. Verify the API docs**

Open http://localhost:8000/api/docs in a browser. You should see the Swagger UI with the `/api/health` endpoint listed.

**5. Verify direct service access**

```bash
# Backend directly
curl -s http://localhost:8000/api/health

# Frontend directly
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:3000/
```

Both should return 200.

**6. Run the automated tests**

```bash
# Backend
cd backend
uv run pytest tests/ -v

# Frontend
cd frontend
npx vitest run
```

All tests should pass.

**7. Stop the stack**

```bash
./scripts/stop.sh
```

Verify all containers are removed (no output from `docker ps`).

---

## Part 3: Database and Authentication

### Prerequisites

- Docker Desktop running
- Part 2 verified

### Steps

**1. Start the stack and apply the database**

```bash
./scripts/start.sh
```

Wait for all containers, then run the migration and seed:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal uv run python -m src.backend.seed
```

The seed should print "created" for 8 users. Running it again should print "exists" for all 8 (idempotent).

**2. Verify all tables exist**

```bash
docker exec docker-postgres-1 psql -U fnu -d fnu_portal -c "\dt"
```

You should see 14 tables: users, sessions, applications, application_documents, offers, payment_attempts, payment_plans, chatbot_conversations, chatbot_knowledge, enquiries, kpi_definitions, kpi_values, notifications, audit_log.

**3. Test login via API**

```bash
curl -s http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"student@fnu.ac.fj","password":"student123"}' | python3 -m json.tool
```

Expected: 200 response with `access_token`, `token_type: "bearer"`, and user object (Apisai Delana, role: student, banner_id: S00012345).

**4. Test /me with valid token**

```bash
TOKEN=$(curl -s http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"student@fnu.ac.fj","password":"student123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost/api/auth/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: 200 with the same user object.

**5. Test wrong password**

```bash
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"student@fnu.ac.fj","password":"wrong"}'
```

Expected: HTTP 401, `{"detail":"Invalid credentials"}`.

**6. Test unauthenticated access**

```bash
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/auth/me
```

Expected: HTTP 401 or 403.

**7. Test frontend auth redirect**

Open http://localhost/dashboard in a browser (not logged in). You should be redirected to `/login?callbackUrl=%2Fdashboard`.

**8. Test browser login flow**

- Go to http://localhost/login
- Enter `student@fnu.ac.fj` / `student123`
- Click "Sign In"
- You should land on the dashboard showing "Welcome, Apisai Delana. You are logged in as student."
- Six placeholder cards should be visible (My Account, My Timetable, etc.)
- Click "Sign Out" — you should return to the login page

**9. Test other roles**

Login with each account and verify the dashboard shows the correct name and role:

| Email | Password | Expected name | Expected role |
|---|---|---|---|
| `admin@fnu.ac.fj` | `admin123` | System Administrator | admin |
| `staff@fnu.ac.fj` | `staff123` | Registry Staff | staff |
| `finance@fnu.ac.fj` | `finance123` | Finance Officer | finance |
| `lecturer@fnu.ac.fj` | `lecturer123` | Dr. Mere Tuisawau | lecturer |
| `manager@fnu.ac.fj` | `manager123` | Dean of CBHTS | manager |
| `vc@fnu.ac.fj` | `vc123456` | Vice Chancellor | vc |
| `student2@fnu.ac.fj` | `student123` | Litia Nabalarua | student |

**10. Verify audit log**

After logging in at least once:

```bash
docker exec docker-postgres-1 psql -U fnu -d fnu_portal \
  -c "SELECT action, target_type, occurred_at FROM audit_log ORDER BY occurred_at DESC LIMIT 5;"
```

You should see `auth.login` entries.

**11. Test reset password endpoint**

```bash
curl -s http://localhost/api/auth/reset-password \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"anyone@fnu.ac.fj"}' | python3 -m json.tool
```

Expected: 200, `{"detail":"If that email exists, a reset link has been sent."}` (always succeeds, no email enumeration).

**12. API docs**

Open http://localhost:8000/api/docs — you should see auth endpoints listed alongside health.

**13. Run automated tests**

```bash
cd backend && uv run pytest tests/ -v
cd frontend && npx vitest run
```

All tests should pass (13 backend, 2 frontend).

**14. Stop the stack**

```bash
./scripts/stop.sh
```

---

## Part 4: Portal Shell, Login UI, and Public Landing

### Prerequisites

- Docker Desktop running
- Parts 2 and 3 verified (database migrated and seeded)

### Steps

**1. Start the stack**

```bash
./scripts/start.sh
```

Wait for all four containers to start, then ensure the database is migrated and seeded:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal uv run python -m src.backend.seed
```

**2. Verify the public landing page**

Open http://localhost in a browser. You should see:

- A white header with "Fiji National University", "Apply" link, and "Sign In" button
- A blue hero section with "Student Services Portal" heading, description text, "Apply Now" (gold button), and "Current Students" (outlined button)
- Six feature cards: Online Application, Course Registration, Fee Payments, Timetable and Grades, AI Assistant, Digital Student ID
- A "System Status" section showing health status (should say "ok" for API and Postgres)
- A dark footer with "Fiji National University Student Services Portal"

**3. Verify the login page**

Click "Sign In" or navigate to http://localhost/login. You should see:

- Centered card with "Sign In" heading in FNU blue
- Email and Password fields with labels
- "Sign In" button
- Fields are required (try submitting empty)

**4. Test login with invalid credentials**

Enter `student@fnu.ac.fj` / `wrongpassword` and click Sign In. You should see:

- Red error message: "Invalid email or password."
- Form remains on the login page

**5. Test successful login**

Enter `student@fnu.ac.fj` / `student123` and click Sign In. You should land on the dashboard showing:

- Top blue header with "FNU Portal", user name "Apisai Delana", role badge "student", and "Sign Out" button
- Left sidebar with 9 navigation links: Dashboard, Register, Timetable, My Courses, My Grades, Invoices, Make a Payment, Student ID, Profile
- "Dashboard" link highlighted (active state)
- Main area with "Dashboard" heading, welcome message, "Quick Actions" section with 6 clickable widget cards, and an "Announcements" section

**6. Test sidebar navigation**

- Click each sidebar link — the page should navigate and the active link should highlight
- On desktop (>1024px): sidebar is always visible
- On mobile (<1024px): sidebar is hidden; tap the hamburger icon (top-left) to slide it open with a dark overlay; tap the overlay or a link to close it

**7. Test mobile responsiveness**

Open browser DevTools, toggle device toolbar (Ctrl/Cmd+Shift+M), and set viewport to 375px wide:

- Landing page: hero text stacks vertically, feature cards become single column
- Login page: card fits within the viewport with padding
- Portal shell: sidebar is hidden, hamburger icon is visible, tap targets are at least 44×44px

**8. Test accessibility (keyboard navigation)**

- On the login page, Tab through fields and button — focus outlines should be visible
- On the portal shell, Tab through sidebar links — each link should receive focus with a visible ring
- Dashboard widget cards should be focusable (they are links)
- All navigation elements have `aria-label` or `aria-current` attributes

**9. Test the admin layout**

Login as `admin@fnu.ac.fj` / `admin123`, then navigate to http://localhost/admin. You should see:

- Dark header (not blue) with "FNU Admin"
- Sidebar with admin links: Admin Dashboard, Applications, Users, KPI Dashboard, Enquiries
- Main area with "Admin Dashboard" heading and 3 stat cards (Pending Applications, Active Students, Outstanding Fees — all showing "--")

**10. Test the lecturer layout**

Login as `lecturer@fnu.ac.fj` / `lecturer123`, then navigate to http://localhost/lecturer. You should see:

- Blue header with "FNU Lecturer"
- Sidebar with lecturer links: Lecturer Dashboard, My Courses, Enter Grades
- Main area with "Lecturer Dashboard" heading and 2 stat cards

**11. Test the outstanding fees banner**

The fees banner is wired to accept a `balanceCents` prop. In the current implementation it is passed `null`, so it should NOT be visible. This will be connected to real data in a later part.

**12. Test logout**

Click "Sign Out" in the header. You should be redirected to `/login`.

**13. Test route protection**

While logged out, try navigating directly to http://localhost/dashboard. You should be redirected to `/login?callbackUrl=%2Fdashboard`.

After logging in, you should be redirected back to `/dashboard` (the original callbackUrl).

**14. Run automated tests**

```bash
# Backend
cd backend && uv run pytest tests/ -v

# Frontend
cd frontend && npx vitest run
```

All tests should pass (13 backend, 9 frontend).

**15. Verify security headers**

```bash
curl -s -D - http://localhost -o /dev/null | grep -iE "(x-content|x-frame|referrer|strict-transport|permissions-policy|content-security)"
```

Expected headers present:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=()`
- `Content-Security-Policy: default-src 'self'; ...`

**16. Verify rate limiting on login**

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "Attempt $i: HTTP %{http_code}\n" \
    http://localhost/api/auth/login \
    -X POST -H "Content-Type: application/json" \
    -d '{"email":"test@fnu.ac.fj","password":"wrong"}'
done
```

Expected: first 10 attempts return 401, attempts 11+ return 429 (rate limited).

**17. Verify Swagger docs accessible in development**

Open http://localhost:8000/api/docs — Swagger UI should load. In production (ENVIRONMENT=production), this endpoint returns 404.

**18. Verify input validation**

```bash
# Email format validation
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"not-an-email","password":"test"}'
```

Expected: HTTP 422 (validation error, not 500).

**19. Stop the stack**

```bash
./scripts/stop.sh
```

---

## Security Verification Checklist (All Parts)

Run this checklist before any production deployment or after any security-related change.

### Infrastructure

- [ ] All containers running as non-root user (`docker exec <container> whoami` → not root)
- [ ] nginx `server_tokens off` (response does not reveal nginx version)
- [ ] All six security headers present on every response (see step 15 above)
- [ ] `.env` file is git-ignored and not present in Docker images
- [ ] No secrets in `NEXT_PUBLIC_*` environment variables
- [ ] Docker base images are current (no known CVEs)

### Authentication

- [ ] JWT_SECRET is not "change-me" (check .env)
- [ ] NEXTAUTH_SECRET is set and at least 32 characters
- [ ] Login returns 401 for wrong credentials (no information leakage)
- [ ] Account lockout activates after 5 failed attempts
- [ ] Lockout persists across container restarts (database-backed)
- [ ] Rate limiting active on login, reset-password endpoints
- [ ] Password reset does not enumerate valid emails
- [ ] Swagger/OpenAPI docs disabled when ENVIRONMENT=production

### Frontend

- [ ] Unauthenticated access to /dashboard redirects to /login
- [ ] Session cookie has httpOnly, Secure, SameSite flags
- [ ] No tokens stored in localStorage or sessionStorage
- [ ] Server Components used by default (no unnecessary client JS)

### Error Handling

- [ ] Backend never returns stack traces to clients (trigger a 500 and verify response is `{"detail": "Internal server error"}`)
- [ ] Frontend error boundaries catch rendering errors gracefully
