"""Profile API integration — auth scoping, email uniqueness, photo upload."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from src.backend.auth import get_current_user
from src.backend.db.models import ProfilePhoto, StudentProfile, User
from src.backend.db.session import get_session
from src.backend.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _mock_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        banner_id="S00012345",
        email="student@fnu.ac.fj",
        phone="+679 123 4567",
        password_hash="x",
        role="student",
        full_name="Test Student",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )


def _install_overrides(db, user):
    async def _session_override():
        yield db

    async def _user_override():
        return user

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override


def _make_db(profile=None, photo=None):
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()

    async def _scalar(stmt):
        text = str(stmt)
        if "profile_photos.image_data" in text:
            # full ProfilePhoto row select
            return photo
        if "profile_photos.id" in text:
            # has_photo existence check -> scalar id
            return photo.id if photo else None
        if "profile_photos" in text:
            return photo
        if "student_profiles" in text:
            return profile
        if "users" in text:
            return None  # email uniqueness lookup -> no collision by default
        return None

    db.scalar.side_effect = _scalar
    db.add = MagicMock()
    return db


async def test_get_profile_returns_authenticated_user(client: AsyncClient, monkeypatch):
    user = _mock_user()
    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        address_line1="1 Samabula Rd",
        city="Suva",
        country="Fiji",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db = _make_db(profile=profile, photo=None)
    _install_overrides(db, user)

    try:
        resp = await client.get("/api/profile")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["email"] == user.email
        assert body["city"] == "Suva"
        assert body["has_photo"] is False
    finally:
        app.dependency_overrides.clear()


async def test_update_profile_validates_phone(client: AsyncClient):
    user = _mock_user()
    db = _make_db()
    _install_overrides(db, user)

    try:
        resp = await client.put(
            "/api/profile",
            json={"phone": "not-a-phone-number!!!@@@"},
        )
        assert resp.status_code == 400
        assert "phone" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_upload_photo_rejects_empty(client: AsyncClient):
    user = _mock_user()
    db = _make_db()
    _install_overrides(db, user)

    try:
        resp = await client.post(
            "/api/profile/photo",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Empty upload"
    finally:
        app.dependency_overrides.clear()


async def test_upload_photo_rejects_non_image(client: AsyncClient):
    user = _mock_user()
    db = _make_db()
    _install_overrides(db, user)

    try:
        resp = await client.post(
            "/api/profile/photo",
            files={"file": ("fake.jpg", b"not-an-image", "image/jpeg")},
        )
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


async def test_upload_photo_accepts_valid_jpeg(client: AsyncClient, monkeypatch):
    user = _mock_user()

    # Stub out write_audit_log so the test does not hit the real DB
    from src.backend.api import profile as profile_api
    monkeypatch.setattr(profile_api, "write_audit_log", AsyncMock())

    db = _make_db()
    _install_overrides(db, user)

    buf = io.BytesIO()
    Image.new("RGB", (300, 300), "green").save(buf, format="JPEG")
    raw = buf.getvalue()

    try:
        resp = await client.post(
            "/api/profile/photo",
            files={"file": ("me.jpg", raw, "image/jpeg")},
        )
        assert resp.status_code == 200, resp.text
        # db.add should have been called (for the new ProfilePhoto row)
        assert db.add.called
    finally:
        app.dependency_overrides.clear()


async def test_get_photo_returns_404_when_missing(client: AsyncClient):
    user = _mock_user()
    db = _make_db(photo=None)
    _install_overrides(db, user)

    try:
        resp = await client.get("/api/profile/photo/me")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


async def test_get_photo_returns_bytes_when_present(client: AsyncClient):
    user = _mock_user()
    photo = ProfilePhoto(
        id=uuid.uuid4(),
        user_id=user.id,
        mime_type="image/jpeg",
        size_bytes=4,
        image_data=b"abcd",
        uploaded_at=datetime.now(UTC),
    )
    db = _make_db(photo=photo)
    _install_overrides(db, user)

    try:
        resp = await client.get("/api/profile/photo/me")
        assert resp.status_code == 200
        assert resp.content == b"abcd"
        assert resp.headers["content-type"] == "image/jpeg"
    finally:
        app.dependency_overrides.clear()
