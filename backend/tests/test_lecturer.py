"""Tests for the Part 13 lecturer API.

Covers schema validation, grade-value validation, role-based access,
the draft → submitted → finalised workflow, ownership scoping, and
the roster export formats.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api import lecturer as lecturer_api
from src.backend.api.lecturer import (
    VALID_EXPORT_FORMATS,
    VALID_GRADES,
    VALID_STATUSES,
    GradeUpsertItem,
    GradeUpsertRequest,
    _validate_grade,
)
from src.backend.auth import get_current_user
from src.backend.banner.types import (
    Campus,
    ClassRoster,
    Offering,
    RosterEntry,
    Semester,
    SubmitGradeResponse,
)
from src.backend.db.models import LecturerGrade, User
from src.backend.db.session import get_session
from src.backend.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- helpers --------------------------------------------------------------


def _make_lecturer(banner_id: str = "L00010001") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        banner_id=banner_id,
        email="lecturer@fnu.ac.fj",
        phone=None,
        password_hash="x",
        role="lecturer",
        full_name="Dr. Mere Tuisawau",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )


def _make_student() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        banner_id="S00012345",
        email="student@fnu.ac.fj",
        phone=None,
        password_hash="x",
        role="student",
        full_name="Apisai Delana",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )


def _make_offering(
    *,
    offering_id: str = "OFF-2026-S1-ACC101-NAS",
    lecturer_banner_id: str | None = "L00010001",
    course_code: str = "ACC101",
) -> Offering:
    return Offering(
        id=offering_id,
        course_code=course_code,
        semester=Semester.S1,
        year=2026,
        campus=Campus.NASINU,
        lecturer_name="Dr. Mere Tuisawau",
        lecturer_banner_id=lecturer_banner_id,
        day_of_week="Monday",
        start_time="09:00",
        end_time="11:00",
        room="CBHTS-LT1",
        capacity=60,
        enrolled=2,
    )


def _make_roster(offering_id: str = "OFF-2026-S1-ACC101-NAS") -> ClassRoster:
    return ClassRoster(
        offering_id=offering_id,
        course_code="ACC101",
        course_name="Introduction to Accounting",
        semester=Semester.S1,
        year=2026,
        campus=Campus.NASINU,
        entries=[
            RosterEntry(
                banner_student_id="S00012345",
                student_name="Apisai Delana",
                email="student@fnu.ac.fj",
                grade=None,
                attendance_pct=92.5,
            ),
            RosterEntry(
                banner_student_id="S00099001",
                student_name="Joeli Ravuama",
                email="joeli@student.fnu.ac.fj",
                grade=None,
                attendance_pct=86.0,
            ),
        ],
    )


def _install(db, user):
    async def _session_override():
        yield db

    async def _user_override():
        return user

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override


def _fake_banner(
    offerings: list[Offering] | None = None,
    roster: ClassRoster | None = None,
    submit_result: SubmitGradeResponse | None = None,
):
    banner = MagicMock()
    banner.get_offerings = AsyncMock(return_value=offerings or [])
    banner.get_courses = AsyncMock(return_value=[])
    banner.get_class_roster = AsyncMock(return_value=roster)
    banner.submit_grade = AsyncMock(
        return_value=submit_result
        or SubmitGradeResponse(success=True, message="ok"),
    )
    return banner


def _scalars_returning(rows):
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    return AsyncMock(return_value=scalars_result)


# --- schema / validation tests -------------------------------------------


def test_grade_values_span_fnu_scale():
    assert VALID_GRADES == {
        "A+", "A", "A-",
        "B+", "B", "B-",
        "C+", "C", "C-",
        "D", "E", "F", "WD",
    }


def test_status_set_covers_workflow():
    assert VALID_STATUSES == {"draft", "submitted", "finalised"}


def test_export_formats_set_is_constrained():
    assert VALID_EXPORT_FORMATS == {"csv", "xlsx", "pdf"}


def test_validate_grade_accepts_blank():
    assert _validate_grade(None) is None
    assert _validate_grade("") is None


def test_validate_grade_uppercases_trims():
    assert _validate_grade(" a- ") == "A-"


def test_validate_grade_rejects_unknown():
    with pytest.raises(Exception):
        _validate_grade("Z")


def test_upsert_request_requires_entries():
    with pytest.raises(Exception):
        GradeUpsertRequest(offering_id="X", entries=[])


def test_upsert_item_allows_null_grade_draft():
    req = GradeUpsertRequest(
        offering_id="OFF-1",
        entries=[GradeUpsertItem(banner_student_id="S1", grade=None)],
    )
    assert req.entries[0].grade is None


# --- integration tests ---------------------------------------------------


async def test_rosters_requires_lecturer_role(client: AsyncClient):
    resp = await client.get("/api/lecturer/rosters")
    assert resp.status_code in (401, 403)


async def test_rosters_forbids_student(client: AsyncClient):
    _install(AsyncMock(), _make_student())
    try:
        resp = await client.get("/api/lecturer/rosters")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_rosters_lists_only_my_offerings(
    client: AsyncClient, monkeypatch
):
    lecturer = _make_lecturer()
    mine = _make_offering()
    other = _make_offering(
        offering_id="OFF-2026-S1-MGT101-NAS",
        lecturer_banner_id="L00010002",
        course_code="MGT101",
    )

    banner = _fake_banner(
        offerings=[mine, other],
        roster=_make_roster(),
    )
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    db = AsyncMock()
    db.scalars = _scalars_returning([])  # no grade rows yet

    _install(db, lecturer)
    try:
        resp = await client.get("/api/lecturer/rosters")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["courses"]) == 1
        assert body["courses"][0]["course_code"] == "ACC101"
        assert body["courses"][0]["student_count"] == 2
    finally:
        app.dependency_overrides.clear()


async def test_roster_detail_scopes_to_owner(client: AsyncClient, monkeypatch):
    lecturer = _make_lecturer()
    not_mine = _make_offering(lecturer_banner_id="L99999999")
    banner = _fake_banner(offerings=[not_mine], roster=_make_roster())
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    db = AsyncMock()
    db.scalars = _scalars_returning([])

    _install(db, lecturer)
    try:
        resp = await client.get(
            f"/api/lecturer/rosters/{not_mine.id}",
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


async def test_upsert_rejects_student_not_on_roster(
    client: AsyncClient, monkeypatch
):
    lecturer = _make_lecturer()
    mine = _make_offering()
    banner = _fake_banner(offerings=[mine], roster=_make_roster())
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    db = AsyncMock()
    db.scalars = _scalars_returning([])
    db.commit = AsyncMock()

    _install(db, lecturer)
    try:
        resp = await client.post(
            "/api/lecturer/grades",
            json={
                "offering_id": mine.id,
                "entries": [
                    {"banner_student_id": "S99999999", "grade": "A"},
                ],
            },
        )
        assert resp.status_code == 400
        assert "not on this roster" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_upsert_rejects_invalid_grade(client: AsyncClient, monkeypatch):
    lecturer = _make_lecturer()
    mine = _make_offering()
    banner = _fake_banner(offerings=[mine], roster=_make_roster())
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    db = AsyncMock()
    db.scalars = _scalars_returning([])
    db.commit = AsyncMock()

    _install(db, lecturer)
    try:
        resp = await client.post(
            "/api/lecturer/grades",
            json={
                "offering_id": mine.id,
                "entries": [
                    {"banner_student_id": "S00012345", "grade": "Z"},
                ],
            },
        )
        assert resp.status_code == 400
        assert "invalid grade" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_upsert_blocked_on_finalised_row(
    client: AsyncClient, monkeypatch
):
    lecturer = _make_lecturer()
    mine = _make_offering()
    banner = _fake_banner(offerings=[mine], roster=_make_roster())
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    existing = LecturerGrade(
        id=uuid.uuid4(),
        offering_id=mine.id,
        course_code="ACC101",
        banner_student_id="S00012345",
        semester="S1",
        year=2026,
        assessment_period="final",
        grade="A",
        status="finalised",
        entered_by_user_id=lecturer.id,
    )
    db = AsyncMock()
    db.scalars = _scalars_returning([existing])
    db.commit = AsyncMock()

    _install(db, lecturer)
    try:
        resp = await client.post(
            "/api/lecturer/grades",
            json={
                "offering_id": mine.id,
                "entries": [
                    {"banner_student_id": "S00012345", "grade": "B"},
                ],
            },
        )
        assert resp.status_code == 400
        assert "finalised" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_submit_requires_grade_filled_in(
    client: AsyncClient, monkeypatch
):
    lecturer = _make_lecturer()
    mine = _make_offering()
    banner = _fake_banner(offerings=[mine], roster=_make_roster())
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    empty_row = LecturerGrade(
        id=uuid.uuid4(),
        offering_id=mine.id,
        course_code="ACC101",
        banner_student_id="S00012345",
        semester="S1",
        year=2026,
        assessment_period="final",
        grade=None,
        status="draft",
        entered_by_user_id=lecturer.id,
    )
    db = AsyncMock()
    db.scalars = _scalars_returning([empty_row])
    db.commit = AsyncMock()

    _install(db, lecturer)
    try:
        resp = await client.post(
            f"/api/lecturer/grades/{mine.id}/submit",
        )
        assert resp.status_code == 400
        assert "must have a grade" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_finalise_writes_through_to_banner(
    client: AsyncClient, monkeypatch
):
    lecturer = _make_lecturer()
    mine = _make_offering()
    banner = _fake_banner(offerings=[mine], roster=_make_roster())
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)
    monkeypatch.setattr(lecturer_api, "write_audit_log", AsyncMock())

    row = LecturerGrade(
        id=uuid.uuid4(),
        offering_id=mine.id,
        course_code="ACC101",
        banner_student_id="S00012345",
        semester="S1",
        year=2026,
        assessment_period="final",
        grade="A-",
        status="submitted",
        entered_by_user_id=lecturer.id,
    )
    db = AsyncMock()
    db.scalars = _scalars_returning([row])
    db.commit = AsyncMock()

    _install(db, lecturer)
    try:
        resp = await client.post(
            f"/api/lecturer/grades/{mine.id}/finalise",
        )
        assert resp.status_code == 200, resp.text
        banner.submit_grade.assert_awaited_once()
        submitted = banner.submit_grade.await_args.args[0]
        assert submitted.banner_student_id == "S00012345"
        assert submitted.grade == "A-"
        assert row.status == "finalised"
        assert row.finalised_at is not None
    finally:
        app.dependency_overrides.clear()


async def test_finalise_fails_when_banner_rejects(
    client: AsyncClient, monkeypatch
):
    lecturer = _make_lecturer()
    mine = _make_offering()
    banner = _fake_banner(
        offerings=[mine],
        roster=_make_roster(),
        submit_result=SubmitGradeResponse(success=False, message="nope"),
    )
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    row = LecturerGrade(
        id=uuid.uuid4(),
        offering_id=mine.id,
        course_code="ACC101",
        banner_student_id="S00012345",
        semester="S1",
        year=2026,
        assessment_period="final",
        grade="B",
        status="submitted",
        entered_by_user_id=lecturer.id,
    )
    db = AsyncMock()
    db.scalars = _scalars_returning([row])
    db.commit = AsyncMock()

    _install(db, lecturer)
    try:
        resp = await client.post(
            f"/api/lecturer/grades/{mine.id}/finalise",
        )
        assert resp.status_code == 502
        assert row.status == "submitted"
    finally:
        app.dependency_overrides.clear()


async def test_export_csv_streams_rows(client: AsyncClient, monkeypatch):
    lecturer = _make_lecturer()
    mine = _make_offering()
    banner = _fake_banner(offerings=[mine], roster=_make_roster())
    monkeypatch.setattr(lecturer_api, "get_banner_client", lambda: banner)

    db = AsyncMock()
    db.scalars = _scalars_returning([])

    _install(db, lecturer)
    try:
        resp = await client.get(
            f"/api/lecturer/rosters/{mine.id}/export?format=csv",
        )
        assert resp.status_code == 200, resp.text
        body = resp.text
        assert "banner_student_id" in body
        assert "S00012345" in body
        assert "S00099001" in body
        disposition = resp.headers.get("content-disposition", "")
        assert "roster_ACC101" in disposition
    finally:
        app.dependency_overrides.clear()
