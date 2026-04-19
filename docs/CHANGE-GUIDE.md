# FNU Web Portal — Change Management Guide

An ITIL-aligned guide for operations teams to plan, approve, implement, and review changes to the FNU Web Portal. Every change — from a new API endpoint to a database migration — follows the same lifecycle to protect service availability and data integrity.

---

## Table of Contents

1. [Change Management Lifecycle](#1-change-management-lifecycle)
2. [Change Classification](#2-change-classification)
3. [Change Advisory Board (CAB)](#3-change-advisory-board-cab)
4. [Environment Strategy](#4-environment-strategy)
5. [Change Procedures by Type](#5-change-procedures-by-type)
   - [5.1 Add a Backend API Endpoint](#51-add-a-backend-api-endpoint)
   - [5.2 Add a Frontend Page or Component](#52-add-a-frontend-page-or-component)
   - [5.3 Modify the Database Schema](#53-modify-the-database-schema)
   - [5.4 Add or Update a User Role](#54-add-or-update-a-user-role)
   - [5.5 Add a New Navigation Link](#55-add-a-new-navigation-link)
   - [5.6 Add an Environment Variable or Secret](#56-add-an-environment-variable-or-secret)
   - [5.7 Integrate a New External Service](#57-integrate-a-new-external-service)
   - [5.8 Update Dependencies](#58-update-dependencies)
   - [5.9 Modify the CI Pipeline](#59-modify-the-ci-pipeline)
   - [5.10 Change Brand Assets or Colours](#510-change-brand-assets-or-colours)
   - [5.11 Add or Update Chatbot FAQ Data](#511-add-or-update-chatbot-faq-data)
   - [5.12 Modify Payment Gateway Configuration](#512-modify-payment-gateway-configuration)
   - [5.13 Scale or Reconfigure Infrastructure](#513-scale-or-reconfigure-infrastructure)
6. [Rollback Procedures](#6-rollback-procedures)
7. [Post-Implementation Review](#7-post-implementation-review)
8. [Templates](#8-templates)

---

## 1. Change Management Lifecycle

Every change follows this lifecycle, regardless of size. Smaller changes move through faster; larger ones require more documentation at each stage.

```
  ┌─────────────┐
  │   Request    │  Developer or stakeholder raises an RFC
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Classify   │  Standard / Normal / Emergency (see section 2)
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Assess     │  Impact analysis, risk rating, rollback plan
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Approve    │  CAB or delegated approver (see section 3)
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Plan       │  Implementation steps, test plan, schedule
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Build      │  Develop on feature branch, pass CI
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Test       │  Automated tests + manual verification on staging
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Deploy     │  Merge to main, deploy to production
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Verify     │  Smoke test production, monitor for regressions
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Review     │  Post-implementation review (see section 7)
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Close      │  Update documentation, close RFC
  └─────────────┘
```

---

## 2. Change Classification

### Standard Changes (Pre-Approved)

Low-risk, repeatable changes that have been pre-approved by the CAB. No individual approval needed.

| Change | Conditions for Pre-Approval |
|---|---|
| Add/update chatbot FAQ entries | Via admin UI, no code deploy |
| Update notification templates | Via admin UI, no code deploy |
| Reset a user's lockout or password | Via database or admin UI |
| Restart a container | No config changes |
| Run database seed on staging | Non-destructive, idempotent |
| Update `.env` secrets (key rotation) | Same variable, new value |
| Add a test (no production code change) | CI must pass |

### Normal Changes

Require assessment, approval, and testing before deployment.

| Risk Level | Examples | Approval |
|---|---|---|
| Low | New frontend page, new FAQ endpoint, CSS/brand update, dependency patch | Lead developer |
| Medium | New API endpoint, database migration (additive), new external integration, new role | Lead developer + product owner |
| High | Database migration (destructive), payment gateway change, auth flow change, infrastructure scaling | Full CAB |

### Emergency Changes

Critical fixes for production incidents. Expedited approval from one CAB member. Full retrospective required within 48 hours.

| Trigger | Process |
|---|---|
| Security vulnerability (active exploit) | Hotfix branch → one approver → deploy → retrospective |
| Data loss or corruption | Restore from backup → hotfix → one approver → deploy |
| Service outage >15 minutes | Hotfix or rollback → one approver → deploy → retrospective |

---

## 3. Change Advisory Board (CAB)

### Membership

| Role | Responsibility |
|---|---|
| Project Lead | Final approval authority, risk acceptance |
| Lead Developer | Technical assessment, impact analysis |
| FNU IT Representative | Infrastructure and network impact |
| Product Owner (FNU) | Business impact and user communication |
| Operations Lead | Deployment coordination, monitoring |

### Approval Matrix

```
Change Risk Level → Required Approvers
│
├─ Standard     → None (pre-approved)
├─ Low Normal   → Lead Developer
├─ Medium Normal → Lead Developer + Product Owner
├─ High Normal  → Full CAB (majority)
└─ Emergency    → Any one CAB member (retrospective within 48h)
```

### Meeting Cadence

- Weekly CAB review for queued Normal changes (during active development)
- Monthly CAB review during steady-state operations
- Emergency CAB convened ad-hoc via group chat/call

---

## 4. Environment Strategy

### Environments

| Environment | Purpose | URL | Deploy Method |
|---|---|---|---|
| Local Dev | Individual developer testing | http://localhost | `./scripts/start.sh` |
| Staging | Integration testing, UAT | TBD (staging URL) | Merge to `staging` branch → auto-deploy |
| Production | Live service | TBD (portal.fnu.ac.fj) | Merge to `main` → tagged release → deploy |

### Promotion Flow

```
Feature Branch → Pull Request → CI Green → Code Review → Merge to main
                                                              │
                                                              v
                                                    Deploy to Staging
                                                              │
                                                              v
                                                    Manual Verification
                                                              │
                                                              v
                                                    Tag Release (vX.Y.Z)
                                                              │
                                                              v
                                                    Deploy to Production
                                                              │
                                                              v
                                                    Production Smoke Test
```

### Branching Convention

| Branch | Purpose | Merge Target |
|---|---|---|
| `main` | Production-ready code | — |
| `feature/<name>` | New features | `main` via PR |
| `fix/<name>` | Bug fixes | `main` via PR |
| `hotfix/<name>` | Emergency production fixes | `main` via PR (expedited) |

### Version Numbering

Use semantic versioning: `vMAJOR.MINOR.PATCH`

- **MAJOR**: Breaking API changes, database schema changes requiring data migration
- **MINOR**: New features, new endpoints, additive schema changes
- **PATCH**: Bug fixes, dependency updates, documentation

---

## 5. Change Procedures by Type

Each procedure below lists the files to modify, the testing requirements, and the rollback approach. Follow the lifecycle in section 1 for governance.

---

### 5.1 Add a Backend API Endpoint

**Classification**: Normal (Low)

**Impact Assessment**:
- Does the endpoint require authentication? Which roles?
- Does it read from or write to the database?
- Does it interact with external services (Banner, payment, LLM)?
- Does it need a new Pydantic model?

**Implementation Steps**:

```
Step 1: Define the contract
│
├─ Add the endpoint contract to docs/API.md
│  └─ Include: method, path, auth level, request/response schema
│
├─ Create Pydantic request/response models
│  └─ File: backend/src/backend/db/schemas.py
│  └─ OR: new file in backend/src/backend/db/ if domain-specific
│
Step 2: Implement the route
│
├─ Create or edit the route file
│  └─ Directory: backend/src/backend/api/
│  └─ Convention: one file per bounded context (auth.py, applications.py, payments.py)
│
├─ Apply role-based access control
│  └─ Use: Depends(require_role("student")) or Depends(get_current_user)
│  └─ NEVER implement ad-hoc auth checks
│
├─ Register the router in main.py
│  └─ File: backend/src/backend/main.py
│  └─ Add: app.include_router(new_router, prefix="/api")
│
Step 3: Write tests
│
├─ Unit test for business logic (>=80% coverage)
│  └─ Directory: backend/tests/
│
├─ Happy-path integration test
│
├─ Auth-failure test (no token → 401, wrong role → 403)
│
Step 4: Regenerate frontend types
│
├─ Run: cd frontend && npm run generate:types
│  └─ This regenerates frontend/lib/api-types.ts from the backend OpenAPI schema
│  └─ Commit the updated types file
│
Step 5: Verify
│
├─ Run: cd backend && uv run pytest tests/ -v
├─ Run: cd backend && uv run ruff check src/ tests/
├─ Run: cd backend && uv run mypy src/ --ignore-missing-imports
└─ Verify endpoint in Swagger UI: http://localhost:8000/api/docs
```

**Files Typically Modified**:
| File | Purpose |
|---|---|
| `docs/API.md` | Endpoint contract |
| `backend/src/backend/db/schemas.py` | Pydantic models |
| `backend/src/backend/api/<context>.py` | Route handler |
| `backend/src/backend/main.py` | Router registration |
| `backend/tests/test_<context>.py` | Tests |
| `frontend/lib/api-types.ts` | Auto-generated types |

**Rollback**: Revert the commit. No database changes involved.

---

### 5.2 Add a Frontend Page or Component

**Classification**: Normal (Low)

**Impact Assessment**:
- Is it a public page or authenticated?
- Which route group: `(public)`, `(portal)`, `(admin)`, `(lecturer)`?
- Does it need data from a backend API?
- Server Component or Client Component?

**Implementation Steps**:

```
Step 1: Choose the rendering strategy
│
├─ Data display only (no user interaction)?
│  └─ Use a Server Component (default, no "use client" directive)
│  └─ Fetch data server-side using fetch() with INTERNAL_API_URL
│
├─ Interactive (forms, state, event handlers)?
│  └─ Use a Client Component ("use client" at top of file)
│  └─ Use TanStack Query or apiFetch for data
│
└─ Mixed?
   └─ Server Component shell with Client Component children
   └─ Pass data down as props

Step 2: Create the page file
│
├─ Public page:     frontend/app/(public)/<route>/page.tsx
├─ Student portal:  frontend/app/(portal)/<route>/page.tsx
├─ Admin panel:     frontend/app/(admin)/admin/<route>/page.tsx
├─ Lecturer panel:  frontend/app/(lecturer)/lecturer/<route>/page.tsx
│
├─ The route group determines which layout wraps the page
│  └─ (portal) → portal layout with sidebar, header, fees banner
│  └─ (admin)  → admin layout with dark header, admin sidebar
│  └─ (lecturer) → lecturer layout with lecturer sidebar
│  └─ (public) → no auth required, minimal chrome

Step 3: Create shared components (if needed)
│
├─ Directory: frontend/components/
├─ Convention: one component per file, named export matching file name
├─ Include: accessible markup (aria labels, roles, keyboard navigation)
└─ Include: 44px minimum tap targets for interactive elements

Step 4: Handle route protection
│
├─ Authenticated routes are automatically protected by middleware.ts
│  └─ Unauthenticated users are redirected to /login
│
├─ Public routes: add the path to PUBLIC_PATHS in middleware.ts
│  └─ File: frontend/middleware.ts
│  └─ const PUBLIC_PATHS = ["/", "/login", "/apply", ...]

Step 5: Write tests
│
├─ Vitest unit test for the component
│  └─ File: alongside the component (e.g., component-name.test.tsx)
│  └─ Mock next/navigation, next-auth/react as needed
│
├─ Check: afterEach(() => { cleanup(); }) to avoid jsdom teardown errors

Step 6: Verify
│
├─ Run: cd frontend && npx vitest run
├─ Run: cd frontend && npx tsc --noEmit
├─ Run: cd frontend && npx next build
├─ Browser test: check the page at multiple viewports (375px, 768px, 1280px)
└─ Keyboard test: Tab through all interactive elements
```

**Files Typically Modified**:
| File | Purpose |
|---|---|
| `frontend/app/(<group>)/<route>/page.tsx` | Page component |
| `frontend/components/<name>.tsx` | Shared component |
| `frontend/components/<name>.test.tsx` | Component tests |
| `frontend/middleware.ts` | Route protection (public pages only) |

**Rollback**: Revert the commit. Frontend-only change.

---

### 5.3 Modify the Database Schema

**Classification**: Normal (Medium to High)

**CRITICAL**: Database migrations can cause data loss if not handled carefully. Always test on staging with production-like data before applying to production. Destructive migrations (drop column, rename table, change type) are HIGH risk.

**Impact Assessment**:
- Is this additive (new table, new nullable column) or destructive (drop, rename, type change)?
- Does it affect existing data?
- Does the application work with both old and new schemas during deployment? (Zero-downtime consideration)
- Is a data migration (backfill) needed?

**Implementation Steps**:

```
Step 1: Update the SQLAlchemy model
│
├─ File: backend/src/backend/db/models.py
├─ Add/modify the mapped_column definitions
├─ If adding a new table: register in backend/src/backend/db/base.py imports

Step 2: Generate the Alembic migration
│
├─ Run from backend/ directory:
│  DATABASE_URL=postgresql+asyncpg://fnu:fnu_dev_password@localhost:5432/fnu_portal \
│    uv run alembic revision --autogenerate -m "description of change"
│
├─ Review the generated migration file:
│  └─ Directory: backend/src/backend/db/migrations/versions/
│  └─ Check: upgrade() and downgrade() functions are correct
│  └─ Check: No unintended changes (autogenerate can pick up ordering differences)
│
├─ IMPORTANT: Generated migration files are excluded from ruff linting
│  └─ Configured in pyproject.toml: extend-exclude = ["src/backend/db/migrations/versions"]

Step 3: Test the migration
│
├─ Apply: uv run alembic upgrade head
├─ Verify: \dt in psql to check table structure
├─ Rollback: uv run alembic downgrade -1
├─ Re-apply: uv run alembic upgrade head
│
├─ If data migration is needed:
│  └─ Write a separate Python script or add SQL to the migration's upgrade()
│  └─ Test with representative data volumes

Step 4: Update dependent code
│
├─ Update Pydantic schemas if API contracts changed
├─ Update API routes if new fields are exposed
├─ Update seed command if new required fields added
├─ Regenerate frontend types: cd frontend && npm run generate:types

Step 5: Update documentation
│
├─ docs/DATABASE.md — update table definitions
├─ docs/API.md — update affected endpoint contracts

Step 6: Verify
│
├─ Run: cd backend && uv run pytest tests/ -v
├─ Run: cd backend && uv run alembic upgrade head (clean DB)
├─ Run: cd backend && uv run python -m src.backend.seed
└─ Run full stack: ./scripts/start.sh and verify affected features
```

**Additive Migration Checklist** (Low–Medium Risk):
- [ ] New columns are nullable OR have a default value
- [ ] No existing data is modified
- [ ] Application works with the new schema before new code is deployed
- [ ] Migration tested up and down
- [ ] Seed script updated

**Destructive Migration Checklist** (High Risk):
- [ ] Database backup taken before applying
- [ ] Data migration script written and tested
- [ ] Application code updated to not reference removed columns BEFORE migration
- [ ] Two-phase deployment: deploy code that handles both schemas, then apply migration
- [ ] Rollback plan documented with data restoration steps
- [ ] CAB approval obtained

**Rollback**:
- Additive: `alembic downgrade -1` (safe if no data depends on new columns)
- Destructive: Restore from database backup (always take one before applying)

---

### 5.4 Add or Update a User Role

**Classification**: Normal (Medium)

**Impact Assessment**:
- Which routes/features should the new role access?
- Does it need its own layout/dashboard?
- Does it affect existing role checks?

**Implementation Steps**:

```
Step 1: Define the role
│
├─ Add to backend role validation
│  └─ The role column in the users table is TEXT — no enum migration needed
│  └─ Update any role validation lists in Pydantic schemas
│
├─ Document the role and its permissions in docs/API.md

Step 2: Apply access control
│
├─ Backend: Use require_role() dependency on relevant routes
│  └─ File: backend/src/backend/auth.py (require_role function)
│  └─ Usage: Depends(require_role("new_role"))
│  └─ For multiple roles: Depends(require_role("admin", "staff", "new_role"))
│
├─ Frontend: Add role-based rendering if needed
│  └─ Check session.user.role in components

Step 3: Create a route group layout (if needed)
│
├─ Directory: frontend/app/(<role>)/
├─ Create layout.tsx with role-specific sidebar and header
├─ Create <role>/page.tsx as the dashboard landing

Step 4: Update seed data
│
├─ File: backend/src/backend/seed.py
├─ Add a test user with the new role

Step 5: Write tests
│
├─ Backend: test that the role can access its routes (200)
├─ Backend: test that other roles cannot access (403)
├─ Frontend: test that the layout renders for the role

Step 6: Update documentation
│
├─ docs/API.md — document which endpoints the role can access
├─ docs/TESTING.md — add test credentials for the new role
├─ docs/TROUBLESHOOTING.md — add to test credentials table
```

**Rollback**: Revert the commit. Remove the role from the seed if added to production data.

---

### 5.5 Add a New Navigation Link

**Classification**: Standard (Pre-Approved if page already exists)

**Implementation Steps**:

```
Which sidebar?
│
├─ Student portal sidebar
│  └─ File: frontend/components/portal-nav.tsx
│  └─ Add to STUDENT_LINKS array:
│     { href: "/new-page", label: "New Page" }
│
├─ Admin sidebar
│  └─ File: frontend/app/(admin)/layout.tsx
│  └─ Add to ADMIN_LINKS array
│
└─ Lecturer sidebar
   └─ File: frontend/app/(lecturer)/layout.tsx
   └─ Add to LECTURER_LINKS array

Verify:
├─ The target page exists (href matches a page.tsx route)
├─ Active state highlighting works (pathname === href)
├─ Run frontend tests: npx vitest run
└─ Visual check at 375px and 1280px viewports
```

**Rollback**: Remove the entry from the links array.

---

### 5.6 Add an Environment Variable or Secret

**Classification**: Normal (Low)

**CRITICAL**: Never put secrets in `NEXT_PUBLIC_*` variables — they are embedded in the client JavaScript bundle and visible to anyone.

**Implementation Steps**:

```
Step 1: Determine scope
│
├─ Backend only → Add to backend/src/backend/config.py (Settings class)
├─ Frontend server-side only → Use in Server Components via process.env
├─ Frontend client-side → Use NEXT_PUBLIC_ prefix (NON-SECRET values only)
└─ Docker only → Add to docker/docker-compose.yml environment block

Step 2: Add to Settings (backend)
│
├─ File: backend/src/backend/config.py
│  class Settings(BaseSettings):
│      new_variable: str = "default-value"
│
├─ Access in code: settings.new_variable

Step 3: Update templates
│
├─ File: .env.example — add with a safe placeholder value
│  └─ e.g., NEW_VARIABLE=change-me
│
├─ File: docker/docker-compose.yml — add to the relevant service's environment block
│  └─ Backend vars go under services.backend.environment
│  └─ Frontend vars go under services.frontend.environment

Step 4: Update documentation
│
├─ docs/TROUBLESHOOTING.md — add to environment variables table
├─ docs/README.md — mention if it's required for setup

Step 5: Deploy
│
├─ Add the actual value to .env on each environment (dev, staging, production)
├─ Restart the affected container(s)
├─ Verify: the feature works with the new variable set
├─ Verify: the feature degrades gracefully if the variable is unset (if applicable)
```

**Rollback**: Remove the variable from `.env` and restart. Code should handle the default value.

---

### 5.7 Integrate a New External Service

**Classification**: Normal (Medium)

**Impact Assessment**:
- What data does the service receive? Any PII?
- What happens when the service is unavailable?
- Is there a sandbox/test environment?
- Does it require firewall/network changes?

**Implementation Steps**:

```
Step 1: Build an adapter
│
├─ Follow the adapter pattern used by Banner and payment gateways
│  └─ Directory: backend/src/backend/services/
│  └─ Create: <service>_adapter.py with an interface class
│  └─ Create: <service>_mock.py with a mock implementation
│
├─ The mock adapter should:
│  └─ Honour the same interface as the real adapter
│  └─ Return realistic test data
│  └─ Be selectable via environment variable (e.g., SERVICE_MODE=mock|live)
│
├─ The real adapter should:
│  └─ Handle timeouts (set explicit timeout, e.g., 10s)
│  └─ Handle errors (return structured error, never crash)
│  └─ Log requests/responses (without PII or secrets)
│  └─ Verify signatures/certificates where applicable

Step 2: Add configuration
│
├─ Add credentials to .env.example (with placeholders)
├─ Add to Settings in config.py
├─ Add to docker-compose.yml

Step 3: Add health check
│
├─ Include the service in /api/health response
│  └─ File: backend/src/backend/api/health.py
│  └─ Add a check that the service is reachable

Step 4: Write tests
│
├─ Unit tests against the mock adapter
├─ Integration test against sandbox (gated behind credential availability)
├─ Failure mode tests: service down, timeout, malformed response

Step 5: Update documentation
│
├─ docs/ARCHITECTURE.md — add to component diagram
├─ docs/API.md — document affected endpoints
├─ docs/TROUBLESHOOTING.md — add troubleshooting section
```

**Rollback**: Switch to mock mode via environment variable. No code deploy needed.

---

### 5.8 Update Dependencies

**Classification**: Normal (Low for patches, Medium for major versions)

**Implementation Steps**:

```
Backend (Python):
│
├─ File: backend/pyproject.toml
├─ Update version constraint
├─ Run: cd backend && uv sync
├─ Run: cd backend && uv run pytest tests/ -v
├─ Run: cd backend && uv run ruff check src/ tests/
├─ Run: cd backend && uv run mypy src/ --ignore-missing-imports
└─ Check for breaking changes in the dependency changelog

Frontend (Node.js):
│
├─ File: frontend/package.json
├─ Run: cd frontend && npm update <package>
│  └─ OR for major: npm install <package>@latest
├─ Run: cd frontend && npx vitest run
├─ Run: cd frontend && npx tsc --noEmit
├─ Run: cd frontend && npx next build
└─ Check for breaking changes in the dependency changelog

Security patches:
│
├─ Backend: uv audit (or pip-audit)
├─ Frontend: npm audit
├─ Fix: update the vulnerable package
└─ If no fix available: document the risk and apply a workaround
```

**Rollback**: Revert `pyproject.toml` / `package.json` and lock files, re-install.

---

### 5.9 Modify the CI Pipeline

**Classification**: Normal (Low)

**Implementation Steps**:

```
File: .github/workflows/ci.yml

Current jobs:
├─ backend:    ruff lint → mypy type check → pytest tests
├─ frontend:   npm lint → tsc type check → vitest tests
├─ contract-check: verify generated types match backend schema
└─ docker-build: build both Docker images

To add a new CI step:
│
├─ Identify which job it belongs to (backend, frontend, or new job)
├─ Add the step to the appropriate job
├─ Test by pushing to a feature branch (CI runs on all PRs to main)
├─ Verify the step passes before merging

To add a new CI job:
│
├─ Add under the 'jobs:' key in ci.yml
├─ Set 'needs:' if it depends on other jobs
├─ Use the same runner (ubuntu-latest) unless a different OS is needed
```

**Rollback**: Revert the CI file. Broken CI does not affect production.

---

### 5.10 Change Brand Assets or Colours

**Classification**: Normal (Low)

**Impact Assessment**: Colour changes affect every page. Test visually across the full application.

**Implementation Steps**:

```
Step 1: Update Tailwind theme tokens (single source of truth)
│
├─ File: frontend/app/globals.css
├─ Modify the @theme block:
│  @theme {
│    --color-fnu-blue: #003A70;    /* primary */
│    --color-fnu-gold: #FFB81C;    /* accent */
│    --color-success: #2E7D32;
│    --color-warning: #F9A825;
│    --color-danger: #C62828;
│    --color-dark: #0A1F33;
│    --color-gray: #6B7280;
│    --color-surface: #F4F6F9;
│  }
│
├─ All components use Tailwind utility classes (bg-fnu-blue, text-fnu-gold, etc.)
│  └─ No hardcoded hex values in component files
│  └─ Changing the theme tokens changes the entire application

Step 2: Update logo/letterhead images
│
├─ Directory: frontend/public/
├─ Replace image files (keep same filenames to avoid code changes)
├─ If filename changes: grep for the old filename and update references

Step 3: Verify
│
├─ Run: cd frontend && npx next build
├─ Visual check: landing page, login, dashboard, admin panel
├─ WCAG contrast check: text on new background colours must meet 4.5:1 ratio
│  └─ Tool: Chrome DevTools > Accessibility > Contrast
├─ PDF templates: check offer letter and invoice render correctly
│  └─ PDF templates use separate CSS — update those too
```

**Rollback**: Revert the `globals.css` changes.

---

### 5.11 Add or Update Chatbot FAQ Data

**Classification**: Standard (Pre-Approved)

This change does NOT require a code deployment.

```
Option A: Via Admin UI (preferred, no deploy needed)
│
├─ Login as admin (admin@fnu.ac.fj)
├─ Navigate to /admin/chatbot/knowledge
├─ Add / Edit / Delete FAQ entries
├─ Test: Ask the chatbot the question covered by the FAQ
└─ Verify: Response includes the FAQ content

Option B: Via seed data (for bulk initial load)
│
├─ File: backend/seed/chatbot_faq.json
├─ Add entries in the format:
│  { "question": "...", "answer": "...", "category": "..." }
├─ Run seed: DATABASE_URL=... uv run python -m src.backend.seed
└─ Test: Verify via chatbot
```

**Rollback**: Delete or revert the FAQ entry via admin UI or database.

---

### 5.12 Modify Payment Gateway Configuration

**Classification**: Normal (High)

**CRITICAL**: Payment changes directly affect student finances. Test exhaustively on sandbox before production. Never test on production with real student funds.

```
Step 1: Change assessment
│
├─ Is this a credential rotation?
│  └─ Update .env only — no code change needed
│  └─ Restart backend container
│  └─ Test: initiate a sandbox payment to verify new credentials work
│
├─ Is this a new payment method?
│  └─ Follow section 5.7 (Integrate a New External Service)
│  └─ Build adapter + mock
│  └─ Add callback route to backend
│  └─ Add callback route to middleware.ts PUBLIC_PATHS
│
├─ Is this changing the callback URL?
│  └─ Update in gateway merchant dashboard
│  └─ Update in middleware.ts PUBLIC_PATHS if path changed
│  └─ Ensure proxy routes the callback directly to backend
│  └─ Test: trigger a sandbox callback and verify it reaches backend

Step 2: Testing (mandatory for ALL payment changes)
│
├─ Sandbox test: full initiate → redirect → callback → status update cycle
├─ Idempotency test: replay the same callback twice → only one state change
├─ Failure test: simulate gateway timeout, signature mismatch
├─ Reconciliation: verify payment_attempts table matches gateway records
└─ Sign-off: product owner verifies correct amounts on student account
```

**Rollback**: Switch to previous credentials in `.env` and restart. For code changes, revert the commit.

---

### 5.13 Scale or Reconfigure Infrastructure

**Classification**: Normal (Medium to High)

```
Horizontal scaling (more containers):
│
├─ Backend is stateless — can run multiple instances behind load balancer
├─ Frontend is stateless — can run multiple instances
├─ Postgres: single instance (scale vertically or use read replicas)
│
├─ If using Docker Compose:
│  └─ docker compose up --scale backend=3 --scale frontend=2
│
├─ If using container platform (Railway, Render, Fly.io):
│  └─ Increase instance count in platform dashboard

Vertical scaling (bigger server):
│
├─ Increase RAM/CPU on host
├─ Adjust Postgres connection pool limits:
│  └─ backend/src/backend/db/session.py — pool_size, max_overflow
├─ Adjust uvicorn worker count:
│  └─ docker/Dockerfile.backend CMD — --workers N (usually 2-4 per CPU)

Adding a CDN:
│
├─ Place CDN in front of nginx for static assets
├─ Configure cache headers for /_next/static/* (long-lived cache)
├─ Do NOT cache /api/* or authenticated pages
```

**Rollback**: Revert instance count or server size. No data impact.

---

## 6. Rollback Procedures

### Rollback Decision Tree

```
Is the change causing a production issue?
│
├─ YES
│  │
│  ├─ Is it a code change?
│  │  ├─ YES → Git revert + redeploy (see 6.1)
│  │  └─ NO (config/env change) → Revert .env + restart containers (see 6.2)
│  │
│  ├─ Is it a database change?
│  │  ├─ Additive (new column/table) → alembic downgrade -1 (see 6.3)
│  │  └─ Destructive (dropped/renamed) → Restore from backup (see 6.4)
│  │
│  └─ Is it an external service change?
│     └─ Switch to mock/previous adapter via env var + restart (see 6.5)
│
└─ NO → Monitor and proceed
```

### 6.1 Code Rollback

```bash
# Create a revert commit (preserves history)
git revert <commit-hash>
git push origin main

# Redeploy
cd docker && docker compose up --build -d
```

### 6.2 Configuration Rollback

```bash
# Restore previous .env values
# Restart affected containers
cd docker && docker compose restart backend
# OR
cd docker && docker compose restart frontend
```

### 6.3 Database Rollback (Additive)

```bash
cd backend
DATABASE_URL=... uv run alembic downgrade -1
# Verify
DATABASE_URL=... uv run alembic current
```

### 6.4 Database Rollback (Destructive — from backup)

```bash
# Stop the application
./scripts/stop.sh

# Restore database from backup
docker exec -i docker-postgres-1 psql -U fnu -d fnu_portal < backup_YYYYMMDD.sql

# Revert application code to match the restored schema
git revert <commit-hash>

# Restart
./scripts/start.sh
```

### 6.5 External Service Rollback

```bash
# Switch to mock adapter
# In .env:
BANNER_MODE=mock
PAYMENT_MODE=stub

# Restart backend
cd docker && docker compose restart backend
```

---

## 7. Post-Implementation Review

Complete within 5 business days of deployment for Normal changes, 2 business days for Emergency changes.

### PIR Checklist

- [ ] **Was the change implemented as planned?** If not, document deviations.
- [ ] **Did the change achieve its objective?** Verify against the RFC success criteria.
- [ ] **Were there any incidents during or after deployment?** Document and root-cause.
- [ ] **Was rollback needed?** If so, document why and how long it took.
- [ ] **Are monitoring and alerting in place for the new functionality?**
- [ ] **Is documentation updated?** (API.md, DATABASE.md, TESTING.md, TROUBLESHOOTING.md)
- [ ] **Are tests adequate?** (Unit, integration, manual test plan)
- [ ] **Lessons learned?** What would we do differently next time?

### PIR Distribution

- Filed alongside the RFC in the project's change log
- Discussed at the next CAB meeting
- Emergency changes: presented at a retrospective within 48 hours

---

## 8. Templates

### 8.1 Request for Change (RFC) Template

```
RFC-<YYYY>-<NNN>: <Title>

Requester:      <Name / Role>
Date:           <YYYY-MM-DD>
Classification: Standard / Normal (Low/Medium/High) / Emergency
Target Date:    <YYYY-MM-DD>

## Description
<What is being changed and why>

## Business Justification
<Why this change is needed. Link to ticket/issue if applicable.>

## Impact Assessment
- Services affected:    <backend / frontend / database / infrastructure>
- Users affected:       <students / staff / admin / all>
- Downtime required:    <yes (estimated duration) / no>
- Data migration:       <yes / no>
- External dependencies:<Banner / payment gateway / LLM / none>

## Risk Assessment
- Risk level:           <Low / Medium / High>
- What could go wrong:  <...>
- Mitigation:           <...>

## Implementation Plan
1. <Step>
2. <Step>
3. <Step>

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual verification on staging
- [ ] <Feature-specific tests>

## Rollback Plan
<How to undo this change if it causes issues>

## Approval
- [ ] Lead Developer: <Name> / <Date>
- [ ] Product Owner: <Name> / <Date> (if Medium+)
- [ ] CAB: <Date> (if High)
```

### 8.2 Emergency Change Record Template

```
EMERGENCY-<YYYY>-<NNN>: <Title>

Incident:       <Link to incident record>
Reported:       <YYYY-MM-DD HH:MM>
Deployed:       <YYYY-MM-DD HH:MM>
Approved by:    <CAB member name>

## What happened
<Root cause of the incident>

## What was changed
<Description of the emergency fix>

## How it was tested
<Testing performed before/after deployment>

## Was rollback needed?
<Yes/No — if yes, describe>

## Retrospective scheduled
<Date, within 48 hours>
```

### 8.3 Post-Implementation Review Template

```
PIR for RFC-<YYYY>-<NNN>: <Title>

Deployed:       <YYYY-MM-DD>
Reviewed:       <YYYY-MM-DD>
Reviewer:       <Name>

## Outcome
<Successful / Partially successful / Failed>

## Deviations from plan
<Any differences from the RFC implementation plan>

## Issues encountered
<Problems during or after deployment>

## Monitoring status
<Alerts configured? Dashboards updated?>

## Documentation updated
- [ ] API.md
- [ ] DATABASE.md
- [ ] TESTING.md
- [ ] TROUBLESHOOTING.md
- [ ] README.md

## Lessons learned
<What would we do differently?>
```

---

## Quick Reference: File Locations by Change Type

| What you want to change | Primary file(s) |
|---|---|
| API endpoint | `backend/src/backend/api/<context>.py`, `backend/src/backend/main.py` |
| API contract docs | `docs/API.md` |
| Data model | `backend/src/backend/db/models.py` |
| Pydantic schemas | `backend/src/backend/db/schemas.py` |
| Database migration | `backend/src/backend/db/migrations/versions/` (auto-generated) |
| Database docs | `docs/DATABASE.md` |
| Backend config | `backend/src/backend/config.py` |
| Auth/role logic | `backend/src/backend/auth.py` |
| Audit logging | `backend/src/backend/services/audit_service.py` |
| Frontend page | `frontend/app/(<group>)/<route>/page.tsx` |
| Shared component | `frontend/components/<name>.tsx` |
| Student sidebar | `frontend/components/portal-nav.tsx` |
| Admin sidebar | `frontend/app/(admin)/layout.tsx` |
| Lecturer sidebar | `frontend/app/(lecturer)/layout.tsx` |
| Route protection | `frontend/middleware.ts` |
| API client helper | `frontend/lib/api-client.ts` |
| Auth config | `frontend/lib/auth.ts` |
| Brand colours | `frontend/app/globals.css` (@theme block) |
| Generated API types | `frontend/lib/api-types.ts` (auto-generated, do not hand-edit) |
| Environment vars | `.env` (runtime), `.env.example` (template) |
| Docker services | `docker/docker-compose.yml` |
| Nginx proxy | `docker/nginx.conf` |
| CI pipeline | `.github/workflows/ci.yml` |
| Backend Dockerfile | `docker/Dockerfile.backend` |
| Frontend Dockerfile | `docker/Dockerfile.frontend` |
| Start/stop scripts | `scripts/start.sh`, `scripts/stop.sh` |
| Seed data | `backend/src/backend/seed.py` |
| Chatbot FAQ | `backend/seed/chatbot_faq.json` (initial), admin UI (ongoing) |
| Test plans | `docs/TESTING.md` |
| Troubleshooting | `docs/TROUBLESHOOTING.md` |
