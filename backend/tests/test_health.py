from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_health_returns_ok(client: AsyncClient):
    with patch("src.backend.api.health.async_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["banner"] == "ok"


async def test_health_postgres_unavailable(client: AsyncClient):
    with patch("src.backend.api.health.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("connection refused"),
        )
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["postgres"] == "unavailable"
