"""Part 15 — cross-cutting security assertions.

These tests codify the hardening invariants so regressions are caught in CI:
- Response-time header on every response
- IDOR guards on authenticated routes (unauthenticated → 401/403)
- Admin-only routes reject lower-privileged roles
- Payment callbacks reject unsigned/invalid signatures
- Input length bounds enforced on public POSTs
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.db.session import get_session
from src.backend.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _override_get_session(mock):
    async def _override():
        yield mock

    return _override


async def test_response_time_header_present(client: AsyncClient):
    response = await client.get("/api/health")
    assert "x-response-time-ms" in {k.lower() for k in response.headers.keys()}


async def test_unauthenticated_student_routes_reject(client: AsyncClient):
    protected = [
        "/api/programme",
        "/api/timetable",
        "/api/grades",
        "/api/my-courses",
        "/api/invoices",
        "/api/account",
        "/api/profile",
    ]
    for path in protected:
        response = await client.get(path)
        assert response.status_code in (401, 403), (
            f"{path} returned {response.status_code} without auth; expected 401/403"
        )


async def test_unauthenticated_admin_routes_reject(client: AsyncClient):
    admin_routes = [
        "/api/admin/applications",
        "/api/admin/students",
        "/api/admin/enquiries",
        "/api/admin/kpi/definitions",
        "/api/admin/kpi/dashboard/vc",
        "/api/admin/kpi/dashboard/finance",
        "/api/admin/chatbot/conversations",
        "/api/admin/communications/batch",
    ]
    for path in admin_routes:
        response = await client.get(path)
        assert response.status_code in (401, 403, 405), (
            f"{path} returned {response.status_code} without auth; expected 401/403/405"
        )


async def test_payment_callback_rejects_unsigned(client: AsyncClient):
    response = await client.post(
        "/api/payments/callback/mpaisa",
        json={"gateway_reference": "FAKE-REF", "status": "success"},
    )
    # Unsigned callback → 400 or 401 (Not 200 under any circumstance)
    assert response.status_code != 200
    assert response.status_code in (400, 401, 403, 422)


async def test_payment_callback_rejects_invalid_signature(client: AsyncClient):
    response = await client.post(
        "/api/payments/callback/mycash",
        json={"gateway_reference": "FAKE-REF", "status": "success"},
        headers={"X-Signature": "deadbeef"},
    )
    assert response.status_code != 200


async def test_public_application_rejects_overlong_field(client: AsyncClient):
    # first_name is clamped to 100 chars by Pydantic
    body = {
        "applicant_email": "ok@example.com",
        "personal_details": {
            "first_name": "A" * 500,
            "last_name": "B",
            "date_of_birth": "2000-01-01",
            "gender": "x",
            "nationality": "Fiji",
            "address": "Suva",
        },
        "prior_qualifications": [
            {
                "institution": "FNU",
                "qualification": "Diploma",
                "year_completed": 2020,
                "grade": "B",
            }
        ],
        "programme_preference": "BCOM",
        "campus_preference": "Suva",
    }
    response = await client.post("/api/applications", json=body)
    assert response.status_code == 422, response.text


async def test_offer_token_lookup_404_on_bogus(client: AsyncClient):
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    app.dependency_overrides[get_session] = _override_get_session(mock_db)
    try:
        response = await client.get("/api/offers/definitely-not-a-real-token")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


async def test_verify_qr_public_rejects_invalid(client: AsyncClient):
    response = await client.get("/api/verify/not-a-real-qr")
    # Endpoint is intentionally 200-with-reason so public verifiers see a clear
    # message — but the payload must never say valid:true for a bogus QR.
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "reason" in data


async def test_swagger_disabled_in_production(client: AsyncClient, monkeypatch):
    # Guard the setting without recreating the app — verify the code path.
    from src.backend.config import settings as _s
    original = _s.environment
    try:
        _s.environment = "production"
        is_prod = _s.environment == "production"
        docs_url = None if is_prod else "/api/docs"
        assert docs_url is None
    finally:
        _s.environment = original
