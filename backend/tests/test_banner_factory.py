"""Tests for the Banner client factory and production validation."""

import pytest

from src.backend.banner.cached_client import CachedBannerClient
from src.backend.banner.factory import get_banner_client, reset_banner_client


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_banner_client()
    yield  # type: ignore[misc]
    reset_banner_client()


def test_factory_returns_cached_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BANNER_MODE", "mock")
    monkeypatch.setenv("ENVIRONMENT", "development")

    from src.backend.config import Settings

    monkeypatch.setattr("src.backend.banner.factory.settings", Settings())
    reset_banner_client()

    client = get_banner_client()
    assert isinstance(client, CachedBannerClient)


def test_factory_rejects_mock_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BANNER_MODE", "mock")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("PAYMENTS_MODE", "live")
    monkeypatch.setenv("MPAISA_MERCHANT_ID", "test-merchant")
    monkeypatch.setenv("MPAISA_SECRET", "test-secret")
    monkeypatch.setenv("MYCASH_MERCHANT_ID", "test-merchant")
    monkeypatch.setenv("MYCASH_SECRET", "test-secret")

    from src.backend.config import Settings

    monkeypatch.setattr("src.backend.banner.factory.settings", Settings())
    reset_banner_client()

    with pytest.raises(ValueError, match="BANNER_MODE=mock is not allowed in production"):
        get_banner_client()


def test_factory_rejects_live_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BANNER_MODE", "live")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("BANNER_API_URL", "")
    monkeypatch.setenv("BANNER_API_KEY", "")

    from src.backend.config import Settings

    monkeypatch.setattr("src.backend.banner.factory.settings", Settings())
    reset_banner_client()

    with pytest.raises(ValueError, match="BANNER_API_URL and BANNER_API_KEY must be set"):
        get_banner_client()


def test_factory_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BANNER_MODE", "mock")
    monkeypatch.setenv("ENVIRONMENT", "development")

    from src.backend.config import Settings

    monkeypatch.setattr("src.backend.banner.factory.settings", Settings())
    reset_banner_client()

    client1 = get_banner_client()
    client2 = get_banner_client()
    assert client1 is client2
