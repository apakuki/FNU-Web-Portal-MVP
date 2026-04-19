"""TTL cache wrapper for Banner read operations.

Caches programmes, courses, and fee schedules with a configurable TTL
(default 15 minutes) to reduce Banner API calls under load.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

DEFAULT_TTL_SECONDS = 900  # 15 minutes


class TTLCache:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    async def get_or_fetch(self, key: str, fetch_fn: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        if key in self._store:
            expires_at, value = self._store[key]
            if now < expires_at:
                return value

        value = await fetch_fn()
        self._store[key] = (now + self._ttl, value)
        return value

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def invalidate_all(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)
