"""Direct tests for core rate limit primitives."""

import asyncio
import time

import pytest

from core.rate_limit import FixedSpacingLimiter, StrictSlidingWindowLimiter


@pytest.mark.asyncio
async def test_strict_window_allows_burst_then_blocks():
    lim = StrictSlidingWindowLimiter(rate_limit=2, rate_window=0.2)
    await lim.acquire()
    await lim.acquire()
    start = time.monotonic()
    await lim.acquire()
    assert time.monotonic() - start >= 0.15


@pytest.mark.asyncio
async def test_strict_window_async_context_manager():
    lim = StrictSlidingWindowLimiter(rate_limit=1, rate_window=0.15)

    async def run():
        async with lim:
            pass

    await run()
    start = time.monotonic()
    await run()
    assert time.monotonic() - start >= 0.1


def test_strict_window_rejects_invalid_config():
    with pytest.raises(ValueError):
        StrictSlidingWindowLimiter(rate_limit=0, rate_window=1.0)
    with pytest.raises(ValueError):
        StrictSlidingWindowLimiter(rate_limit=1, rate_window=0.0)


@pytest.mark.asyncio
async def test_fixed_spacing_spaces_concurrent_requests():
    """Concurrent requests are spaced at ``rate_window / rate_limit`` apart."""
    lim = FixedSpacingLimiter(rate_limit=3, rate_window=0.6)  # 0.2s interval

    acquired: list[float] = []

    async def acquire():
        await lim.acquire()
        acquired.append(time.monotonic())

    await asyncio.gather(*(acquire() for _ in range(4)))

    acquired.sort()
    assert len(acquired) == 4

    tolerance = 0.05
    for i in range(1, len(acquired)):
        gap = acquired[i] - acquired[i - 1]
        expected = 0.2  # 0.6 / 3
        assert gap >= expected - tolerance, (
            f"Gap {i}: {gap:.3f}s, expected ~{expected:.3f}s"
        )


@pytest.mark.asyncio
async def test_fixed_spacing_idle_request_passes_immediately():
    """Request after idle period should not wait."""
    lim = FixedSpacingLimiter(rate_limit=10, rate_window=1.0)
    await lim.acquire()
    await asyncio.sleep(0.1)
    start = time.monotonic()
    await lim.acquire()
    assert time.monotonic() - start < 0.05


def test_fixed_spacing_rejects_invalid_config():
    with pytest.raises(ValueError):
        FixedSpacingLimiter(rate_limit=0, rate_window=1.0)
    with pytest.raises(ValueError):
        FixedSpacingLimiter(rate_limit=1, rate_window=0.0)
