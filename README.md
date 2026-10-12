# FNU Web Portal MVP

Integrated Student Services portal for Fiji National University: student registration, payments, AI chatbot, staff administration, lecturer interface and a KPI dashboard.

**Stack:** Next.js (App Router, TypeScript) · FastAPI (Python, uv) · PostgreSQL · nginx reverse proxy · Docker Compose

## Security and operations

- **Transport and headers:** nginx with a TLS 1.2/1.3 profile, HSTS preload, CSP and related security headers; `server_tokens off`
- **Authentication:** bcrypt password hashing, JWTs issued by FastAPI inside an httpOnly next-auth session cookie, role-based access control
- **Hardening:** rate limiting, CORS limited to known origins and verbs, non-root containers, startup rejection of placeholder or short secrets
- **Testing:** pytest, Vitest and Playwright suites; OWASP ZAP baseline scans ([scripts/zap_baseline.sh](scripts/zap_baseline.sh)); Locust load tests ([scripts/loadtest.sh](scripts/loadtest.sh))
- **Operations:** automated Postgres backups, uptime monitoring, post-deploy smoke tests, structured JSON logging
- **Runbooks:** [incident response](docs/INCIDENT_RESPONSE.md), [operations](docs/OPS_RUNBOOK.md), [deployment](docs/DEPLOYMENT.md), [security reference](docs/SECURITY.md)

## Getting started

```bash
cp .env.example .env    # fill in values
./scripts/start.sh      # Mac / Linux (scripts\start.bat on Windows)
```

The portal is served at `http://localhost`. Full setup, development and testing instructions are in [docs/README.md](docs/README.md); architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the build plan in [docs/PLAN.md](docs/PLAN.md).
