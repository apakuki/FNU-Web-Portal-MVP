# Test Report — FNU Web Portal MVP

TOR **D10** deliverable. Summarises every automated test suite, manual test plan, UAT result, and outstanding defect at the point of go-live. Updated live during UAT (Week 7) and signed off by FNU PM + IT lead before production deployment (Week 8).

---

## 1. Executive summary

| Indicator | Target | Status |
|---|---|---|
| Automated backend unit/integration tests pass | 100% | *run `scripts/test_report.sh` to refresh* |
| Automated frontend Vitest tests pass | 100% | *run `scripts/test_report.sh` to refresh* |
| Backend coverage | ≥80% | *as above* |
| Frontend coverage | ≥80% | *as above* |
| Axe-core critical/serious violations | 0 | *as above* |
| Load test — 500 users, p95 < 3 s | PASS | *staging run; reference `reports/locust-*`* |
| OWASP ZAP baseline — high-severity findings | 0 | *staging run; reference `reports/zap-baseline-*.html`* |
| UAT scenarios executed | 13/13 | *updated during UAT* |
| Blocker bugs open | 0 | *updated during UAT* |
| Major bugs open | 0 or signed-off deferrals | *updated during UAT* |
| Chatbot acceptance queries passing | 20/20 | *per UAT scenario H* |
| Payment gateway confirmed sandbox transactions | ≥1 per gateway | *per UAT scenario G* |

Run `scripts/test_report.sh` against staging to regenerate the numeric values and paste the output below.

## 2. Automated test suite results

### 2.1 Backend (pytest)

Run:

```bash
cd backend
KPI_SCHEDULER_ENABLED=false .venv/bin/python -m pytest tests/ -v --tb=short
```

Covers (updated through Part 16):

- Authentication, JWT, session revocation, rate limits, lockout
- Database models, migrations (up/down round-trip)
- Banner mock adapter, cache TTL, factory guards, audited writes, rate limiter
- Applications, documents, offers, bulk actions, PDF generator
- Course registration, prereq checks, clash detection, invoice generation, GPA
- Payments — stub/live adapters, HMAC signatures, idempotency, payment plans, reconciliation
- Profile, ID card signing + verification, photo processing
- Chatbot service, FAQ retrieval, escalation, admin CRUD
- Admin students + overrides + enquiries
- Lecturer rosters, grade workflow, Banner write-through
- KPI computation, traffic-light, period filters, RBAC per role
- Security: response-time header, auth-bypass, unsigned callbacks, IDOR guards, token-bucket rate limit

### 2.2 Frontend (Vitest)

```bash
cd frontend
npx vitest run
```

Covers components (layout, portal nav, outstanding-fees banner, chatbot widget), the application form wizard, and SSR health check.

### 2.3 Type check + lint

```bash
cd backend && .venv/bin/ruff check src/ tests/ && .venv/bin/mypy src/
cd frontend && npx tsc --noEmit && npx eslint .
```

### 2.4 End-to-end (Playwright)

```bash
cd frontend
npm run e2e              # full matrix
npm run a11y             # axe-core across 5 browser projects
```

Projects: chromium, firefox, webkit, mobile-chrome, mobile-safari.

### 2.5 Load test (staging)

```bash
USERS=500 P95_MS=3000 RUN_TIME=5m HOST=https://staging.portal.fnu.ac.fj \
  ./scripts/loadtest.sh
```

Output under `reports/locust-<timestamp>/`. Attach the HTML report + PASS/FAIL result.

### 2.6 OWASP ZAP baseline (staging)

```bash
HOST=https://staging.portal.fnu.ac.fj ./scripts/zap_baseline.sh
```

Output under `reports/zap-baseline-<timestamp>.html`. Attach the HTML report + the list of accepted medium/low findings with rationale (filed in [SECURITY.md](SECURITY.md)).

## 3. Manual test plans

Every build part has a detailed manual test plan in [TESTING.md](TESTING.md):

- Part 2 — Scaffolding
- Part 3 — Database + authentication
- Part 4 — Portal shell + login
- Part 5 — Banner integration
- Part 6 — New-student application
- Part 7 — Course registration + timetable + invoicing
- Part 8 — Payment gateway
- Part 9 — AI chatbot backend
- Part 10 — Chatbot UI + admin screens + embed
- Part 11 — Profile + student ID + notifications
- Part 12 — Staff admin panel
- Part 13 — Lecturer interface
- Part 14 — KPI dashboard
- Part 15 — Non-functional hardening
- Part 16 — UAT + deployment (this document's scope)

## 4. UAT log

See [UAT_PLAN.md](UAT_PLAN.md) for the scenario catalogue. Status updates recorded daily during UAT week.

| Scenario | Facilitator | Participant | Status | Notes |
|---|---|---|---|---|
| A — Application submission | | | | |
| B — Application review & offer | | | | |
| C — Offer acceptance | | | | |
| D — First login + portal tour | | | | |
| E — Course registration | | | | |
| F — Timetable / grades / my-courses | | | | |
| G — Payments | | | | |
| H — AI chatbot (20 queries + escalate) | | | | |
| I — Lecturer workflow | | | | |
| J — Staff admin | | | | |
| K — KPI dashboards | | | | |
| L — Communications | | | | |
| M — Non-functional | | | | |

## 5. Bug log

| ID | Scenario | Severity | Title | Status | Owner | Fix commit |
|---|---|---|---|---|---|---|
| *— populated during UAT —* | | | | | | |

Severity legend:

- **Blocker** — go-live cannot proceed until fixed.
- **Major** — core workflow broken or meaningfully degraded; fix preferred, deferral requires FNU PM sign-off.
- **Minor** — workaround available; fix can be post-launch.
- **Cosmetic** — UI polish; defer to backlog.

## 6. Deferred items (post-launch backlog)

These were descoped from the MVP with FNU PM agreement; captured here for Phase 2:

- **TLS certificate pinning** on gateway API calls — depends on live merchant contracts and provider support.
- **Subresource Integrity** hash on the standalone embeddable chatbot bundle — requires release pipeline hashing static assets.
- **Drill-down** beyond institution + college/staff scoping in the KPI dashboard — full four-level drill-down (institution → college → function → individual) deferred.
- **Exports audit-logged** on the admin student search — exports currently landed with KPI work in Part 14; student-search export logging is a small follow-up.
- **CSV/Excel export** from admin student search — captured as a Phase 2 item.

Anything closed in UAT that turns into a deferral rather than a fix gets added to this section with the PM-signed rationale.

## 7. Sign-off

At UAT exit, the following sign-offs are collected:

| Role | Name | Signed (date) |
|---|---|---|
| FNU Project Manager | | |
| FNU IT Director | | |
| FNU Registry lead | | |
| FNU Finance lead | | |
| Build team lead | | |

With sign-off captured above, the system proceeds to production deployment per [DEPLOYMENT.md](DEPLOYMENT.md).

---

*Template version 1.0 — Part 16. Populate during UAT week (early May 2026) and archive the signed copy in the project artifact store.*
