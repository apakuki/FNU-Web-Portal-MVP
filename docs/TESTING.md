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
