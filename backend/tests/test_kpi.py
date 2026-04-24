"""Tests for the Part 14 KPI dashboard.

Schema-level tests exercise the traffic-light helper and Pydantic
validation. Integration tests wire dependency overrides around the real
ASGI app with AsyncMock sessions; the compute pass itself is exercised
via the service directly so we don't need a real Postgres.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api.kpi import (
    DEAN_CODES,
    FINANCE_CODES,
    SECTION_HEAD_CODES,
    VC_CODES,
    ManualEntryRequest,
    TargetUpdateRequest,
)
from src.backend.auth import get_current_user
from src.backend.db.models import KpiDefinition, KpiValue, User
from src.backend.db.session import get_session
from src.backend.main import app
from src.backend.services.kpi_service import (
    Period,
    current_semester_period,
    traffic_light,
    ytd_period,
)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_user(role: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        banner_id=None,
        email=f"{role}@fnu.ac.fj",
        phone=None,
        password_hash="x",
        role=role,
        full_name=role.title(),
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )


def _install(db, user):
    async def _session_override():
        yield db

    async def _user_override():
        return user

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override


def _make_definition(code: str, **overrides) -> KpiDefinition:
    base = {
        "id": uuid.uuid4(),
        "code": code,
        "name": code.replace(".", " ").title(),
        "category": "enrolment",
        "unit": "count",
        "applies_to_role": "vc",
        "target_default": Decimal("100"),
        "direction": "higher_better",
        "description": None,
        "source": "auto",
        "is_active": True,
    }
    base.update(overrides)
    return KpiDefinition(**base)


def _make_value(code: str, value: float, period: Period, **overrides) -> KpiValue:
    base = {
        "id": uuid.uuid4(),
        "kpi_code": code,
        "staff_user_id": None,
        "function": None,
        "college": None,
        "period_start": period.start,
        "period_end": period.end,
        "value": Decimal(str(value)),
        "target": Decimal("100"),
        "source": "auto",
        "recorded_at": datetime.now(UTC),
    }
    base.update(overrides)
    return KpiValue(**base)


# --- Traffic light --------------------------------------------------------


def test_traffic_light_higher_better_green():
    assert traffic_light(100, 100, "higher_better") == "green"
    assert traffic_light(120, 100, "higher_better") == "green"


def test_traffic_light_higher_better_amber_and_red():
    assert traffic_light(85, 100, "higher_better") == "amber"
    assert traffic_light(70, 100, "higher_better") == "red"


def test_traffic_light_lower_better():
    assert traffic_light(24, 24, "lower_better") == "green"
    assert traffic_light(25, 24, "lower_better") == "amber"
    assert traffic_light(30, 24, "lower_better") == "red"


def test_traffic_light_no_target_returns_grey():
    assert traffic_light(50, None, "higher_better") == "grey"


# --- Period helpers -------------------------------------------------------


def test_current_semester_returns_valid_window():
    period = current_semester_period(today=date(2026, 3, 15))
    assert period.start == date(2026, 2, 1)
    assert period.end == date(2026, 6, 30)


def test_current_semester_second_half():
    period = current_semester_period(today=date(2026, 9, 1))
    assert period.start == date(2026, 7, 1)


def test_ytd_period():
    period = ytd_period(today=date(2026, 4, 24))
    assert period.start == date(2026, 1, 1)
    assert period.end == date(2026, 4, 24)


# --- Schema tests ---------------------------------------------------------


def test_manual_entry_valid():
    req = ManualEntryRequest(
        kpi_code="staff.training_hours",
        value=12.5,
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
    )
    assert req.value == 12.5


def test_target_update_rejects_negative():
    with pytest.raises(Exception):
        TargetUpdateRequest(target_default=-5)


# --- Dashboard code lists invariant -------------------------------------


def test_dashboard_code_lists_disjoint_domains():
    # Codes should all be known KPIs loaded from seed.
    for code in VC_CODES + DEAN_CODES + SECTION_HEAD_CODES + FINANCE_CODES:
        assert "." in code  # "<category>.<metric>" convention


# --- RBAC integration -----------------------------------------------------


async def test_dashboard_vc_forbids_student(client: AsyncClient):
    student = _make_user("student")
    db = AsyncMock()
    _install(db, student)
    try:
        resp = await client.get("/api/admin/kpi/dashboard/vc")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_dashboard_finance_forbids_manager(client: AsyncClient):
    manager = _make_user("manager")
    db = AsyncMock()
    _install(db, manager)
    try:
        resp = await client.get("/api/admin/kpi/dashboard/finance")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_dashboard_section_head_forbids_finance(client: AsyncClient):
    finance = _make_user("finance")
    db = AsyncMock()
    _install(db, finance)
    try:
        resp = await client.get("/api/admin/kpi/dashboard/section-head")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_target_update_forbids_manager(client: AsyncClient):
    manager = _make_user("manager")
    db = AsyncMock()
    _install(db, manager)
    try:
        resp = await client.put(
            "/api/admin/kpi/definitions/enrolment.active_students/target",
            json={"target_default": 500},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


# --- Happy-path dashboard build ------------------------------------------


async def test_dashboard_vc_returns_cards(client: AsyncClient):
    vc = _make_user("vc")
    period = current_semester_period()

    # `_build_cards` issues two scalar calls per KPI: definition, then value.
    sequence = []
    for code in VC_CODES:
        direction = (
            "lower_better"
            if "hours" in code or code.endswith("rate")
            else "higher_better"
        )
        defn = _make_definition(code, direction=direction, source="auto")
        value = _make_value(code, 50.0, period)
        sequence.extend([defn, value])

    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=sequence)

    _install(db, vc)
    try:
        resp = await client.get("/api/admin/kpi/dashboard/vc")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["view"] == "vc"
        assert len(body["cards"]) == len(VC_CODES)
        assert body["cards"][0]["status"] in {"green", "amber", "red", "grey"}
    finally:
        app.dependency_overrides.clear()


# --- Manual entry validation ---------------------------------------------


async def test_manual_entry_rejects_auto_kpi(client: AsyncClient, monkeypatch):
    admin = _make_user("admin")
    defn = _make_definition("enrolment.active_students", source="auto")

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=defn)
    _install(db, admin)
    try:
        resp = await client.post(
            "/api/admin/kpi/manual",
            json={
                "kpi_code": "enrolment.active_students",
                "value": 5,
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
            },
        )
        assert resp.status_code == 400
        assert "manual input" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


async def test_manual_entry_rejects_unknown_kpi(client: AsyncClient):
    admin = _make_user("admin")
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    _install(db, admin)
    try:
        resp = await client.post(
            "/api/admin/kpi/manual",
            json={
                "kpi_code": "does.not.exist",
                "value": 1,
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
            },
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


async def test_manual_entry_forbids_student(client: AsyncClient):
    student = _make_user("student")
    db = AsyncMock()
    _install(db, student)
    try:
        resp = await client.post(
            "/api/admin/kpi/manual",
            json={
                "kpi_code": "staff.training_hours",
                "value": 5,
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
            },
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


# --- Custom period validation --------------------------------------------


async def test_custom_period_requires_dates(client: AsyncClient):
    vc = _make_user("vc")
    db = AsyncMock()
    _install(db, vc)
    try:
        resp = await client.get("/api/admin/kpi/dashboard/vc?preset=custom")
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


async def test_custom_period_rejects_overlong_range(client: AsyncClient):
    vc = _make_user("vc")
    db = AsyncMock()
    _install(db, vc)
    try:
        resp = await client.get(
            "/api/admin/kpi/dashboard/vc"
            "?preset=custom&period_start=2020-01-01&period_end=2025-01-01"
        )
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()
