# Backend (FastAPI)

## Stack

- Python 3.12+, FastAPI, Pydantic v2
- `uv` as the package manager
- SQLAlchemy 2.x (async) + Alembic for PostgreSQL
- `python-oracledb` for Banner (via `banner_client` module)
- OpenRouter for AI chatbot (key: `OPENROUTER_API_KEY` in `.env`)
- WeasyPrint for PDF generation (offer letters, invoices)
- APScheduler for background jobs
- bcrypt for password hashing, PyJWT for JWT tokens
- pytest + pytest-asyncio for tests

## Directory Structure

```
backend/
  src/backend/
    api/                  # Route handlers grouped by bounded context
      auth.py             # /api/auth/*
      applications.py     # /api/applications/*
      registration.py     # /api/registration/*
      payments.py         # /api/payments/*
      chatbot.py          # /api/chat/*
      profile.py          # /api/profile/*
      timetable.py        # /api/timetable/*
      grades.py           # /api/grades/*
      invoices.py         # /api/invoices/*
      account.py          # /api/account/*
      id_card.py          # /api/id-card/*
      admin/              # /api/admin/* routes
        applications.py
        students.py
        enquiries.py
        communications.py
        chatbot.py
        kpi.py
      lecturer/           # /api/lecturer/* routes
        rosters.py
        grades.py
    banner/               # Banner client module
      client.py           # Typed read/write functions
      mock_adapter.py     # Mock adapter for local dev and tests
      cache.py            # In-memory cache with 15-min TTL
    db/
      models.py           # SQLAlchemy models
      schemas.py          # Pydantic request/response schemas
      session.py          # Async session factory
      migrations/         # Alembic migrations
    services/             # Business logic
      application_service.py
      registration_service.py
      payment_service.py
      chatbot_service.py
      kpi_service.py
      notification_service.py
      pdf_service.py
    auth.py               # JWT helpers, password hashing, require_role dependency
    config.py             # Settings loaded from environment
    main.py               # FastAPI app factory
  tests/
  seed/                   # Synthetic data JSON files
  alembic.ini
  pyproject.toml
```

## Conventions

- Every route has a Pydantic request model and response model. No raw dicts.
- Role-based access control is enforced via the shared `require_role()` FastAPI dependency. Never check roles ad-hoc in route handlers.
- All Banner access goes through the `banner_client` module. No direct Oracle connections elsewhere.
- Audit trail writes are fire-and-forget background tasks. Never block the user response.
- The mock Banner adapter implements the same interface as the real client. All other parts develop against the mock until live credentials arrive.
- Secrets are loaded from environment variables via `config.py`. Nothing hardcoded.
- Use parameterised queries only (SQLAlchemy ORM). No raw SQL string interpolation.

## Banner Client

The `banner/` package is the single gateway to Ellucian Banner:

**Read functions**: `get_programmes`, `get_courses`, `get_offerings`, `get_fee_schedule`, `get_student`, `get_invoices`, `get_class_roster`

**Write functions**: `create_student`, `register_course`, `submit_grade`, `create_invoice`

**Cache**: in-memory, 15-minute TTL for programmes, courses, fee schedules.

**Mock adapter**: returns seeded data, honours the same interface. Selected via `BANNER_MODE=mock` environment variable.

## Testing

- pytest + pytest-asyncio. Minimum 80% unit test coverage.
- Every endpoint: at least one happy-path and one auth-failure test.
- Every role-based route: wrong role returns 403.
- Migration up/down round-trip test.
- Banner mock adapter used in all unit/integration tests.

## Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Secret for HS256 JWT signing |
| `OPENROUTER_API_KEY` | AI chatbot LLM calls |
| `BANNER_MODE` | `mock` or `live` |
| `BANNER_DSN` | Oracle connection string (when live) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | Email sender |
| `MPAISA_MERCHANT_ID`, `MPAISA_SECRET` | M-PAiSA sandbox |
| `MYCASH_MERCHANT_ID`, `MYCASH_SECRET` | MyCash sandbox |
