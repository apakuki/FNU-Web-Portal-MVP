# Deployment Runbook — FNU Web Portal MVP

Production deployment and operations guide. Pair with [SECURITY.md](SECURITY.md) and [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md).

Target environment: single VM (Ubuntu 22.04 LTS or later) running Docker + Docker Compose, with DNS pointing `portal.fnu.ac.fj` at the host.

---

## 1. Server prerequisites

1. Provision a VM with at least 4 vCPU / 8 GB RAM / 40 GB SSD. Attach a second 100 GB disk for Postgres data + backups (or use managed Postgres).
2. Install Docker Engine and Docker Compose plugin following Docker's official apt repository instructions.
3. Open inbound firewall ports 80 (HTTP, for ACME redirect) and 443 (HTTPS). Close 5432 (Postgres) and 8000 (backend) — nginx is the only public surface.
4. Create a non-root user for operating the stack:
   ```bash
   sudo adduser fnuops
   sudo usermod -aG docker fnuops
   ```
5. Clone the repo under `/opt/fnu-portal` (or similar) and set ownership:
   ```bash
   sudo git clone <repo-url> /opt/fnu-portal
   sudo chown -R fnuops:fnuops /opt/fnu-portal
   ```

## 2. DNS and TLS

1. Point the A/AAAA record for `portal.fnu.ac.fj` at the VM's public IP.
2. Add a CAA record restricting certificate issuance to Let's Encrypt:
   ```
   portal.fnu.ac.fj.  CAA 0 issue "letsencrypt.org"
   portal.fnu.ac.fj.  CAA 0 iodef "mailto:security@fnu.ac.fj"
   ```
3. First-run certificate issuance (before starting the production stack):
   ```bash
   cd /opt/fnu-portal/docker
   mkdir -p certs certbot-webroot
   docker run --rm \
     -v "$PWD/certs:/etc/letsencrypt" \
     -v "$PWD/certbot-webroot:/var/www/certbot" \
     -p 80:80 \
     certbot/certbot:latest certonly \
       --standalone \
       -d portal.fnu.ac.fj \
       --email ops@fnu.ac.fj \
       --agree-tos --no-eff-email
   ```
   After issuance, switch to the webroot method (certbot service in `docker-compose.prod.yml` renews via `/var/www/certbot`).
4. Host-side crontab for renewal (once per day, 03:10 UTC):
   ```cron
   10 3 * * * cd /opt/fnu-portal/docker && docker compose -f docker-compose.prod.yml run --rm certbot && docker compose -f docker-compose.prod.yml exec proxy nginx -s reload
   ```

## 3. Secrets

1. Copy the production env template and fill in real values:
   ```bash
   cp /opt/fnu-portal/.env.production.example /opt/fnu-portal/.env.production
   chmod 600 /opt/fnu-portal/.env.production
   ```
2. Generate the required random secrets with the helper script:
   ```bash
   /opt/fnu-portal/scripts/generate_secrets.sh >> /opt/fnu-portal/.env.production.generated
   ```
   Copy the emitted `JWT_SECRET`, `NEXTAUTH_SECRET`, `ID_CARD_SECRET`, and `POSTGRES_PASSWORD` values into `.env.production`, then delete `.env.production.generated`.
3. Populate integration credentials:
   - `BANNER_MODE=live`, `BANNER_API_URL`, `BANNER_API_KEY` (from FNU IT / Ellucian)
   - `PAYMENTS_MODE=live`, `MPAISA_*`, `MYCASH_*` (live merchant credentials from Vodafone Fiji / Digicel)
   - `CHATBOT_MODE=live`, `OPENROUTER_API_KEY`
   - `NOTIFICATIONS_MODE=live`, `SMTP_*`, optionally `SMS_PROVIDER=vodafone` with `SMS_API_URL` + `SMS_API_KEY`
4. Verify no placeholders remain:
   ```bash
   grep -E '(change-me|your-key-here|replace-me)' /opt/fnu-portal/.env.production && echo 'FAIL' || echo 'OK'
   ```
   The backend's `Settings.validate_secrets` will refuse to start if any of `JWT_SECRET`, `ID_CARD_SECRET`, `PAYMENTS_MODE`, or integration credentials are unset or placeholder in `ENVIRONMENT=production`.

## 4. Database

### 4.1 Initial provisioning

1. Start only Postgres first so migrations can be applied before the backend boots:
   ```bash
   cd /opt/fnu-portal/docker
   docker compose -f docker-compose.prod.yml up -d postgres
   ```
2. Create an unprivileged application role (production Postgres must not use a superuser):
   ```bash
   docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
     CREATE ROLE fnu_app LOGIN PASSWORD '<strong-random>';
     GRANT CONNECT ON DATABASE $POSTGRES_DB TO fnu_app;
     GRANT USAGE, CREATE ON SCHEMA public TO fnu_app;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fnu_app;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO fnu_app;
   "
   ```
   Update `.env.production` → `DATABASE_URL` to use `fnu_app` instead of the superuser.
3. Run Alembic migrations through a one-shot backend container (auto-sync):
   ```bash
   docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
   ```
4. Seed KPI definitions and notification templates (idempotent):
   ```bash
   docker compose -f docker-compose.prod.yml run --rm backend python -m src.backend.seed
   ```
   Do **not** seed synthetic users in production — create the first admin user manually (step 6).

### 4.2 Backups

`scripts/backup.sh` wraps `pg_dump` with gzip compression and 14-day retention. Install the host-side crontab (recommended: 02:00 local daily):

```cron
0 2 * * * /opt/fnu-portal/scripts/backup.sh >> /var/log/fnu-backup.log 2>&1
```

Confirm the first backup runs cleanly and is readable:

```bash
/opt/fnu-portal/scripts/backup.sh
ls -lh /opt/fnu-portal/backups/ | tail
```

### 4.3 Restore drill (perform monthly)

See [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) Part 15 section for the full procedure. Summary:

```bash
docker compose -f docker-compose.prod.yml exec postgres createdb -U $POSTGRES_USER fnu_portal_restore_test
gunzip -c backups/fnu_portal_<timestamp>.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T postgres psql -U $POSTGRES_USER -d fnu_portal_restore_test
docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d fnu_portal_restore_test \
  -c "SELECT count(*) FROM users; SELECT count(*) FROM applications;"
docker compose -f docker-compose.prod.yml exec postgres dropdb -U $POSTGRES_USER fnu_portal_restore_test
```

## 5. First start

```bash
cd /opt/fnu-portal/docker
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

All four services (`postgres`, `backend`, `frontend`, `proxy`) should show `running` with healthchecks green within ~60 s. Tail logs:

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=100
```

Exit logs once you see:

```
backend  | INFO:     Application startup complete.
frontend | ready - started server on 0.0.0.0:3000
```

## 6. Create the first admin user

Synthetic seed accounts are disabled in production. Provision the bootstrap admin interactively:

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import asyncio, os, getpass
from src.backend.auth import hash_password
from src.backend.db.session import async_session_factory
from src.backend.db.models import User

async def main():
    email = input('Admin email: ').strip()
    password = getpass.getpass('Admin password: ')
    async with async_session_factory() as db:
        u = User(email=email, role='admin', password_hash=hash_password(password), is_active=True)
        db.add(u); await db.commit()
        print(f'Created admin user id={u.id}')
asyncio.run(main())
"
```

Immediately change this password from the portal UI after the first login.

## 7. Post-deployment verification

Run the production smoke test script from your workstation (not the server):

```bash
PORTAL_URL=https://portal.fnu.ac.fj ./scripts/smoke_test.sh
```

Expected: every check passes. See `scripts/smoke_test.sh` for the list of assertions (TLS, security headers, auth, first login, health endpoint, Swagger docs disabled, HSTS, `/embed/*` CSP).

## 8. Monitoring

### 8.1 Uptime monitoring

Use the sample script under `scripts/uptime_monitor.sh` or plug `https://portal.fnu.ac.fj/api/health` into a third-party monitor (UptimeRobot, StatusCake, Pingdom) with a 60-second cadence. Alert thresholds:

- Two consecutive failures → page the on-call engineer.
- `status != "ok"` (degraded subsystem) → email ops alias.

### 8.2 Log aggregation

Backend emits structured JSON to stdout when `LOG_FORMAT=json` (set in the prod compose file). Ship the container logs with Loki, CloudWatch, or `rsyslog`:

```bash
# Example: forward with Promtail (config not in repo)
docker compose -f docker-compose.prod.yml logs -f backend | <shipper>
```

Search queries:

- Latency outliers: `response_ms > 3000`
- Error rate: `status >= 500`
- Auth anomalies: `path = /api/auth/login AND status = 429`

## 9. Rolling upgrade

Production is deployed as immutable images built from a tagged commit. Rollout:

```bash
cd /opt/fnu-portal
git fetch --tags
git checkout <new-tag>
cd docker
docker compose -f docker-compose.prod.yml pull         # if images are registered
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend
```

Healthcheck recovery is automatic; `proxy` only routes to healthy upstreams.

## 10. Rollback

```bash
cd /opt/fnu-portal
git checkout <previous-tag>
cd docker
docker compose -f docker-compose.prod.yml build backend frontend
docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend
```

If the new release included an Alembic migration, roll it back **first**:

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic downgrade -1
```

Destructive migrations (column drops) should ship behind a two-step deploy — add new column / dual-write / cut over / drop old column — so rollback never requires data recovery. The current migration set is additive only (through `f6a7b8c9d0e1`).

## 11. Shutdown

Graceful:

```bash
cd /opt/fnu-portal/docker
docker compose -f docker-compose.prod.yml down
```

This preserves the `postgres-data` volume. To wipe (DO NOT run in production without a confirmed backup):

```bash
docker compose -f docker-compose.prod.yml down -v
```

## 12. Configuration reference

All environment variables consumed by the stack are listed in [SHARED_CONTEXT.md](../SHARED_CONTEXT.md#environment-variables). Production-required variables (enforced by `Settings.validate_secrets`) are marked "Yes" in the "Required in prod" column.

---

*Owner: ops@fnu.ac.fj. Escalation: see [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md).*
