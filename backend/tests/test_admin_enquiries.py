"""Tests for the Part 12 enquiries admin API.

Covers schema validation, the resolved-before-note and locked-note
invariants, feedback preconditions, and role-based access.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api import admin_enquiries as admin_enquiries_api
from src.backend.api.admin_enquiries import (
    VALID_SOURCES,
    VALID_STATUSES,
    EnquiryCreateRequest,
    EnquiryUpdateRequest,
    FeedbackRequest,
)
from src.backend.auth import get_current_user
from src.backend.db.models import Enquiry, User
from src.backend.db.session import get_session
from src.backend.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_staff() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        banner_id=None,
        email="staff@fnu.ac.fj",
        phone=None,
        password_hash="x",
        role="staff",
        full_name="Registry Staff",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )


def _make_enquiry(
    *, status: str = "open", resolution_note: str | None = None
) -> Enquiry:
    return Enquiry(
        id=uuid.uuid4(),
        source="chatbot",
        student_user_id=None,
        student_identifier="S00012345",
        subject="Cannot see my timetable",
        body="I logged in but the timetable page is blank.",
        status=status,
        assigned_staff_id=None,
        resolution_note=resolution_note,
        student_feedback=None,
        opened_at=datetime.now(UTC),
        resolved_at=None,
    )


def _install(db, user):
    async def _session_override():
        yield db

    async def _user_override():
        return user

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override


# --- Schema tests ---------------------------------------------------------


def test_status_set_covers_workflow():
    assert VALID_STATUSES == {"open", "in_progress", "resolved", "closed"}


def test_source_set_covers_channels():
    assert VALID_SOURCES == {"chatbot", "phone", "email", "walk_in", "staff"}


def test_create_request_rejects_bad_source():
    with pytest.raises(Exception):
        EnquiryCreateRequest(subject="x", body="y", source="mystery")


def test_update_request_rejects_bad_status():
    with pytest.raises(Exception):
        EnquiryUpdateRequest(status="floating")


def test_feedback_request_range():
    FeedbackRequest(rating=1)
    FeedbackRequest(rating=5)
    with pytest.raises(Exception):
        FeedbackRequest(rating=0)
    with pytest.raises(Exception):
        FeedbackRequest(rating=6)


# --- Integration tests ----------------------------------------------------


async def test_list_enquiries_requires_auth(client: AsyncClient):
    resp = await client.get("/api/admin/enquiries")
    assert resp.status_code in (401, 403)


async def test_list_enquiries_returns_rows(client: AsyncClient):
    staff = _make_staff()
    enq = _make_enquiry()

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=1)
    scalars_result = MagicMock()
    scalars_result.all.return_value = [enq]
    db.scalars = AsyncMock(return_value=scalars_result)

    _install(db, staff)
    try:
        resp = await client.get("/api/admin/enquiries?status=open")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["subject"] == enq.subject
    finally:
        app.dependency_overrides.clear()


async def test_update_rejects_edit_of_existing_resolution_note(client: AsyncClient):
    staff = _make_staff()
    enq = _make_enquiry(status="resolved", resolution_note="Already written")

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=enq)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    _install(db, staff)
    try:
        resp = await client.put(
            f"/api/admin/enquiries/{enq.id}",
            json={"resolution_note": "Second attempt"},
        )
        assert resp.status_code == 400
        assert "cannot be edited" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_cannot_resolve_without_note(client: AsyncClient):
    staff = _make_staff()
    enq = _make_enquiry(status="in_progress", resolution_note=None)

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=enq)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    _install(db, staff)
    try:
        resp = await client.put(
            f"/api/admin/enquiries/{enq.id}",
            json={"status": "resolved"},
        )
        assert resp.status_code == 400
        assert "resolution note is required" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_resolve_happy_path_sets_note_and_timestamp(
    client: AsyncClient, monkeypatch
):
    staff = _make_staff()
    enq = _make_enquiry(status="in_progress", resolution_note=None)

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=enq)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    monkeypatch.setattr(admin_enquiries_api, "write_audit_log", AsyncMock())

    _install(db, staff)
    try:
        resp = await client.put(
            f"/api/admin/enquiries/{enq.id}",
            json={
                "status": "resolved",
                "resolution_note": "Cleared browser cache; issue gone.",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["resolution_note"].startswith("Cleared browser")
        assert enq.resolved_at is not None
    finally:
        app.dependency_overrides.clear()


async def test_feedback_requires_resolved(client: AsyncClient):
    staff = _make_staff()
    enq = _make_enquiry(status="open")

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=enq)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    _install(db, staff)
    try:
        resp = await client.post(
            f"/api/admin/enquiries/{enq.id}/feedback",
            json={"rating": 5},
        )
        assert resp.status_code == 400
        assert "resolved" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_feedback_locked_after_recorded(client: AsyncClient, monkeypatch):
    staff = _make_staff()
    enq = _make_enquiry(status="resolved", resolution_note="done")
    enq.student_feedback = 4

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=enq)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    monkeypatch.setattr(admin_enquiries_api, "write_audit_log", AsyncMock())

    _install(db, staff)
    try:
        resp = await client.post(
            f"/api/admin/enquiries/{enq.id}/feedback",
            json={"rating": 3},
        )
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
