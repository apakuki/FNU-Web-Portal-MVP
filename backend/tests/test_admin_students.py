"""Tests for the Part 12 admin students + overrides API.

Schema-level assertions use Pydantic directly (no DB). Integration tests
wire dependency overrides around the real ASGI app with AsyncMock sessions
and a stub banner client so the search / detail / override paths can be
exercised without Postgres or Banner.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api import admin_students as admin_students_api
from src.backend.api.admin_students import (
    OVERRIDE_TYPES,
    OverrideRequest,
    _audit_to_override,
)
from src.backend.auth import get_current_user
from src.backend.db.models import AuditLog, User
from src.backend.db.session import get_session
from src.backend.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_admin() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        banner_id=None,
        email="admin@fnu.ac.fj",
        phone=None,
        password_hash="x",
        role="admin",
        full_name="System Administrator",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )


def _make_student(
    *, email: str = "student@fnu.ac.fj", full_name: str = "Test Student"
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        banner_id="S00012345",
        email=email,
        phone="+6799991001",
        password_hash="x",
        role="student",
        full_name=full_name,
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


# --- Schema tests ---------------------------------------------------------


def test_override_request_valid():
    req = OverrideRequest(
        override_type="prereq_waiver",
        reason="Student completed equivalent at UniFiji",
        subject="ACC201",
    )
    assert req.override_type == "prereq_waiver"


def test_override_request_reason_too_short():
    with pytest.raises(Exception):
        OverrideRequest(override_type="prereq_waiver", reason="short")


def test_override_request_unknown_type():
    with pytest.raises(Exception):
        OverrideRequest(override_type="made_up", reason="Long enough reason here")


def test_override_types_set_complete():
    assert OVERRIDE_TYPES == {"prereq_waiver", "late_registration", "overload"}


def test_audit_to_override_unpacks_payload():
    row = AuditLog(
        id=42,
        actor_user_id=uuid.uuid4(),
        action="override.prereq_waiver",
        target_type="student_override",
        target_id=str(uuid.uuid4()),
        before=None,
        after={
            "override_type": "prereq_waiver",
            "subject": "ACC201",
            "reason": "Equivalent credit",
        },
        reason="Equivalent credit",
        ip_address="127.0.0.1",
        occurred_at=datetime.now(UTC),
    )
    out = _audit_to_override(row)
    assert out.override_type == "prereq_waiver"
    assert out.subject == "ACC201"
    assert out.reason == "Equivalent credit"


# --- Integration tests ----------------------------------------------------


async def test_list_students_requires_staff_or_admin(client: AsyncClient):
    # Unauthenticated -> 401/403
    resp = await client.get("/api/admin/students")
    assert resp.status_code in (401, 403)


async def test_list_students_forbids_student_role(client: AsyncClient):
    student = _make_student()
    db = AsyncMock()
    _install(db, student)
    try:
        resp = await client.get("/api/admin/students")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_list_students_returns_items(client: AsyncClient, monkeypatch):
    admin = _make_admin()
    students = [
        _make_student(email="s1@fnu.ac.fj", full_name="Alpha One"),
        _make_student(email="s2@fnu.ac.fj", full_name="Beta Two"),
    ]
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=len(students))

    scalars_result = MagicMock()
    scalars_result.all.return_value = students
    db.scalars = AsyncMock(return_value=scalars_result)

    # Fake Banner client returns None for every student.
    banner = MagicMock()
    banner.get_student = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_students_api, "get_banner_client", lambda: banner)

    _install(db, admin)
    try:
        resp = await client.get("/api/admin/students")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 2
        assert {i["email"] for i in body["items"]} == {"s1@fnu.ac.fj", "s2@fnu.ac.fj"}
    finally:
        app.dependency_overrides.clear()


async def test_create_override_rejects_short_reason(client: AsyncClient):
    admin = _make_admin()
    db = AsyncMock()
    _install(db, admin)
    try:
        resp = await client.post(
            f"/api/admin/students/{uuid.uuid4()}/overrides",
            json={"override_type": "prereq_waiver", "reason": "short"},
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_create_override_happy_path_writes_audit(
    client: AsyncClient, monkeypatch
):
    admin = _make_admin()
    student = _make_student()

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=student)

    added: list[AuditLog] = []

    def _add(obj):
        # Simulate Postgres assigning a sequence id.
        if isinstance(obj, AuditLog):
            obj.id = 101
            obj.occurred_at = datetime.now(UTC)
            added.append(obj)

    db.add = MagicMock(side_effect=_add)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    notify_spy = AsyncMock()
    monkeypatch.setattr(admin_students_api, "send_notification", notify_spy)

    _install(db, admin)
    try:
        resp = await client.post(
            f"/api/admin/students/{student.id}/overrides",
            json={
                "override_type": "late_registration",
                "reason": "Medical clearance received after deadline",
                "subject": "ACC101",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["override_type"] == "late_registration"
        assert body["subject"] == "ACC101"
        assert added and added[0].action == "override.late_registration"
        assert added[0].target_type == "student_override"
        assert added[0].reason.startswith("Medical clearance")
        notify_spy.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


async def test_create_override_404_when_student_missing(client: AsyncClient):
    admin = _make_admin()
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    _install(db, admin)
    try:
        resp = await client.post(
            f"/api/admin/students/{uuid.uuid4()}/overrides",
            json={
                "override_type": "prereq_waiver",
                "reason": "A proper justification string",
            },
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
