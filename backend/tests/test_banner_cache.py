"""Tests for the TTL cache and CachedBannerClient."""

import time

import pytest

from src.backend.banner.cache import TTLCache
from src.backend.banner.cached_client import CachedBannerClient
from src.backend.banner.mock_adapter import MockBannerClient


async def test_cache_returns_cached_value() -> None:
    cache = TTLCache(ttl_seconds=60)
    call_count = 0

    async def fetcher() -> str:
        nonlocal call_count
        call_count += 1
        return "result"

    val1 = await cache.get_or_fetch("key", fetcher)
    val2 = await cache.get_or_fetch("key", fetcher)

    assert val1 == val2 == "result"
    assert call_count == 1


async def test_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = TTLCache(ttl_seconds=1)
    call_count = 0
    current_time = [100.0]

    monkeypatch.setattr(time, "monotonic", lambda: current_time[0])

    async def fetcher() -> str:
        nonlocal call_count
        call_count += 1
        return f"v{call_count}"

    val1 = await cache.get_or_fetch("key", fetcher)
    assert val1 == "v1"
    assert call_count == 1

    current_time[0] = 102.0
    val2 = await cache.get_or_fetch("key", fetcher)
    assert val2 == "v2"
    assert call_count == 2


async def _co(val: str) -> str:
    return val


async def test_cache_invalidate() -> None:
    cache = TTLCache(ttl_seconds=300)

    await cache.get_or_fetch("key", lambda: _co("value"))
    assert cache.size == 1

    cache.invalidate("key")
    assert cache.size == 0


async def test_cache_invalidate_all() -> None:
    cache = TTLCache(ttl_seconds=300)

    await cache.get_or_fetch("a", lambda: _co("1"))
    await cache.get_or_fetch("b", lambda: _co("2"))
    assert cache.size == 2

    cache.invalidate_all()
    assert cache.size == 0


async def test_cached_client_programmes_cached() -> None:
    inner = MockBannerClient()
    cached = CachedBannerClient(inner, ttl_seconds=60)

    p1 = await cached.get_programmes()
    p2 = await cached.get_programmes()

    assert p1 == p2
    assert cached.cache.size >= 1


async def test_cached_client_courses_keyed_by_programme() -> None:
    inner = MockBannerClient()
    cached = CachedBannerClient(inner, ttl_seconds=60)

    c1 = await cached.get_courses("BCOM")
    c2 = await cached.get_courses("BSCI")

    assert c1 != c2
    assert cached.cache.size == 2


async def test_cached_client_fee_schedule_cached() -> None:
    inner = MockBannerClient()
    cached = CachedBannerClient(inner, ttl_seconds=60)

    f1 = await cached.get_fee_schedule(2026, "S1")
    f2 = await cached.get_fee_schedule(2026, "S1")

    assert f1 == f2
    assert cached.cache.size == 1


async def test_cached_client_student_not_cached() -> None:
    inner = MockBannerClient()
    cached = CachedBannerClient(inner, ttl_seconds=60)

    await cached.get_student("S00012345")
    await cached.get_student("S00012345")

    assert cached.cache.size == 0
