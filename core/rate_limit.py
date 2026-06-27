"""Shared rate limiting primitives with O(1) token bucket implementation."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class TokenBucketRateLimiter:
    """Token bucket rate limiter — O(1) per acquire.

    The bucket holds up to ``capacity`` tokens and refills at ``rate`` tokens
    per second.  Each :meth:`acquire` call consumes one token; if the bucket is
    empty the caller sleeps until a token becomes available.

    Implemented as an async context manager so call sites can do::

        async with limiter:
            ...
    """

    def __init__(self, rate: int, window: float) -> None:
        """Initialise a token bucket.

        Args:
            rate: Maximum number of tokens (requests) per window.
            window: Time window in seconds.
        """
        if rate <= 0:
            raise ValueError("rate must be > 0")
        if window <= 0:
            raise ValueError("window must be > 0")

        self._capacity = float(rate)
        self._refill_rate = float(rate) / float(window)  # tokens per second
        self._tokens = 0.0  # start empty — no burst on first request
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire one token, blocking until available."""
        while True:
            async with self._lock:
                wait_time = self._try_acquire()
                if wait_time <= 0:
                    return
            await asyncio.sleep(wait_time)

    def _try_acquire(self) -> float:
        """Non-blocking attempt; returns seconds to wait (0.0 = acquired).

        Caller must hold ``self._lock``.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return 0.0

        # Time until next token is available
        return (1.0 - self._tokens) / self._refill_rate

    async def __aenter__(self) -> TokenBucketRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class StrictSlidingWindowLimiter:
    """Strict sliding window limiter — O(n) in worst case, amortised O(1).

    Guarantees: at most ``rate_limit`` acquisitions in any interval of length
    ``rate_window`` (seconds).

    Retained for API and messaging rate limiters where burst accuracy matters.
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
