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

## Part 5: Banner Integration Layer

### Prerequisites

- Docker Desktop running
- Parts 2-4 verified (database migrated and seeded)

### Steps

**1. Start the stack**

```bash
./scripts/start.sh
```

Wait for all containers, then ensure the database is migrated and seeded.

**2. Verify Banner health endpoint (mock mode)**

```bash
curl -s http://localhost/api/banner/health | python3 -m json.tool
```

Expected:

```json
{
    "status": "ok",
    "latency_ms": 1.0
}
```

**3. Verify main health endpoint includes Banner status**

```bash
curl -s http://localhost/api/health | python3 -m json.tool
```

Expected: `status: "ok"`, `postgres: "ok"`, `banner: "ok"`.

**4. Verify Banner health in Swagger docs**

Open http://localhost:8000/api/docs — you should see the `/api/banner/health` endpoint listed under the "banner" tag.

**5. Run the Banner unit tests**

```bash
cd backend
uv run pytest tests/test_banner_mock.py tests/test_banner_cache.py tests/test_banner_factory.py -v
```

Expected: 34 tests pass, covering:
- 22 mock adapter tests (all read/write functions)
- 8 cache tests (TTL, invalidation, cached client behaviour)
- 4 factory tests (singleton, production validation, credential checks)

**6. Verify mock adapter data is realistic**

```bash
cd backend
uv run python -c "
import asyncio
from src.backend.banner.mock_adapter import MockBannerClient

async def check():
    c = MockBannerClient()
    progs = await c.get_programmes()
    print(f'Programmes: {len(progs)}')
    for p in progs:
        print(f'  {p.code}: {p.name} ({p.college})')
    
    courses = await c.get_courses('BCOM')
    print(f'BCOM courses: {len(courses)}')
    
    fees = await c.get_fee_schedule(2026, 'S1')
    print(f'Fee items: {len(fees.items)}')
    
    student = await c.get_student('S00012345')
    print(f'Student: {student.first_name} {student.last_name} ({student.banner_id})')
    
    invoices = await c.get_invoices('S00012345')
    print(f'Invoices: {len(invoices)}, balance: FJD {(invoices[0].total_cents - invoices[0].paid_cents)/100:.2f}')

asyncio.run(check())
"
```

Expected output showing 5 programmes, BCOM courses, fee items, student data, and invoice balances.

**7. Verify cache behaviour**

```bash
cd backend
uv run python -c "
import asyncio
from src.backend.banner.mock_adapter import MockBannerClient
from src.backend.banner.cached_client import CachedBannerClient

async def check():
    inner = MockBannerClient()
    cached = CachedBannerClient(inner, ttl_seconds=60)
    
    await cached.get_programmes()
    await cached.get_programmes()
    print(f'Cache size after 2 programme calls: {cached.cache.size} (should be 1)')
    
    await cached.get_courses('BCOM')
    await cached.get_courses('BSCI')
    print(f'Cache size after 2 different course calls: {cached.cache.size} (should be 3)')
    
    await cached.get_student('S00012345')
    print(f'Cache size after student call: {cached.cache.size} (should still be 3, students not cached)')

asyncio.run(check())
"
```

**8. Verify production safety — mock blocked in production**

```bash
cd backend
ENVIRONMENT=production BANNER_MODE=mock JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  uv run python -c "
from src.backend.banner.factory import get_banner_client, reset_banner_client
reset_banner_client()
try:
    get_banner_client()
    print('ERROR: Should have raised ValueError')
except ValueError as e:
    print(f'Correctly blocked: {e}')
"
```

Expected: `Correctly blocked: BANNER_MODE=mock is not allowed in production...`

**9. Verify live mode requires credentials**

```bash
cd backend
BANNER_MODE=live BANNER_API_URL= BANNER_API_KEY= \
  uv run python -c "
from src.backend.banner.factory import get_banner_client, reset_banner_client
reset_banner_client()
try:
    get_banner_client()
    print('ERROR: Should have raised ValueError')
except ValueError as e:
    print(f'Correctly blocked: {e}')
"
```

Expected: `Correctly blocked: BANNER_API_URL and BANNER_API_KEY must be set...`

**10. Run full backend test suite**

```bash
cd backend && uv run pytest tests/ -v
```

All tests should pass (47 backend).

**11. Stop the stack**

```bash
./scripts/stop.sh
```

---

## Part 6: New-Student Application Flow

### Prerequisites

- Docker Desktop running
- Parts 2-5 verified (database migrated and seeded)

### Steps

**1. Start the stack**

```bash
./scripts/start.sh
```

Wait for all containers, then ensure the database is migrated and seeded:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal uv run python -m src.backend.seed
```

**2. Verify the public application page loads**

Open http://localhost/apply in a browser. You should see:

- A multi-step form starting with "Contact Information"
- Step indicators at the top: Contact, Personal, Qualifications, Programme, Review
- "Contact" step highlighted as active
- An email field and a Next button

**3. Test form validation — empty email**

Click "Next" without entering an email. You should see:

- Red error message: "Email is required"
- Form stays on the Contact step

**4. Test step progression — Contact to Personal**

Enter a valid email (e.g. `jane@email.com`) and click "Next". You should see:

- Step 2: "Personal Details" with fields for First Name, Last Name, Date of Birth, Gender, Nationality, Address
- "Contact" step indicator marked as completed
- "Back" button now visible

**5. Test back navigation**

Click "Back". You should return to the Contact step with the email preserved.

**6. Test Personal Details validation**

Navigate to Personal Details (step 2), leave fields empty, and click "Next". You should see:

- Validation errors for required fields (e.g. "First name is required")

**7. Complete Personal Details**

Fill in: First Name "Jane", Last Name "Doe", DOB "2000-01-15", Gender "Female", Nationality "Fijian", Address "123 Main St, Suva". Click "Next".

You should advance to step 3: "Qualifications".

**8. Test Qualifications step**

- Default: one qualification entry with fields for Institution, Qualification, Year Completed, Grade
- Click "Add Qualification" — a second entry should appear
- Click "Remove" on the second entry — it should disappear
- Fill in: Institution "Suva Grammar School", Qualification "Year 13", Year "2023", Grade "A"
- Click "Next" to advance to Programme Selection

**9. Test Programme Selection**

- Select a programme (e.g. "BCOM") and campus (e.g. "Nasinu")
- Click "Next" to advance to Review

**10. Test Review step**

The review summary should show all entered data:

- Email, phone
- Personal details (name, DOB, gender, nationality, address)
- Qualifications list
- Programme and campus selection
- A "Submit Application" button

**11. Test application submission via API**

```bash
curl -s http://localhost/api/applications \
  -X POST -H "Content-Type: application/json" \
  -d '{
    "applicant_email": "jane@email.com",
    "applicant_phone": "+6799991234",
    "personal_details": {
      "first_name": "Jane",
      "last_name": "Doe",
      "date_of_birth": "2000-01-15",
      "gender": "female",
      "nationality": "Fijian",
      "address": "123 Main St, Suva"
    },
    "prior_qualifications": [{
      "institution": "Suva Grammar School",
      "qualification": "Year 13",
      "year_completed": 2023,
      "grade": "A"
    }],
    "programme_preference": "BCOM",
    "campus_preference": "Nasinu"
  }' | python3 -m json.tool
```

Expected: 200 response with `application_number` (format: APP-2026-NNNNNN), `id`, `status: "submitted"`.

**12. Test input validation via API**

```bash
# Missing email — should return 422
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/applications \
  -X POST -H "Content-Type: application/json" \
  -d '{"personal_details":{"first_name":"Jane","last_name":"Doe","date_of_birth":"2000-01-15","gender":"female","nationality":"Fijian","address":"123 Main St"},"prior_qualifications":[{"institution":"School","qualification":"Y13","year_completed":2023,"grade":"A"}],"programme_preference":"BCOM","campus_preference":"Nasinu"}'

# Invalid email — should return 422
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/applications \
  -X POST -H "Content-Type: application/json" \
  -d '{"applicant_email":"not-an-email","personal_details":{"first_name":"Jane","last_name":"Doe","date_of_birth":"2000-01-15","gender":"female","nationality":"Fijian","address":"123 Main St"},"prior_qualifications":[{"institution":"School","qualification":"Y13","year_completed":2023,"grade":"A"}],"programme_preference":"BCOM","campus_preference":"Nasinu"}'

# Empty qualifications — should return 422
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/applications \
  -X POST -H "Content-Type: application/json" \
  -d '{"applicant_email":"jane@email.com","personal_details":{"first_name":"Jane","last_name":"Doe","date_of_birth":"2000-01-15","gender":"female","nationality":"Fijian","address":"123 Main St"},"prior_qualifications":[],"programme_preference":"BCOM","campus_preference":"Nasinu"}'
```

**13. Test document upload security**

```bash
# Valid PDF upload — should return 200
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/applications/documents \
  -F "file=@/dev/stdin;filename=test.pdf;type=application/pdf" \
  -F "document_type=transcript" <<< "%PDF-1.4 test content"

# Wrong MIME type — should return 400
curl -s http://localhost/api/applications/documents \
  -F "file=@/dev/stdin;filename=test.exe;type=application/x-msdownload" \
  -F "document_type=transcript" <<< "MZ executable"

# Magic byte mismatch (claims PDF but isn't) — should return 400
curl -s http://localhost/api/applications/documents \
  -F "file=@/dev/stdin;filename=fake.pdf;type=application/pdf" \
  -F "document_type=transcript" <<< "NOT_A_PDF"
```

**14. Test admin application queue**

Login as `staff@fnu.ac.fj` / `staff123`, then navigate to http://localhost/admin/applications. You should see:

- "Applications" heading with total count
- Status filter dropdown (All, Submitted, Under Review, etc.)
- Table with columns: App #, Email, Programme, Campus, Status, Submitted, Review link
- Pagination controls if more than 20 applications

**15. Test admin application detail**

Click "Review" on any application. You should see:

- Application number and submission date
- Status badge (colour-coded)
- Four sections: Applicant details, Programme info, Documents list, Actions panel
- Action dropdown with options: Mark Under Review, Request Documents, Approve, Approve (Conditional), Reject
- Selecting an action reveals a reason textarea and Confirm button
- "Reject" and "Request Documents" show "Reason (required)" placeholder

**16. Test status update via API**

```bash
TOKEN=$(curl -s http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"staff@fnu.ac.fj","password":"staff123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get application list
curl -s http://localhost/api/admin/applications \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Update status (replace <ID> with actual application ID)
curl -s http://localhost/api/admin/applications/<ID>/status \
  -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"under_review"}' | python3 -m json.tool
```

**17. Test offer flow**

After approving an application, an offer token is generated. Test the offer page:

- Check the offers table for the token:
  ```bash
  docker exec docker-postgres-1 psql -U fnu -d fnu_portal \
    -c "SELECT token, expires_at, accepted_at FROM offers ORDER BY created_at DESC LIMIT 1;"
  ```
- Navigate to http://localhost/offer/<TOKEN> — you should see the offer details with Accept and Decline buttons
- Click "Accept" — the page should update to show "Offer Accepted" confirmation
- Revisiting the same URL should show "Already responded"

**18. Test rate limiting on application submission**

```bash
for i in $(seq 1 7); do
  curl -s -o /dev/null -w "Attempt $i: HTTP %{http_code}\n" \
    http://localhost/api/applications \
    -X POST -H "Content-Type: application/json" \
    -d '{"applicant_email":"test'$i'@email.com","personal_details":{"first_name":"Test","last_name":"User","date_of_birth":"2000-01-15","gender":"male","nationality":"Fijian","address":"Suva"},"prior_qualifications":[{"institution":"School","qualification":"Y13","year_completed":2023,"grade":"A"}],"programme_preference":"BCOM","campus_preference":"Nasinu"}'
done
```

Expected: first 5 succeed (200 or 500 if DB not available), attempt 6+ returns 429.

**19. Run automated tests**

```bash
# Backend (76 tests)
cd backend && uv run pytest tests/ -v

# Frontend (15 tests)
cd frontend && npx vitest run
```

All tests should pass.

**20. Stop the stack**

```bash
./scripts/stop.sh
```

---

## Part 7: Course Registration, Timetable, Invoicing

### Prerequisites

- Docker Desktop running
- Parts 2–6 verified (database migrated and seeded)

### Steps

**1. Start the stack**

```bash
./scripts/start.sh
```

Wait for all containers, then ensure the database is migrated and seeded.

**2. Verify the programme endpoint**

```bash
TOKEN=$(curl -s http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"student@fnu.ac.fj","password":"student123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost/api/programme \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: programme structure for BCOM with `code`, `name`, `level`, `college`, `total_credits`, `completed_credits`, and a `courses` array of offerings with `prereqs_met`, `prereq_issues`, `available`, etc.

**3. Verify the courses endpoint**

```bash
curl -s "http://localhost/api/courses?semester=S1&year=2026" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: array of courses with offerings, `prereqs_met` and `prereq_issues` per course.

**4. Test the Course Registration page**

Login as `student@fnu.ac.fj` / `student123`, navigate to http://localhost/register. You should see:

- Page heading "Course Registration" with BCOM credits progress
- Table of available offerings with columns: Select, Course, Day / Time, Room, Lecturer, Seats, Status
- Available courses show green "Available" badge; blocked courses show "Prereqs not met" detail
- For Apisai (BCOM, S00012345): ACC101 and MGT101 should be blocked ("already completed"); ACC201 should be available with prereqs_met

**5. Test prereq blocking UI**

Courses where prerequisites are not met should have the checkbox disabled and display the specific reason (e.g. "ACC101 not completed").

**6. Test clash detection (client-side)**

Select two offerings that clash (ACC101 Mon 09-11 and ACC201 Mon 10-12). A red warning banner should appear listing the clash before you even click Confirm.

**7. Test registration confirmation**

Select 2 non-clashing courses (e.g. ACC201 Mon and MGT101 Tue). Click "Confirm Registration". Expected:

- Success screen with green "Registration Confirmed" banner
- Lists the registered course codes
- Shows invoice ID and total fee (e.g. FJ$1,890.00 for 2 courses at partial load pricing)

**8. Test double-registration prevention (API)**

```bash
# Try registering the same offering twice
curl -s http://localhost/api/registration/confirm \
  -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"offering_ids":["acc201-offering-uuid"],"semester":"S1","year":2026}' \
  | python3 -m json.tool
```

A second identical request should return 400 or be idempotent depending on Banner mock behaviour.

**9. Test server-side clash rejection (API)**

```bash
curl -s http://localhost/api/registration/confirm \
  -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"offering_ids":["<acc101-id>","<acc201-id>"],"semester":"S1","year":2026}' \
  | python3 -m json.tool
```

Expected: success=false with `clashes` array containing details of the overlap.

**10. Verify the Timetable page**

Navigate to http://localhost/timetable. You should see:

- Heading "My Timetable — Semester 1, 2026"
- Registered courses grouped by day (Monday, Tuesday, etc.)
- Each entry shows time, course code, room, campus, lecturer
- "Export to Calendar (.ics)" button visible in top-right

**11. Test .ics export**

Click "Export to Calendar (.ics)". A `timetable.ics` file should download. Open it in a text editor and verify:

- `BEGIN:VCALENDAR` header present
- `RRULE:FREQ=WEEKLY;COUNT=14` for each course
- `TZID=Pacific/Fiji` in the DTSTART line
- One `VEVENT` block per registered course

Try importing the file into Google Calendar or macOS Calendar — events should appear on the correct days for 14 weeks.

**12. Verify the My Courses page**

Navigate to http://localhost/courses. You should see:

- Heading "My Courses — Semester 1, 2026"
- Cards for each registered course showing code, name, credits, schedule, room, lecturer
- Credit summary in the subtitle

**13. Verify the Grades page**

Navigate to http://localhost/grades. You should see:

- Heading "My Grades"
- GPA summary cards at the top: Cumulative GPA (should be 3.45 for Apisai based on seed data), per-semester GPA
- Transcript table grouped by semester showing course code, name, credits, grade letter, and GPA points
- Colour-coded grades (A/A-/A+ in green, B grades in blue, C grades in amber, F in red)

**14. Verify the Invoices page**

Navigate to http://localhost/invoices. You should see:

- Heading "My Invoices"
- Invoice card for INV-2026-S1-00001 (Apisai's partially paid invoice: FJ$3,780 total, FJ$1,890 paid)
- Itemised fee breakdown in the card
- Status badge: "Partially Paid"
- "Download PDF" link
- "Pay Now" button (since balance > 0)
- Outstanding balance summary in top-right

**15. Test invoice PDF download**

Click "Download PDF" on any invoice. A PDF file should download. Open it and verify:

- FNU header and "Tax Invoice" subtitle
- Invoice ID, semester, due date
- Itemised fee table with amounts
- Total, Paid, and Balance Due rows

If WeasyPrint is unavailable, the endpoint returns 500 — that is acceptable for local dev without system libraries; note WeasyPrint requires `libpango`, `libcairo`, and `libgdk-pixbuf` in the Docker image.

**16. Test unauthenticated access to student endpoints**

```bash
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/timetable
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/grades
curl -s -w "\nHTTP %{http_code}\n" http://localhost/api/invoices
```

All three should return HTTP 401 or 403.

**17. Test IDOR prevention — student 2 cannot see student 1 invoices**

```bash
TOKEN2=$(curl -s http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"student2@fnu.ac.fj","password":"student123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Try to retrieve student 1's invoice using student 2's token
curl -s -w "\nHTTP %{http_code}\n" \
  "http://localhost/api/invoices/INV-2026-S1-00001" \
  -H "Authorization: Bearer $TOKEN2"
```

Expected: HTTP 404 (invoice not found for student 2's banner_id — not 200 or 403 revealing ownership).

**18. Test registration rate limiting**

```bash
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "Attempt $i: HTTP %{http_code}\n" \
    http://localhost/api/registration/confirm \
    -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"offering_ids":["fake-id"],"semester":"S1","year":2026}'
done
```

Expected: attempts 1–3 return 400 (invalid offering), attempt 4 returns 429 (rate limited).

**19. Verify second student (Litia — BNUR)**

```bash
TOKEN2=$(curl -s http://localhost/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"email":"student2@fnu.ac.fj","password":"student123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost/api/programme \
  -H "Authorization: Bearer $TOKEN2" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['code'], d['name'])"

curl -s http://localhost/api/grades \
  -H "Authorization: Bearer $TOKEN2" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(f'GPA: {d[\"cumulative_gpa\"]}, courses: {len(d[\"grades\"])}')"
```

Expected: programme BNUR (Bachelor of Nursing), GPA based on NUR101 (A) and BIO101 (B+) seed data.

**20. Run automated tests**

```bash
# Backend (100 tests)
cd backend && uv run pytest tests/ -v

# Frontend
cd frontend && npx vitest run
```

All tests should pass.

**21. Stop the stack**

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

---

## Part 8: Payment Gateway Integration

### Setup

- [ ] Backend running with `PAYMENTS_MODE=stub` and `BANNER_MODE=mock`
- [ ] Logged in as student with an unpaid invoice (see Part 7 fixtures)
- [ ] A second login as a user with `finance` or `admin` role available in another browser

### Student Pay page (`/pay`)

- [ ] Navigate to **Make a Payment** from the portal sidebar
- [ ] Outstanding balance card shows the sum of all unpaid invoices
- [ ] Invoice dropdown lists only invoices with `balance_cents > 0`
- [ ] Method radios show M-PAiSA, MyCash, Bank Transfer; M-PAiSA selected by default
- [ ] "Full balance" option shows the outstanding amount inline
- [ ] Selecting "Partial" reveals an FJD amount input; entering `0` or blank keeps the submit button disabled by validation
- [ ] Submitting a partial amount greater than the invoice balance shows the error "Amount exceeds outstanding balance"
- [ ] Rate limit: submitting 11 times within 1 minute produces a 429 Too Many Requests on the 11th
- [ ] Submitting M-PAiSA in stub mode redirects the browser to `/api/payments/callback/mpaisa?ref=…&pid=…&stub=1`
- [ ] Submitting Bank Transfer renders deposit instructions (bank name, account name, account number, reference starting with `FNU-<banner_id>-`)
- [ ] Recent Payments table lists the latest attempt with status `initiated`

### Stub callback (idempotency)

- [ ] POST a signed callback to `/api/payments/callback/mpaisa` with `status=confirmed`; response returns "Callback processed"
- [ ] Replay the identical callback; response returns "Already processed" (idempotent)
- [ ] Tamper with `amount_cents` and replay; response is 400 Invalid signature
- [ ] Remove the `payment_id` field and replay; response is 400 with "Missing callback fields"
- [ ] Student /pay page now shows the payment with status `confirmed` and balance updates on the account card

### Bank transfer confirmation

- [ ] As student, initiate a bank transfer payment; note the `payment_id` and `deposit_reference`
- [ ] Switch to the finance login and open **Admin → Finance**
- [ ] In "Confirm Bank Transfer", enter the payment ID, bank reference, and amount; submit
- [ ] Response shows "Confirmed (payment <uuid>)" and the entries table updates
- [ ] A student role trying to POST `/api/payments/bank-confirm` directly is rejected 403

### Finance reconciliation (`/admin/finance`)

- [ ] Default report shows last 30 days; date filters apply on "Apply"
- [ ] Method filter narrows entries correctly
- [ ] Top cards show Total Confirmed and a per-method breakdown (M-PAiSA, MyCash, Bank Transfer)
- [ ] Only `confirmed` payments contribute to the totals; `initiated`/`pending`/`failed` do not
- [ ] "Export CSV" downloads a file with columns `payment_id,student_banner_id,invoice_id,method,amount_cents,status,gateway_reference,created_at`
- [ ] Opening the CSV in a spreadsheet shows the same rows as the on-screen table

### Payment plan

- [ ] POST `/api/account/plan` with `{"invoice_id": "<inv>", "num_instalments": 3, "first_due_date": "2026-05-01"}`
- [ ] Response returns `schedule.instalments` with 3 entries summing to the invoice balance
- [ ] Student /pay page shows the schedule table under "Payment Plan"
- [ ] Instalments past today appear as `overdue`; future instalments as `upcoming`

### Security

- [ ] Callback with missing `X-MPaisa-Signature` header and no `signature` field in body is rejected 400
- [ ] Callback with incorrect signature returns 400 Invalid signature (not a generic 500)
- [ ] Production config refuses `PAYMENTS_MODE=stub` at startup (pydantic ValidationError)
- [ ] Production config with `PAYMENTS_MODE=live` but missing `MPAISA_SECRET` raises a clear error

---

## Part 9: AI Chatbot Backend

### Prerequisites

- Part 3 verified (auth working, seed data loaded)
- `.env` has `OPENROUTER_API_KEY` set, and `CHATBOT_MODE=live` if you want real LLM replies; otherwise `CHATBOT_MODE=stub` uses a deterministic canned reply

### Public chat endpoint (`POST /api/chat`)

**1. Unauthenticated request (no bearer token)**

```bash
curl -s -X POST http://localhost/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"When does semester 2 start?"}' | python3 -m json.tool
```

Expected:
- 200 OK with `session_key`, `reply`, `escalated` (boolean), `sources` (array of FAQ titles)
- `session_key` is a new URL-safe token you can reuse on follow-ups

**2. Continuing a conversation (reuse `session_key`)**

Repeat the request with the `session_key` from step 1. The backend loads prior turns and answers in context. Verify in the admin conversations log (Part 10) that both turns are persisted under the same row.

**3. Authenticated student request**

Log in as `student@fnu.ac.fj`, copy the Bearer token, then:

```bash
curl -s -X POST http://localhost/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"What is my balance?"}'
```

- The student's programme, balance, and registered courses are included in the LLM prompt (see `services/chatbot_service.py::compose_messages`)
- Reply references the student's invoice balance when relevant
- If Banner is unreachable, the chat still completes (context gracefully missing)

**4. Escalation detection**

Send: `"I want to speak to a human"` — response has `escalated: true`, `escalation_reason` populated, and a row is written to `enquiries` with `source="chatbot"`.

**5. PII masking**

Send a message containing an email address and phone number; verify the admin conversation log shows the content with the email replaced by `[email]` and the phone by `[phone]` (see `mask_pii` helper).

**6. Rate limit**

Fire 31 requests in 60 seconds from the same IP — the 31st returns 429 (`30/minute` limit on `/api/chat`).

### Admin knowledge CRUD

Log in as admin and confirm from curl or Swagger:

- [ ] `GET /api/admin/chatbot/knowledge` returns the 10 seeded FAQ entries
- [ ] `POST /api/admin/chatbot/knowledge` creates a new entry and audit log row
- [ ] `POST` body containing `<script>` in title or content is rejected 400
- [ ] `PUT /api/admin/chatbot/knowledge/{id}` updates an entry; audit log has before/after
- [ ] `DELETE /api/admin/chatbot/knowledge/{id}` flips `is_active=false` (soft delete) and writes an audit log
- [ ] A staff user can read but not write (POST/PUT/DELETE return 403)

### Automated tests

```bash
cd backend && uv run pytest tests/test_chatbot_api.py tests/test_chatbot_service.py -v
```

All tests pass.

---

## Part 10: Chatbot UI (Widget, Admin, Embed)

### Prerequisites

- Part 9 verified (backend endpoints working)
- Stack running (`./scripts/start.sh`)

### Floating widget (student portal)

**1. Widget appears in the portal**

- Log in as `student@fnu.ac.fj`; navigate to any authenticated page (`/dashboard`, `/timetable`, etc.)
- A round blue launcher button is pinned to the bottom-right corner
- Click it: a 360x480 panel opens with the greeting "Hi! I'm the FNU chatbot..."

**2. Happy path**

- Type "When does semester 2 start?" and press Send
- "Typing…" bubble appears while the request is in flight
- Within a second or two the assistant reply appears; sources (FAQ titles) appear beneath
- `sessionStorage.getItem("fnu_chatbot_session")` is populated (DevTools → Application → Session Storage)

**3. Multi-turn continuity**

- Ask a follow-up without reloading the page
- Admin → Chatbot Log shows one conversation row with 4 messages (2 user + 2 assistant)

**4. Escalation path**

- Ask "I need to speak to a human"
- Reply appears plus a yellow banner: "This enquiry has been flagged for staff…"
- Admin → Chatbot Log → row is marked `escalated`; Admin → Enquiries has a new `chatbot` enquiry

**5. Error handling**

- Stop the backend container (`docker stop fnu-backend`) and send a message
- The UI shows a small red error line beneath the messages, and the input re-enables so the user can retry
- Restart the backend; retry works

**6. Mobile (375px)**

- Shrink the browser to 375px wide; the panel resizes to `calc(100vw - 2rem)` and remains usable
- Launcher button does not overlap primary portal content

**7. Auth header**

- DevTools → Network → `POST /api/chat`; confirm the `Authorization: Bearer …` header is present for logged-in students
- The saved conversation (Admin → Chatbot Log) has `user_id` populated — not anon

### Admin — Chatbot FAQ (`/admin/chatbot/knowledge`)

- [ ] Log in as `admin@fnu.ac.fj`; sidebar has "Chatbot FAQ", "Chatbot Log", "Chatbot Analytics"
- [ ] List shows all 10 seeded FAQ entries
- [ ] "Add Entry" form — create a new entry with tags "admissions, fees"; it appears at the top of the list on refresh
- [ ] "Edit" loads the entry into the form; save updates it in place
- [ ] "Deactivate" prompts for confirmation, soft-deletes; "Show inactive" toggle reveals it with a `inactive` tag
- [ ] Creating an entry whose content contains `<script>` shows a red inline error (400 from backend)
- [ ] Logged in as `staff@fnu.ac.fj`, the "Add Entry" form returns 403 on submit (staff can read, not write)

### Admin — Chatbot Log (`/admin/chatbot/conversations`)

- [ ] List shows the most recent conversations (updated_at desc), 25 per page
- [ ] "Escalated only" filter narrows to escalated rows
- [ ] Search box accepts session key fragments or category names
- [ ] Clicking a row opens a modal with the full message history; PII in messages is masked
- [ ] Prev/Next paginate through older conversations

### Admin — Chatbot Analytics (`/admin/chatbot/analytics`)

- [ ] Four KPI cards: Total, Escalated (with %), Resolved (with %), Active FAQ entries
- [ ] 7/30/90 day buttons reload the analytics for that window
- [ ] Top escalation categories table shows grouped counts (empty state if none)

### Embeddable widget

**1. Standalone embed page**

Open http://localhost/embed/chatbot directly. The entire viewport is the chat UI (no portal shell, no session header). Launcher/close button is hidden. You can ask a question as an anonymous visitor.

**2. Iframe bootstrapper**

Open `/Users/apakuki/Documents/Consulting/FNU Web Portal MVP/docs/embed-test.html` (or any static HTML file) containing only:

```html
<!doctype html>
<html><body>
  <h1>Test host</h1>
  <script src="http://localhost/embed/chatbot.js"></script>
</body></html>
```

- A round blue launcher appears bottom-right
- Clicking it toggles an iframe pointing to `/embed/chatbot`
- The chat works end-to-end against the live backend

**3. Security headers**

```bash
curl -sI http://localhost/embed/chatbot | grep -iE "x-frame|content-security"
```

- `X-Frame-Options` is **absent** (removed specifically for /embed)
- `Content-Security-Policy: frame-ancestors *` is present (or the configured `NEXT_PUBLIC_EMBED_ALLOWED_ORIGINS` list)

On any non-embed page (e.g. `/dashboard`) confirm `X-Frame-Options: DENY` is still set.

### Automated tests

```bash
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
cd frontend && npx next build
```

All frontend tests pass; TypeScript is clean; build completes including `/embed/chatbot` and the three `/admin/chatbot/*` pages.

---

## Part 11: Profile, Student ID, Notifications

### Setup

- [ ] Backend running with `NOTIFICATIONS_MODE=stub` (email/SMS logged, not sent) and `BANNER_MODE=mock`
- [ ] `ID_CARD_SECRET` set to any dev value (default `id-card-change-me` is fine outside production)
- [ ] DB migration `c3d4e5f6a7b8_part11_profile_photos_templates` applied (`alembic upgrade head`)
- [ ] `python -m src.backend.seed` has been run so `notification_templates` contains 11 seeded templates
- [ ] Logged in as a student (e.g. `student@fnu.ac.fj`) in one browser; logged in as an admin in a second browser

### Profile view (`/profile`)

- [ ] Navigate to **Profile** from the portal sidebar; page loads with name, email, Banner ID pre-filled
- [ ] Empty emergency contact and address fields render as editable inputs (no crash)
- [ ] Edit phone to `+679 999 1234`, address to `1 Samabula Rd`, city to `Suva`; press Save; success toast appears
- [ ] Reload the page; changes persist
- [ ] Enter phone `not-a-phone!!!`; Save; a 400-style error surfaces without the page crashing
- [ ] Change email to an address belonging to another seeded user; expect "Email already in use"

### Profile photo upload

- [ ] From the Profile page, upload a 300x300 JPEG; the preview thumbnail updates within a few seconds
- [ ] Upload a `.txt` file renamed to `.jpg`; expect a 400 error "Only JPEG/PNG/WebP images are accepted"
- [ ] Upload an image > 2 MB; expect a 413 "Photo exceeds maximum size" error
- [ ] `curl -H "Authorization: Bearer <token>" http://localhost/api/profile/photo/me -o /tmp/me.jpg` returns a 400x400 JPEG
- [ ] Run `python -c "from PIL import Image; print(Image.open('/tmp/me.jpg').info)"` — output contains no `exif` key

### Digital Student ID (`/id-card`)

- [ ] Navigate to **Student ID** from the portal sidebar
- [ ] Card renders with photo (if uploaded), full name, Banner ID, expiry date, and a QR code
- [ ] Scan the QR with a phone → it opens `<host>/verify/<payload>`
- [ ] The verify page shows the student photo, name, Banner ID, programme, and "Valid until" date
- [ ] Confirm the verify page does NOT show email, phone, grades, or balance
- [ ] Tamper the URL (change one character in `<payload>`) → page renders "Invalid or tampered QR code"

### Notification service (stub mode)

- [ ] With `NOTIFICATIONS_MODE=stub`, tail the backend logs
- [ ] Trigger a payment confirmation (complete a stub M-PAiSA callback as in Part 8)
- [ ] Backend logs show `[email/stub] to=…@… subject=Payment Confirmed`
- [ ] `SELECT status, template_code, recipient_email FROM notifications ORDER BY queued_at DESC LIMIT 5;` shows the most recent row with `status='sent'`

### Admin communications (`/admin/communications`)

- [ ] As admin, navigate to **Communications**
- [ ] Template list shows the 11 seeded templates (payment.*, application.*, offer.issued, deadline.reminder, sms.*)
- [ ] Pick `payment.reminder`, set `Role = student`, set `variables = {"full_name":"Preview","invoice_id":"INV-TEST","amount_fjd":"100.00","due_date":"2026-05-01","portal_url":"https://portal.fnu.ac.fj"}`, click **Preview** → recipient count and content hash returned, zero actually sent
- [ ] Click **Send**; "Sent X of Y" message appears; the Recent notifications list shows rows with `status='sent'`
- [ ] `SELECT action, after FROM audit_log WHERE action LIKE 'communications.batch.%' ORDER BY created_at DESC LIMIT 2;` shows both a `preview` and a `send` entry with matching `content_hash`
- [ ] As a **student** (non-admin), `curl -H "Authorization: Bearer <student_token>" -X POST http://localhost/api/admin/communications/batch -d '{...}' -H 'Content-Type: application/json'` returns 403

### Template injection safety

- [ ] `curl -X POST .../api/admin/communications/batch -d '{"template_code":"payment.reminder","role":"student","variables":{"full_name":"Eve\r\nBcc: attacker@evil.com"},"dry_run":true}'` succeeds
- [ ] The rendered body contains no `Bcc:` header injection — CR/LF characters are stripped from interpolated values

### QR signature / expiry

```bash
# Forge a payload with a bad signature
curl -s http://localhost/api/verify/AAA.BBB | jq
# -> {"valid":false,"reason":"Invalid or tampered QR code"}

# Expired card — temporarily set ID_CARD_VALIDITY_DAYS=0 in backend env
curl -s http://localhost/api/id-card -H "Authorization: Bearer <student_token>" | jq -r .qr_payload | xargs -I{} curl -s http://localhost/api/verify/{} | jq
# -> {"valid":false,"reason":"ID card has expired"}
```

### Automated tests

```bash
cd backend && .venv/bin/python -m pytest tests/test_id_card_service.py tests/test_notification_service.py tests/test_profile_api.py tests/test_profile_photo.py -v
cd backend && .venv/bin/python -m pytest tests/ -q
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
```

Part 11 adds 25 backend tests (6 ID card signer, 6 notification service, 7 profile API, 6 photo processor). Full backend suite now passes 188 tests; frontend remains at 22.

---

## Part 12: Staff Administration Panel

### Setup

- [ ] Stack running (`./scripts/start.sh`) with `BANNER_MODE=mock`
- [ ] DB migrated through `c3d4e5f6a7b8` and `python -m src.backend.seed` has run (seeds 8 users including `student@fnu.ac.fj`, `staff@fnu.ac.fj`, `admin@fnu.ac.fj`)
- [ ] Logged in as `admin@fnu.ac.fj` / `admin123` in one browser and as `student@fnu.ac.fj` / `student123` in another

### Admin dashboard cards

- [ ] Navigate to `/admin`; five cards render without error (Pending applications, Open enquiries, Active students, Avg. application decision, Avg. enquiry resolution)
- [ ] The three linked cards (pending applications, open enquiries, active students) are keyboard-navigable and the focus ring is visible
- [ ] Submit a new application via the public `/apply` flow and reload `/admin`; the "Pending applications" card increments by 1

### Student search + detail

- [ ] Navigate to **Students** in the admin sidebar
- [ ] Type `apisai` into the search box; the row for `S00012345 · student@fnu.ac.fj` appears
- [ ] Filter by Programme = `BNUR`; only the BNUR student remains
- [ ] Click **View** on the Apisai row; the detail page shows programme BCOM, campus Nasinu, completed courses ACC101/MGT101/ECN101, current registrations (if any), invoice `INV-2026-S1-00001`
- [ ] Empty-state: create a brand-new user with role=student and no Banner ID; detail view renders with "No Banner ID" header and empty programme/completed-courses sections

### Manual overrides

- [ ] On the Apisai detail page scroll to "Apply manual override"
- [ ] Select **Prerequisite Waiver**, subject `ACC201`, reason `Student completed equivalent course at USP` (≥10 chars); click **Apply override** → success and new row appears under "Overrides applied"
- [ ] Attempt with reason `too short` → frontend shows "Reason must be at least 10 characters"; no request is sent
- [ ] `SELECT actor_user_id, action, target_id, reason FROM audit_log WHERE action LIKE 'override.%' ORDER BY occurred_at DESC LIMIT 3;` shows the override with the admin's user_id as actor
- [ ] Check the `notifications` table — a row with `subject='Manual override applied — prereq waiver'` to the student's email exists
- [ ] As the **student**, `curl -H "Authorization: Bearer <student_token>" -X POST http://localhost/api/admin/students/<admin_id>/overrides -d '{"override_type":"prereq_waiver","reason":"Trying to escalate"}' -H 'Content-Type: application/json'` returns 403

### Enquiries: chatbot-escalated row

- [ ] As the student, open the chatbot widget and send "I want to speak to a human about my balance" (this triggers escalation in Part 9)
- [ ] As the admin, navigate to **Enquiries**; a new open enquiry appears at the top of the queue with source `chatbot`
- [ ] Click **Open**; confirm subject/body captured from the conversation
- [ ] Click **Assign to me**; page refreshes showing "Assigned to System Administrator"
- [ ] Change Status to `in_progress`, click **Save changes** → status updates

### Enquiries: resolution workflow

- [ ] With the enquiry still open, try to save with Status=`resolved` and the note field blank → API returns 400 "Resolution note is required before marking resolved"
- [ ] Type a note `Explained balance via phone call`, select Status=`resolved`, click **Save changes** → success; the note is now rendered read-only with the caption "Once saved, the resolution note cannot be edited"
- [ ] Try PUT with a different `resolution_note` via curl → 400 "Resolution note cannot be edited once written"
- [ ] A Student feedback card now appears; pick `5` and click **Record feedback** → rating displays
- [ ] Attempt to POST feedback again via curl → 400 "Feedback has already been recorded"

### Enquiries: staff-logged entry

- [ ] Click **Log enquiry** on the queue; leave subject blank and click Save → "Subject and body are required"
- [ ] Fill subject=`Transcript request`, body=`Student called for an official transcript`, source=`phone`, student identifier=`S00012346`; save → the enquiry appears in the queue with source `phone`
- [ ] `SELECT action, target_id FROM audit_log WHERE action='enquiry.create' ORDER BY occurred_at DESC LIMIT 1;` returns the new enquiry

### Processing-time metrics

- [ ] Approve the application created in the first section via `/admin/applications/<id>` and reload `/admin`
- [ ] The "Avg. application decision" card now displays a non-empty value (minutes or hours)
- [ ] Resolve the enquiry above and reload `/admin`; the "Avg. enquiry resolution" card populates

### Automated tests

```bash
cd backend && .venv/bin/python -m pytest tests/test_admin_students.py tests/test_admin_enquiries.py -v
cd backend && .venv/bin/python -m pytest tests/ -q
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
```

Part 12 adds 23 backend tests (11 students/overrides, 12 enquiries). Full backend suite now passes 211 tests; frontend remains at 22.

---

## Part 13: Lecturer Interface

### Setup

- [ ] Stack running (`./scripts/start.sh`) with `BANNER_MODE=mock`
- [ ] DB migrated through `d4e5f6a7b8c9` (`alembic upgrade head`)
- [ ] `python -m src.backend.seed` has been run — the lecturer seed row has `banner_id=L00010001` (the lecturer for ACC101 + ACC201 in the mock Banner)
- [ ] Logged in as `lecturer@fnu.ac.fj` / `lecturer123` in one browser and as `student@fnu.ac.fj` / `student123` in another

### Lecturer dashboard

- [ ] Navigate to `/lecturer`; three cards render (My Courses, Students Taught, Grading in Progress) without errors
- [ ] Quick-action links route to `/lecturer/courses` and `/lecturer/grades`
- [ ] A student visiting `/api/lecturer/rosters` directly (`curl -H "Authorization: Bearer <student_token>" http://localhost/api/lecturer/rosters`) receives 403

### Rosters (`/lecturer/courses`)

- [ ] The table lists two offerings for Dr. Tuisawau: `ACC101` (Monday 09-11, Nasinu) and `ACC201` (Monday 10-12, Nasinu)
- [ ] Each row shows a student count (≥1) pulled from the mock roster and grading status "Not started"
- [ ] Click **Roster & grades** on ACC101 — the detail page loads with three seeded students (Apisai Delana, Joeli Ravuama, Sera Koroi)

### Grade entry + autosave

- [ ] On the roster detail page, each student row is editable; pick a grade for Apisai (e.g. `B+`). Within about a second the top-right status switches to "Saving…" then "Saved"
- [ ] Reload the page; the grade you selected persists and the row status shows `draft`
- [ ] `SELECT status, grade, banner_student_id FROM lecturer_grades WHERE offering_id='OFF-2026-S1-ACC101-NAS';` shows the draft row
- [ ] Picking a blank option for a student clears their draft grade (saved as null)
- [ ] Attempting to POST `/api/lecturer/grades` with an invalid grade (`Z`) via curl returns 400 "Invalid grade 'Z'. Allowed: …"
- [ ] Attempting to POST with a `banner_student_id` that is not on the roster returns 400 "… is not on this roster"

### Submit for review

- [ ] Without filling every grade, click **Submit for review** — the button is disabled while any cell is blank (client-side) and backend POST to `/api/lecturer/grades/{offering}/submit` also returns 400 with "All draft entries must have a grade before submitting"
- [ ] Fill grades for every student, click **Submit for review** → the page flashes "Submitted N grades for review" and every row status switches to `submitted`
- [ ] Attempting to edit a submitted row via the UI now disables the grade select; a direct POST to `/api/lecturer/grades` with that student returns 400 "has been submitted for review"

### Finalise (writes to Banner)

- [ ] Click **Finalise & write to Banner**; accept the confirmation prompt
- [ ] The page flashes "Finalised N grades and wrote to Banner"; every row status is now `finalised`
- [ ] Log in as `student@fnu.ac.fj` on the second browser and navigate to **My Grades** → ACC101 appears with the grade you entered (mock Banner reflects the `submit_grade` write on the next roster lookup)
- [ ] `SELECT action, target_id FROM audit_log WHERE action LIKE 'lecturer.grade.%' ORDER BY occurred_at DESC LIMIT 5;` returns `lecturer.grade.draft`, `lecturer.grade.submit`, and `lecturer.grade.finalise` entries
- [ ] Attempting to POST new drafts for the finalised offering returns 400 "is finalised and cannot be edited"

### Exports

- [ ] Click **Export CSV** → a `roster_ACC101.csv` downloads; open it and confirm columns `banner_student_id,student_name,email,attendance_pct,grade,status`
- [ ] Click **Export Excel** → the download is still a CSV (content-type `application/vnd.ms-excel`); double-clicking opens it in Excel/Numbers with the same rows
- [ ] Click **Export PDF** → a `roster_ACC101.pdf` downloads rendering the FNU-branded roster (requires `libpango`/`libcairo` in the image; falls back to a 500 with `PDF export unavailable` if WeasyPrint is missing locally)
- [ ] `curl -H "Authorization: Bearer <student_token>" "http://localhost/api/lecturer/rosters/OFF-2026-S1-ACC101-NAS/export?format=csv"` returns 403

### Ownership scoping (IDOR)

- [ ] With the lecturer token, request `/api/lecturer/rosters/OFF-2026-S1-MGT101-NAS` (taught by L00010002) → 404 "Offering not found or not taught by you"
- [ ] Attempting a grade upsert against that same offering returns 404

### Automated tests

```bash
cd backend && .venv/bin/python -m pytest tests/test_lecturer.py -v
cd backend && .venv/bin/python -m pytest tests/ -q
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
cd frontend && npx next build
```

Part 13 adds 19 backend tests (schema validation, role guards, roster scoping, upsert rejections, submit/finalise workflow, Banner write-through, CSV export). Full backend suite now passes 230 tests; frontend remains at 22.

---

## Part 14: KPI Dashboard

### Setup

- [ ] Stack running (`./scripts/start.sh`) with `BANNER_MODE=mock`
- [ ] DB migrated through `e5f6a7b8c9d0` (`alembic upgrade head`)
- [ ] `python -m src.backend.seed` has been run — the 14 KPI definitions are loaded (12 auto + 2 manual)
- [ ] Logged in as `admin@fnu.ac.fj` / `admin123` in one browser; secondary tabs for `vc@fnu.ac.fj` / `vc123456`, `manager@fnu.ac.fj` / `manager123`, `finance@fnu.ac.fj` / `finance123`

### KPI hub (`/admin/kpi`)

- [ ] Navigate to **KPI Dashboard** from the admin sidebar; the hub shows cards visible to the current role (admin sees all six)
- [ ] As `vc@fnu.ac.fj`, only VC / SLT, Dean, and My KPIs cards appear
- [ ] As `finance@fnu.ac.fj`, only the Finance and My KPIs cards appear

### VC / SLT dashboard (`/admin/kpi/vc`)

- [ ] Before any compute run, cards render with value 0 and a grey or red status (targets set, no data yet)
- [ ] Click **Recompute** → "Recompute complete" shown; the cards reload with current-semester counts (active students ≥ 2 from seeded data, chatbot queries reflect any conversations, etc.)
- [ ] `SELECT action, target_id FROM audit_log WHERE action='kpi.compute' ORDER BY occurred_at DESC LIMIT 1;` returns a row with target_id `YYYY-MM-DD:YYYY-MM-DD`
- [ ] Switch **Period** to Year to date; the cards reload for 1 Jan → today
- [ ] Switch to Custom, pick From=2026-01-01 To=2026-04-30; cards reload
- [ ] As `student@fnu.ac.fj`, `curl -H "Authorization: Bearer <student_token>" http://localhost/api/admin/kpi/dashboard/vc` returns 403

### Dean / Manager dashboard (`/admin/kpi/dean`)

- [ ] Navigate to `/admin/kpi/dean` as manager; the 6 dean KPIs render (processing + service + academic)
- [ ] As finance, visiting the URL redirects via the backend 403 (the fetch shows the error banner)

### Section Head dashboard (`/admin/kpi/section-head`)

- [ ] The "Record manual KPI value" form below the cards lists only manual KPIs (`Monthly Staff Training Hours`, `Team Satisfaction Score`)
- [ ] Submit `Monthly Staff Training Hours = 12`, period = this month, college = `CBHTS` → "Saved manual KPI entry"
- [ ] `SELECT kpi_code, value, college, source FROM kpi_values WHERE kpi_code='staff.training_hours' ORDER BY recorded_at DESC LIMIT 1;` shows the row with `source='manual'` and `college='CBHTS'`
- [ ] `SELECT action, target_id FROM audit_log WHERE action='kpi.manual.record' ORDER BY occurred_at DESC LIMIT 1;` returns the row
- [ ] Attempt to POST `/api/admin/kpi/manual` with an auto KPI (e.g. `enrolment.active_students`) → 400 "KPI does not accept manual input"

### Finance dashboard (`/admin/kpi/finance`)

- [ ] Navigate to `/admin/kpi/finance`; three cards render (revenue, confirmed payments, outstanding receivables) with traffic-light colouring
- [ ] Click **Export CSV**; a `finance_kpi_<start>_<end>.csv` downloads with columns `kpi_code,name,unit,value,target,status`
- [ ] `SELECT action, target_id FROM audit_log WHERE action='kpi.finance.export' ORDER BY occurred_at DESC LIMIT 1;` shows the export audit entry
- [ ] As manager, `curl -H "Authorization: Bearer <manager_token>" http://localhost/api/admin/kpi/dashboard/finance` returns 403

### My KPIs (`/admin/kpi/me`)

- [ ] Navigate to `/admin/kpi/me`; two KPI cards render plus a third "Enquiries You Resolved" card scoped to the current user
- [ ] Assign and resolve an enquiry as the logged-in user (see Part 12), reload — the "Enquiries You Resolved" value increments

### KPI targets (`/admin/kpi/targets`)

- [ ] As admin, navigate to `/admin/kpi/targets`; the table lists all 14 KPIs with editable target fields
- [ ] Change the target for `enrolment.active_students` from 5000 to 10 and click **Save** → "Updated target for enrolment.active_students"
- [ ] Reload `/admin/kpi/vc`; the card for active students now shows green (value ≥ 10)
- [ ] As non-admin (e.g. manager), PUT `/api/admin/kpi/definitions/enrolment.active_students/target` returns 403
- [ ] `SELECT action, target_id, before, after FROM audit_log WHERE action='kpi.target.update' ORDER BY occurred_at DESC LIMIT 1;` captures the before/after value

### Date-range guards

- [ ] `curl -H "Authorization: Bearer <vc_token>" "http://localhost/api/admin/kpi/dashboard/vc?preset=custom"` → 400 "period_start and period_end are required"
- [ ] `curl -H "Authorization: Bearer <vc_token>" "http://localhost/api/admin/kpi/dashboard/vc?preset=custom&period_start=2020-01-01&period_end=2025-01-01"` → 400 "Date range cannot exceed 366 days"

### Scheduler

- [ ] With `KPI_SCHEDULER_ENABLED=true` (the default), restart the backend and watch the logs; within `KPI_COMPUTE_INTERVAL_MINUTES` (default 60), a log line "KPI scheduler: recompute complete" appears
- [ ] Set `KPI_SCHEDULER_ENABLED=false` and restart; logs show "KPI scheduler disabled"; no scheduled job fires

### Automated tests

```bash
cd backend && KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest tests/test_kpi.py -v
cd backend && KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest tests/ -q
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
cd frontend && npx next build
```

Part 14 adds 20 backend tests (traffic-light logic, period helpers, schema validation, RBAC across all five dashboards plus target + manual endpoints, custom-period guards, VC happy-path). Full backend suite now passes 250 tests; frontend remains at 22.

---

## Part 15: Non-Functional Hardening

Part 15 is a cross-cutting hardening pass: response-time logging, audit-log
coverage on Banner writes, DB indexes, error boundaries, cross-browser + axe-core
smoke tests, backup/restore drill, OWASP ZAP scan, and Locust load test.

### Prerequisites

- Stack up via `./scripts/start.sh`
- Backend venv at `backend/.venv`
- Docker running (needed for ZAP)
- `pip install locust` (for the load test)

### 15.1 Response-time middleware

```bash
curl -i http://localhost/api/health 2>&1 | grep -i 'x-response-time-ms'
# Expected: X-Response-Time-ms: <some number>

docker logs docker-backend-1 2>&1 | tail -5
# Expected: one 'request method=GET path=/api/health status=200 response_ms=...'
# line per request
```

### 15.2 Banner writes are audit-logged

```bash
# Log in as a student
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"student@fnu.ac.fj","password":"student123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Confirm registration (triggers register_course + create_invoice on Banner)
curl -s -X POST http://localhost/api/registration/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"offering_ids":["ACC101-2026-S1"],"semester":"S1","year":2026}'

# Verify audit rows were written
docker exec docker-postgres-1 psql -U fnu -d fnu_portal -c \
  "SELECT action, target_type, target_id FROM audit_log \
   WHERE action LIKE 'banner.%' ORDER BY occurred_at DESC LIMIT 5;"
# Expected: banner.register_course + banner.create_invoice rows with
# target_id containing the banner student id
```

### 15.3 DB indexes present

```bash
docker exec docker-postgres-1 psql -U fnu -d fnu_portal -c \
  "\d+ audit_log" | grep ix_audit_log
# Expected: ix_audit_log_actor_occurred, ix_audit_log_target

docker exec docker-postgres-1 psql -U fnu -d fnu_portal -c \
  "\di ix_*" | wc -l
# Expected: >= 12 indexes from the Part 15 migration
```

### 15.4 Frontend error boundaries

1. Start the stack.
2. In the browser dev-tools, introduce a runtime error in a portal route (e.g. temporarily add `throw new Error('boom')` to `dashboard/page.tsx`).
3. Reload `/dashboard`.
4. Expected: "Something went wrong" page with a Try again button — **not** a Next.js default error page.
5. Revert the change.

### 15.5 `/api/health` expanded

```bash
curl -s http://localhost/api/health | python3 -m json.tool
```

Expected fields: `status`, `postgres`, `banner`, `scheduler`, `version`,
`environment`. `scheduler` is one of `running` | `stopped` | `disabled`.

### 15.6 Backup + restore drill

```bash
# Manual backup
./scripts/backup.sh
ls -l backups/ | tail -3
# Expected: a fnu_portal_<timestamp>.sql.gz file, size > 10 KB

# Restore into a disposable DB
docker exec docker-postgres-1 createdb -U fnu fnu_portal_restore_test
gunzip -c backups/fnu_portal_*.sql.gz \
  | docker exec -i docker-postgres-1 psql -U fnu -d fnu_portal_restore_test
docker exec docker-postgres-1 psql -U fnu -d fnu_portal_restore_test -c \
  "SELECT count(*) FROM users;"
# Expected: same user count as production DB

# Cleanup
docker exec docker-postgres-1 dropdb -U fnu fnu_portal_restore_test
```

### 15.7 OWASP ZAP baseline scan

```bash
./scripts/zap_baseline.sh
# Runs OWASP ZAP against http://localhost in Docker
# Report: reports/zap-baseline-<timestamp>.html
open reports/zap-baseline-*.html
```

Expected: zero high-severity findings. Medium/low findings are reviewed and
documented in `docs/SECURITY.md` if accepted.

### 15.8 Locust load test (dev profile)

```bash
./scripts/loadtest.sh
# Default: 100 users, 2 minute run, p95 must stay under 5 s
```

For PLAN.md sign-off against staging:

```bash
USERS=500 P95_MS=3000 RUN_TIME=5m HOST=https://staging.fnu \
  ./scripts/loadtest.sh
```

Expected: PASS — `p95 < P95_MS`. The CSVs under `reports/locust-*` contain
per-endpoint latencies for post-mortem.

### 15.9 Cross-browser + axe-core smoke

```bash
cd frontend
npm install                 # picks up @axe-core/playwright
npm run e2e:install         # one-time browser download (~500 MB)
npm run a11y                # runs tests/e2e/axe.spec.ts across all 5 projects
```

Expected: green across chromium, firefox, webkit, mobile-chrome, mobile-safari.
Any critical/serious axe violation fails the test and prints the offending
elements.

### 15.10 Security headers verification

```bash
curl -s -I http://localhost/ | grep -iE \
  'x-frame-options|x-content-type-options|strict-transport|referrer-policy|permissions-policy'
```

Expected: all 5 headers present. On `/embed/chatbot`, `X-Frame-Options` is
absent and `Content-Security-Policy: frame-ancestors` is present.

### 15.11 Auth-bypass tests (automated)

```bash
cd backend
KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest \
  tests/test_security.py tests/test_banner_audit.py -v
```

Expected: all tests green. Verifies response-time header, IDOR guards on every
student/admin route, unsigned payment callbacks rejected, offer/verify-QR 404
on bogus tokens, Banner writes produce audit rows, token bucket throttles.

### 15.12 Full suites (sanity)

```bash
cd backend && KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest tests/ -q
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
cd frontend && npx next build
```

Part 15 adds ~16 backend tests (`test_security.py` + `test_banner_audit.py`).
Frontend adds the Playwright axe spec (run on demand, not in the default
`vitest` suite). No existing tests should regress.

## Part 16: UAT, Deployment, Documentation

Part 16 is the final-mile pass: UAT with FNU staff, production deployment,
user guides, post-launch support. Most of this is exercised *during* UAT
against the staging environment — see [UAT_PLAN.md](UAT_PLAN.md) for the
facilitated 5-day plan. The automated artefacts below are what ship in this
repo and must pass before UAT begins.

### Prerequisites

- Stack up via `./scripts/start.sh`
- Backend venv at `backend/.venv`
- `openssl` on PATH
- For production validator tests, no `.env` in project root (they use explicit
  overrides); run from `backend/` with `KPI_SCHEDULER_ENABLED=false`

### 16.1 Production config validator — reject placeholder secrets

```bash
cd backend
KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest \
  tests/test_config_validators.py -v
```

Expected: 14 tests green. Covers: placeholder markers (`change-me`,
`REPLACE`, `your-key-here`), JWT/ID-card min length, live-mode payment
credential length, Banner live URL must be https, OpenRouter key required
when chatbot live, SMTP/SMS credentials, `PUBLIC_APP_URL` must be https.

### 16.2 Structured JSON logging

```bash
cd backend
LOG_FORMAT=json KPI_SCHEDULER_ENABLED=false .venv/bin/python -c "
from src.backend.logging_config import configure_logging
import logging
configure_logging()
logging.getLogger('fnu.test').info('hello', extra={
  'method':'GET','path':'/foo','status':200,'response_ms':12.3
})
"
```

Expected: one JSON line printed with `timestamp`, `level`, `logger`,
`message`, plus the structured extras (`method`, `path`, `status`,
`response_ms`).

Full request-line format in a live container:

```bash
docker logs docker-backend-1 2>&1 | grep -E '^\{' | head -3
```

Expected: JSON-per-line with request method / path / status / response_ms
fields under production compose.

### 16.3 Generate production secrets

```bash
./scripts/generate_secrets.sh
```

Expected: five `KEY=value` lines with 64-char hex values (JWT_SECRET,
NEXTAUTH_SECRET, ID_CARD_SECRET, POSTGRES_PASSWORD, FNU_APP_DB_PASSWORD).
Safe to re-run any time; every invocation yields fresh secrets.

### 16.4 Production compose config renders

```bash
cp .env.production.example .env.production
./scripts/generate_secrets.sh >> .env.production.generated
# Manually copy the generated values into .env.production, then:
cd docker
docker compose -f docker-compose.prod.yml config >/dev/null && echo OK
```

Expected: `OK` (no stderr). Exercises `${...:?err}` required-variable checks.
Clean up `.env.production*` afterwards.

### 16.5 Production smoke test

Against a running local stack (dev `docker-compose.yml`) the smoke test
passes most checks but fails the production-only gates (Swagger should be
404 but is enabled in dev). For a pass run against a `ENVIRONMENT=production`
deployment:

```bash
PORTAL_URL=https://staging.portal.fnu.ac.fj ./scripts/smoke_test.sh
```

Expected: all checks pass with green ticks. Exits 0 on success, 1 if any
check fails. Cover: TLS, security headers, CSP on /embed/*, /api/health
subsystems, Swagger disabled, auth 401s, unsigned payment callback rejected,
landing SSR content.

### 16.6 Uptime monitor self-test

```bash
PORTAL_URL=https://staging.portal.fnu.ac.fj STATE_DIR=/tmp/fnu-uptime \
  ./scripts/uptime_monitor.sh && echo OK
rm -rf /tmp/fnu-uptime
```

Expected: `OK` when staging is healthy. Point it at an unreachable host to
confirm the failure path emits to stderr.

### 16.7 Deployment runbook dry-run

Walk through every numbered step of [DEPLOYMENT.md](DEPLOYMENT.md) §1–§6 on
the staging VM without running destructive commands. Confirm:

- DNS / CAA records resolve.
- `scripts/generate_secrets.sh` produces 64-char values.
- The unprivileged `fnu_app` role SQL in §4.1 runs cleanly against a disposable
  Postgres.
- `docker compose -f docker-compose.prod.yml config` parses (§16.4 above).
- Bootstrap admin creation snippet runs against the staging DB.
- Smoke test exits 0 against staging (§16.5 above).

Tick each step off in [TEST_REPORT.md](TEST_REPORT.md) before proceeding to
production cutover.

### 16.8 Incident-response tabletop

Schedule a 45-minute exercise with the UAT team. Pick one scenario from
[INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md):

- Credential compromise (JWT secret leaked)
- Portal unreachable (backend container OOM)
- Payment callback fraud (suspect M-PAiSA activity)

Facilitator narrates the alerts; team follows the runbook. Capture gaps in
the runbook and improve before go-live.

### 16.9 Backup restore drill

Reuses the Part 15 restore drill (see §15.6). For Part 16 sign-off, prove
the restored DB boots the application:

```bash
# After restoring the backup into fnu_portal_restore_test per §15.6, spin up
# a one-shot backend container pointing at the restored DB and hit /api/health
DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal_restore_test \
  docker compose -f docker-compose.prod.yml run --rm -p 18000:8000 backend \
  uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 &
sleep 5
curl -sf http://localhost:18000/api/health | grep -q '"status":"ok"' && echo OK
```

Expected: `OK`. Kills the container after.

### 16.10 User-guide validation

Ask one non-technical FNU staff member to complete each of:

- Full student journey from [USER_GUIDE_STUDENT.md](USER_GUIDE_STUDENT.md)
  §1–§7 using only the guide (no coaching).
- Staff admin workflow from [USER_GUIDE_STAFF.md](USER_GUIDE_STAFF.md) §3–§6
  and §9.

Record friction points and edit the guide accordingly before go-live.

### 16.11 Full regression (sanity, all parts)

```bash
cd backend && KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest tests/ -q
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
cd frontend && npx next build
```

Expected: all green. Part 16 adds **19 backend tests** (5 in
`test_logging_config.py`, 14 in `test_config_validators.py`); no existing
test should regress.
