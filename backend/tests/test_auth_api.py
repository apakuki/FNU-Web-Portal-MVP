import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.auth import hash_password
from src.backend.db.models import User
from src.backend.db.session import get_session
from src.backend.main import app


def _mock_db_with_result(return_value):
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = return_value
    mock_db.execute.return_value = result
    return mock_db


def _override_get_session(mock):
    async def _override():
        yield mock

    return _override


def _make_user(role: str = "student") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{role}@fnu.ac.fj",
        full_name=f"Test {role.title()}",
        role=role,
        password_hash=hash_password("password123"),
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )
    return user


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_login_invalid_credentials(client: AsyncClient):
    mock_db = _mock_db_with_result(None)

    app.dependency_overrides[get_session] = _override_get_session(mock_db)
    try:
        response = await client.post(
            "/api/auth/login",
            json={"email": "nobody@fnu.ac.fj", "password": "wrong"},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_login_success(client: AsyncClient):
    user = _make_user("student")
    mock_db = _mock_db_with_result(user)

    app.dependency_overrides[get_session] = _override_get_session(mock_db)
    try:
        response = await client.post(
            "/api/auth/login",
            json={"email": "student@fnu.ac.fj", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["user"]["role"] == "student"
        assert "access_token" in data
    finally:
        app.dependency_overrides.clear()


async def test_me_without_token(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code in (401, 403)


async def test_reset_password_always_succeeds(client: AsyncClient):
    response = await client.post(
        "/api/auth/reset-password",
        json={"email": "anyone@fnu.ac.fj"},
    )
    assert response.status_code == 200
    assert "reset link" in response.json()["detail"].lower()


async def test_reset_password_confirm_rejects_invalid_token(client: AsyncClient):
    response = await client.post(
        "/api/auth/reset-password/confirm",
        json={"token": "invalid-token-value-long-enough", "new_password": "NewSecurePass123"},
    )
    assert response.status_code == 400
