"""In-process rate limiter for outbound Banner API calls.

Token-bucket style limiter shared across all callers in this process.
Ensures we stay within Ellucian's per-second quota even under load.
Configured via BANNER_RATE_LIMIT_PER_SEC (default 20/sec).
"""

import asyncio
import time

from src.backend.config import settings


class _TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int) -> None:
        self._rate = rate_per_sec
        self._capacity = burst
        self._tokens = float(burst)
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._updated
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._updated = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            needed = (1.0 - self._tokens) / self._rate
        await asyncio.sleep(needed)
        await self.acquire()


_bucket: _TokenBucket | None = None


def _get_bucket() -> _TokenBucket:
    global _bucket
    if _bucket is None:
        rate = float(settings.banner_rate_limit_per_sec)
        _bucket = _TokenBucket(rate_per_sec=rate, burst=max(1, int(rate)))
    return _bucket


async def acquire_banner_slot() -> None:
    await _get_bucket().acquire()


def reset_bucket() -> None:
    """Test hook — clear the singleton bucket."""
    global _bucket
    _bucket = None
