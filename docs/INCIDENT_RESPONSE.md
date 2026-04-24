# Incident Response — FNU Web Portal MVP

The playbook for handling security and availability incidents after launch. Pair with [DEPLOYMENT.md](DEPLOYMENT.md), [SECURITY.md](SECURITY.md), and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Severity levels

| Level | Definition | Response time | Example |
|---|---|---|---|
| **SEV1** | Production outage or confirmed security breach | Page within 15 min, mitigate within 1 h | Portal down; credentials leaked; payment callback fraud |
| **SEV2** | Major feature broken for >10% of users; data integrity risk | Page within 1 h, mitigate within 4 h | Login intermittently fails; grade submission stuck |
| **SEV3** | Minor feature broken; workaround available | Ticket within 4 business hours | Export CSV malformed for one role |
| **SEV4** | Cosmetic or informational | Backlog | Typo; stale help text |

## Roles during an incident

| Role | Responsibility |
|---|---|
| **Incident commander** | Owns the response. Coordinates, sets cadence, declares SEV level, closes the incident. |
| **On-call engineer** | Technical response. Runs mitigations, gathers evidence. Does not talk to stakeholders. |
| **Comms lead** | Updates FNU IT leadership, students, and staff via email / portal banner. |
| **Scribe** | Maintains the incident timeline in the ticket. |

Single person can hold multiple roles on a small team — but the incident commander must always be named aloud at the start of the call.

## Contact list

| Contact | Channel |
|---|---|
| On-call rotation | ops@fnu.ac.fj · PagerDuty schedule `fnu-portal-oncall` |
| FNU IT lead | it-director@fnu.ac.fj · +679 xxxx xxxx |
| Ellucian Banner support | banner-support@ellucian.com · 24h ticket line |
| Vodafone Fiji (M-PAiSA) | mpaisa-merchant@vodafone.com.fj |
| Digicel (MyCash) | mycash-support@digicel.com.fj |
| OpenRouter | support@openrouter.ai |
| Certificate authority | Let's Encrypt community forum (non-urgent) |
| Hosting provider | Per provider contract |

## SEV1 response — first 15 minutes

1. **Declare**: On-call engineer opens a new incident ticket titled `INC-YYYYMMDD-<slug>` and posts the initial situation report in the ops channel. Name the incident commander.
2. **Confirm scope**: Hit `/api/health`, run `scripts/smoke_test.sh`, check uptime monitor history, query recent error rate from logs.
3. **Page stakeholders**: Comms lead sends a holding email to FNU IT leadership with "We are investigating a disruption on portal.fnu.ac.fj. Next update in 30 minutes."
4. **Preserve evidence**: For suspected breach, do **not** restart containers until logs are captured:
   ```bash
   docker compose -f docker/docker-compose.prod.yml logs --since 2h > /var/log/fnu-incident-$INC_ID.log
   ```
5. **Mitigate**, see the runbooks below.

---

## Runbook: credential compromise (SEV1)

Symptoms: leaked `JWT_SECRET`, `ID_CARD_SECRET`, `NEXTAUTH_SECRET`, database password, Banner API key, or payment gateway HMAC secret.

1. **Revoke active sessions**:
   ```bash
   docker compose -f docker/docker-compose.prod.yml exec postgres \
     psql -U $POSTGRES_USER -d fnu_portal -c "DELETE FROM sessions;"
   ```
2. **Rotate the JWT/NextAuth secrets** in `.env.production`:
   ```bash
   ./scripts/generate_secrets.sh >> .env.production.generated
   # manually swap into .env.production
   ```
3. **Restart backend + frontend** to pick up new secrets:
   ```bash
   cd docker && docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend
   ```
4. **If the ID card secret was leaked**, QR codes already issued are trivially forgeable. Invalidate all cards and notify students — the next login will re-issue a new signed card automatically. No DB change is required; `sign_id_card` uses the new secret on next request.
5. **If the Banner API key was leaked**, request rotation from Ellucian support immediately. Update `BANNER_API_KEY` in `.env.production` and restart the backend.
6. **If an M-PAiSA or MyCash secret was leaked**, rotate with the respective provider, and audit `payment_attempts` for any transaction in the leak window:
   ```sql
   SELECT id, user_id, amount_cents, gateway_reference, status, created_at
     FROM payment_attempts
    WHERE created_at > '<leak_window_start>' AND provider = '<mpaisa|mycash>'
    ORDER BY created_at DESC;
   ```
7. **Audit log check** — look for suspicious admin actions:
   ```sql
   SELECT action, actor_user_id, ip_address, occurred_at
     FROM audit_log
    WHERE occurred_at > '<leak_window_start>'
    ORDER BY occurred_at DESC LIMIT 200;
   ```
8. **File post-mortem** within 48 h. Include: leak source, scope, remediation, detection improvements.

## Runbook: portal unreachable (SEV1)

1. **Confirm at the edge**:
   ```bash
   curl -I https://portal.fnu.ac.fj/
   ```
2. **Check proxy health**:
   ```bash
   ssh fnuops@<server>
   docker compose -f /opt/fnu-portal/docker/docker-compose.prod.yml ps
   ```
3. **If `proxy` is down**: restart it (`docker compose up -d --no-deps proxy`). If restart fails, inspect the config (`docker compose exec proxy nginx -t`) — a bad config edit is the usual cause.
4. **If backend is unhealthy**: check `/api/health`, tail logs, look for OOM kills (`dmesg | tail`). Restart with `docker compose restart backend`.
5. **If Postgres is unreachable**: check disk space (`df -h`), connection count (`SELECT count(*) FROM pg_stat_activity;`), and archive log size. If Postgres itself is healthy but connections are exhausted, restart the backend.
6. **If certificate expired**: run the certbot flow from [DEPLOYMENT.md §2](DEPLOYMENT.md) and reload nginx.
7. **Fall back to status page**: update FNU main site with "Portal temporarily unavailable" banner pointing to estimated recovery time.

## Runbook: data corruption or accidental mass delete (SEV1)

1. **Freeze writes**: Put the backend into read-only mode by scaling replicas to zero, or set `DATABASE_URL` to a read-only role and restart backend. This prevents further damage while you investigate.
2. **Identify the window** from `audit_log` — find the actor, action, and timestamp of the offending change.
3. **Restore**:
   ```bash
   # Pick the most recent backup before the incident
   gunzip -c /opt/fnu-portal/backups/fnu_portal_<ts>.sql.gz \
     | docker compose -f docker/docker-compose.prod.yml exec -T postgres \
         psql -U $POSTGRES_USER -d fnu_portal_restore
   # Diff the affected tables, cherry-pick recoverable rows back into production
   ```
4. **Do not overwrite production from backup blindly** unless the data loss is total and recent (<1 h since last backup). Prefer row-level recovery.
5. Post-mortem required.

## Runbook: payment gateway callback fraud (SEV1/SEV2)

Symptoms: `payment_attempts` rows with status `paid` but no corresponding ledger entry in M-PAiSA / MyCash merchant portal; or HMAC verification passing with rotated secrets (indicates leaked secret).

1. **Pause payment initiation** — set `PAYMENTS_MODE=stub` temporarily is NOT correct in prod (the validator rejects it). Instead, temporarily revoke payment routes at the proxy:
   ```nginx
   location /api/payments/initiate { return 503; }
   ```
   Reload nginx.
2. **Rotate HMAC secrets** with the gateway provider (see credential-compromise runbook).
3. **Reconcile** against the merchant portal CSV and mark suspicious rows as `disputed`:
   ```sql
   UPDATE payment_attempts SET status = 'disputed', updated_at = now()
    WHERE gateway_reference IN ('...');
   ```
4. Notify finance; trigger the audit trail review.

## Runbook: credential stuffing / brute force (SEV2)

Symptoms: spike in `/api/auth/login` 401s, or lockouts tripping for many students in a short window.

1. The slowapi rate-limiter caps logins at 10/min per IP, and accounts lock after 5 failures. If the attack is distributed across IPs, tighten CORS / proxy:
   ```nginx
   limit_req_zone $binary_remote_addr zone=login:10m rate=5r/s;
   location = /api/auth/login { limit_req zone=login burst=10 nodelay; ... }
   ```
2. For identified attacker IPs, add `deny <ip>;` to nginx.
3. Notify affected students if their accounts were locked — a portal banner "We detected unusual sign-in activity" is usually sufficient.

## Runbook: chatbot generating inappropriate content (SEV2)

1. Disable the chatbot without code change:
   ```bash
   # In .env.production
   CHATBOT_MODE=stub
   ```
   Restart backend. The stub returns canned FAQ answers only.
2. Review `chatbot_conversations` for the offending conversation; capture the prompt + reply.
3. Tighten the system prompt in `services/chatbot_service.py` or the FAQ corpus; ship a patch.
4. Escalate to OpenRouter support if the output suggests a provider-side issue.

---

## Post-incident

1. Within 48 h, incident commander publishes a post-mortem in `docs/incidents/INC-YYYYMMDD-<slug>.md` containing:
   - Summary (1 paragraph)
   - Timeline (UTC)
   - Impact (users affected, data affected, duration)
   - Root cause (technical)
   - Contributing factors (process, missing monitoring, etc.)
   - Remediations — each must be a concrete action item with owner and ETA
2. Remediations tracked to completion in the project tracker; do not close the incident ticket until all SEV1/SEV2 action items ship.
3. If the incident involved a data breach affecting students, legal notification per Fiji Data Protection obligations — escalate to FNU legal within 24 h of confirmation.

---

*Last updated: Part 16. Owner: ops@fnu.ac.fj.*
