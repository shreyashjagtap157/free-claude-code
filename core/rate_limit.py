"""Shared rate limiting primitives."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class StrictSlidingWindowLimiter:
    """Strict sliding window limiter.

    Guarantees: at most ``rate_limit`` acquisitions in any interval of length
    ``rate_window`` (seconds).

    Implemented as an async context manager so call sites can do::

        async with limiter:
            ...
    """

    def __init__(self, rate_limit: int, rate_window: float) -> None:
        if rate_limit <= 0:
            raise ValueError("rate_limit must be > 0")
        if rate_window <= 0:
            raise ValueError("rate_window must be > 0")

        self._rate_limit = int(rate_limit)
        self._rate_window = float(rate_window)
        self._times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            wait_time = 0.0
            async with self._lock:
                now = time.monotonic()
                cutoff = now - self._rate_window

                while self._times and self._times[0] <= cutoff:
                    self._times.popleft()

                if len(self._times) < self._rate_limit:
                    self._times.append(now)
                    return

                oldest = self._times[0]
                wait_time = max(0.0, (oldest + self._rate_window) - now)

            if wait_time > 0:
                await asyncio.sleep(wait_time)
            else:
                await asyncio.sleep(0)

    async def __aenter__(self) -> StrictSlidingWindowLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FixedSpacingLimiter:
    """Evenly spaces acquisitions at ``rate_window / rate_limit`` seconds apart.

    Unlike :class:`StrictSlidingWindowLimiter` (which allows bursts of up to
    ``rate_limit`` requests followed by a stall of up to ``rate_window``
    seconds), this limiter ensures a constant inter-arrival time.

    For example, with ``rate_limit=40, rate_window=60``, each request is
    spaced exactly 1.5 seconds after the previous one.  The first request
    in a burst passes through immediately; subsequent concurrent requests
    are queued and released one-by-one at the configured interval.

    This is ideal for upstream providers with a hard per-minute cap where
    burst-then-stall behavior would cause long, unpredictable pauses for
    interactive clients (e.g. Claude Code).
    """

    def __init__(self, rate_limit: int, rate_window: float) -> None:
        if rate_limit <= 0:
            raise ValueError("rate_limit must be > 0")
        if rate_window <= 0:
            raise ValueError("rate_window must be > 0")

        self._interval = rate_window / rate_limit
        self._last_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until the next slot, then return."""
        while True:
            async with self._lock:
                now = time.monotonic()
                wait = max(0.0, self._last_time + self._interval - now)
                if wait <= 0.0:
                    self._last_time = now
                    return
            await asyncio.sleep(wait)
