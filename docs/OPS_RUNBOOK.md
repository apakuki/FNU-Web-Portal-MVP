# Ops Runbook — FNU Web Portal MVP

Day-to-day operational tasks and diagnostics. For initial deployment see [DEPLOYMENT.md](DEPLOYMENT.md); for outage response see [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md).

---

## Daily checks

| Check | How | Expected |
|---|---|---|
| Portal reachable | `curl -I https://portal.fnu.ac.fj/` | `HTTP/2 200` |
| Health endpoint | `curl -s https://portal.fnu.ac.fj/api/health \| jq .` | `status: "ok"` across postgres, banner, scheduler |
| Backup ran | `ls -lh /opt/fnu-portal/backups/ \| tail -1` | File from last night, >10 KB |
| Error rate | Log query `status >= 500` last 24 h | 0 (investigate anything non-zero) |
| Disk space | `df -h` | <80% on all mounts |
| Certificate expiry | `openssl s_client -connect portal.fnu.ac.fj:443 -servername portal.fnu.ac.fj </dev/null 2>/dev/null \| openssl x509 -noout -dates` | >14 days until `notAfter` |

## Common diagnostics

### Check the running stack

```bash
cd /opt/fnu-portal/docker
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 -f backend
```

### Connect to Postgres

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d fnu_portal
```

Useful queries:

```sql
-- Active sessions
SELECT count(*) FROM sessions WHERE expires_at > now();

-- Recent login failures
SELECT email, failed_login_attempts, locked_until FROM users
 WHERE failed_login_attempts > 0 ORDER BY last_login_at DESC NULLS LAST LIMIT 20;

-- Pending applications
SELECT status, count(*) FROM applications GROUP BY status;

-- Today's payments
SELECT provider, status, count(*), sum(amount_cents)/100.0 AS total_fjd
  FROM payment_attempts
 WHERE created_at > current_date
 GROUP BY provider, status;

-- Recent audit activity
SELECT actor_user_id, action, target_type, target_id, occurred_at
  FROM audit_log
 ORDER BY occurred_at DESC LIMIT 50;
```

### Inspect a specific user

```sql
SELECT id, email, role, is_active, created_at, last_login_at
  FROM users WHERE email = '<email>';

SELECT action, target_type, target_id, occurred_at, ip_address
  FROM audit_log WHERE actor_user_id = '<user_id>'
 ORDER BY occurred_at DESC LIMIT 100;
```

### Clear a stuck scheduler job

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
from src.backend.scheduler import shutdown_scheduler, start_scheduler
shutdown_scheduler(); start_scheduler()
"
```

Or simply restart the backend container — the scheduler starts fresh in the `lifespan` hook.

### Trigger a KPI recompute on demand

```bash
curl -s -X POST https://portal.fnu.ac.fj/api/admin/kpi/compute \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"preset":"current_semester"}'
```

### Regenerate an application's offer letter

Applications land in `applications` and offers in `offers`. If an offer PDF email bounced, re-issue:

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import asyncio
from src.backend.api.applications import issue_offer
# ... call into the domain service; see docs/API.md for the HTTP surface
"
```

Prefer the HTTP surface where possible — it logs to `audit_log` automatically.

## Scheduled maintenance

| Task | Cadence | Command |
|---|---|---|
| Database backup | Daily 02:00 FJT | `scripts/backup.sh` (cron) |
| Certificate renewal | Daily 03:10 UTC | `docker compose … run --rm certbot && nginx reload` (cron) |
| Restore drill | Monthly | See DEPLOYMENT.md §4.3 |
| Dependency audit | Weekly | `cd backend && uv pip list --outdated`; `cd frontend && npm audit` |
| Full load test vs staging | Quarterly | `USERS=500 P95_MS=3000 RUN_TIME=5m HOST=<staging> ./scripts/loadtest.sh` |
| OWASP ZAP baseline | Monthly | `./scripts/zap_baseline.sh` (against staging) |

## User-account operations

### Unlock a locked account

```sql
UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE email = '<email>';
```

### Reset a user's password (admin)

Best done via the password-reset flow — users click the link in email. For emergency admin reset:

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import asyncio
from src.backend.auth import hash_password
from src.backend.db.session import async_session_factory
from src.backend.db.models import User
from sqlalchemy import select

async def main():
    email = '<email>'; new = '<new-password>'
    async with async_session_factory() as db:
        u = (await db.execute(select(User).where(User.email == email))).scalar_one()
        u.password_hash = hash_password(new); await db.commit()
        print('ok')
asyncio.run(main())
"
```

Always write a row to `audit_log` documenting the reason — or better, do this through the normal password reset UI so the audit trail is automatic.

### Deactivate a user (leaving staff, graduated student)

```sql
UPDATE users SET is_active = false WHERE email = '<email>';
DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE email = '<email>');
```

## Release procedure

See [DEPLOYMENT.md §9 (rolling upgrade)](DEPLOYMENT.md) and §10 (rollback). Summary:

1. Tag the release: `git tag -a v0.x.y -m "..."; git push --tags`
2. SSH to the prod host, checkout the tag, rebuild.
3. Run the smoke test: `PORTAL_URL=https://portal.fnu.ac.fj ./scripts/smoke_test.sh`
4. If the smoke test fails, roll back immediately (do not debug in-place on production unless it is unrecoverable).

---

*Last updated: Part 16.*
