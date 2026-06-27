"""
Global Rate Limiter for Messaging Platforms.

Centralizes outgoing message requests and ensures compliance with rate limits
using a strict sliding window algorithm and a task queue.
"""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from functools import cache
from typing import Any

from loguru import logger

from config.settings import get_settings
from core.rate_limit import StrictSlidingWindowLimiter as SlidingWindowLimiter

from .safe_diagnostics import format_exception_for_log


class MessagingRateLimiter:
    """
    A rate limiter for messaging with a task compaction queue.

    Not a singleton --- use :func:`get_messaging_rate_limiter` for the standard
    production instance. Tests may construct instances directly or patch the
    factory function.
    """

    def __init__(self, *, rate_limit: int, rate_window: float) -> None:
        self.limiter = SlidingWindowLimiter(rate_limit, rate_window)
        self._queue_list: deque[str] = deque()
        self._queue_map: dict[
            str, tuple[Callable[[], Awaitable[Any]], list[asyncio.Future]]
        ] = {}
        self._condition = asyncio.Condition()
        self._shutdown = asyncio.Event()
        self._worker_task: asyncio.Task | None = None

        self._paused_until = 0

        logger.info(
            f"MessagingRateLimiter initialized ({rate_limit} req / {rate_window}s with Task Compaction)"
        )
        self._start_worker()

    def _start_worker(self) -> None:
        """Ensure the worker task exists."""
        if self._worker_task and not self._worker_task.done():
            return
        # Named task helps debugging shutdown hangs.
        self._worker_task = asyncio.create_task(
            self._worker(), name="msg-limiter-worker"
        )

    async def _worker(self):
        """Background worker that processes queued messaging tasks."""
        logger.info("MessagingRateLimiter worker started")
        while not self._shutdown.is_set():
            try:
                # Get a task from the queue
                async with self._condition:
                    while not self._queue_list and not self._shutdown.is_set():
                        await self._condition.wait()

                    if self._shutdown.is_set():
                        break

                    dedup_key = self._queue_list.popleft()
                    func, futures = self._queue_map.pop(dedup_key)

                # Check for manual pause (FloodWait)
                now = asyncio.get_event_loop().time()
                if self._paused_until > now:
                    wait_time = self._paused_until - now
                    logger.warning(
                        f"Limiter worker paused, waiting {wait_time:.1f}s more..."
                    )
                    await asyncio.sleep(wait_time)

                # Wait for rate limit capacity
                async with self.limiter:
                    try:
                        result = await func()
                        for f in futures:
                            if not f.done():
                                f.set_result(result)
                    except Exception as exc:
                        # Report error to all futures and log it
                        for f in futures:
                            if not f.done():
                                f.set_exception(exc)

                        error_msg = str(exc).lower()
                        if "flood" in error_msg or "wait" in error_msg:
                            seconds = 30
                            try:
                                if hasattr(exc, "seconds"):
                                    seconds = exc.seconds  # type: ignore[attr-defined]
                                elif "after " in error_msg:
                                    # Try to parse "retry after X"
                                    parts = error_msg.split("after ")
                                    if len(parts) > 1:
                                        seconds = int(parts[1].split()[0])
                            except Exception:
                                pass

                            logger.error(
                                f"FloodWait detected! Pausing worker for {seconds}s"
                            )
                            wait_secs = (
                                float(seconds)
                                if isinstance(seconds, (int, float, str))
                                else 30.0
                            )
                            self._paused_until = (
                                asyncio.get_event_loop().time() + wait_secs
                            )
                        else:
                            d = get_settings().log_messaging_error_details
                            logger.error(
                                "Error in limiter worker for key {}: {}",
                                dedup_key,
                                format_exception_for_log(exc, log_full_message=d),
                            )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                d = get_settings().log_messaging_error_details
                if d:
                    logger.error(
                        "MessagingRateLimiter worker critical error: {}",
                        exc,
                        exc_info=True,
                    )
                else:
                    logger.error(
                        "MessagingRateLimiter worker critical error: exc_type={}",
                        type(exc).__name__,
                    )
                await asyncio.sleep(1)

    async def shutdown(self, timeout: float = 2.0) -> None:
        """Stop the background worker so process shutdown doesn't hang."""
        self._shutdown.set()
        try:
            async with self._condition:
                self._condition.notify_all()
        except Exception:
            # Best-effort: condition may be bound to a closing loop.
            pass

        task = self._worker_task
        if not task or task.done():
            self._worker_task = None
            return

        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except TimeoutError:
            logger.warning("MessagingRateLimiter worker did not stop before timeout")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            d = get_settings().log_messaging_error_details
            logger.debug(
                "MessagingRateLimiter worker shutdown error: {}",
                format_exception_for_log(exc, log_full_message=d),
            )
        finally:
            self._worker_task = None

    async def _enqueue_internal(self, func, future, dedup_key, front=False):
        await self._enqueue_internal_multi(func, [future], dedup_key, front)

    async def _enqueue_internal_multi(self, func, futures, dedup_key, front=False):
        async with self._condition:
            if dedup_key in self._queue_map:
                # Compaction: Update existing task with new func, append new futures
                _old_func, old_futures = self._queue_map[dedup_key]
                old_futures.extend(futures)
                self._queue_map[dedup_key] = (func, old_futures)
                logger.debug(
                    f"Compacted task for key: {dedup_key} (now {len(old_futures)} futures)"
                )
            else:
                self._queue_map[dedup_key] = (func, futures)
                if front:
                    self._queue_list.appendleft(dedup_key)
                else:
                    self._queue_list.append(dedup_key)
                self._condition.notify_all()

    async def enqueue(
        self, func: Callable[[], Awaitable[Any]], dedup_key: str | None = None
    ) -> Any:
        """
        Enqueue a messaging task and return its future result.
        If dedup_key is provided, subsequent tasks with the same key will replace this one.
        """
        if dedup_key is None:
            # Unique key to avoid deduplication
            dedup_key = f"task_{id(func)}_{asyncio.get_event_loop().time()}"

        future = asyncio.get_event_loop().create_future()
        await self._enqueue_internal(func, future, dedup_key)
        return await future

    def fire_and_forget(
        self, func: Callable[[], Awaitable[Any]], dedup_key: str | None = None
    ):
        """Enqueue a task without waiting for the result."""
        if dedup_key is None:
            dedup_key = f"task_{id(func)}_{asyncio.get_event_loop().time()}"

        future = asyncio.get_event_loop().create_future()

        async def _wrapped():
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    return await self.enqueue(func, dedup_key)
                except Exception as exc:
                    error_msg = str(exc).lower()
                    # Only retry transient connectivity issues that might have slipped through
                    # or occurred between platform checks.
                    if attempt < max_retries and any(
                        x in error_msg for x in ["connect", "timeout", "broken"]
                    ):
                        wait = 2**attempt
                        d = get_settings().log_messaging_error_details
                        if d:
                            logger.warning(
                                "Limiter fire_and_forget transient error (attempt {}): {}. Retrying in {}s...",
                                attempt + 1,
                                exc,
                                wait,
                            )
                        else:
                            logger.warning(
                                "Limiter fire_and_forget transient error (attempt {}): exc_type={}. Retrying in {}s...",
                                attempt + 1,
                                type(exc).__name__,
                                wait,
                            )
                        await asyncio.sleep(wait)
                        continue

                    d = get_settings().log_messaging_error_details
                    logger.error(
                        "Final error in fire_and_forget for key {}: {}",
                        dedup_key,
                        format_exception_for_log(exc, log_full_message=d),
                    )
                    if not future.done():
                        future.set_exception(exc)
                    break

        _ = asyncio.create_task(_wrapped())


@cache
def get_messaging_rate_limiter(
    rate_limit: int = 1,
    rate_window: float = 1.0,
) -> MessagingRateLimiter:
    """Return the canonical production rate-limiter instance (cached by arguments).

    Patching this function (e.g. with ``unittest.mock.patch``) lets tests
    supply an isolated :class:`MessagingRateLimiter` without affecting other
    tests.
    """
    return MessagingRateLimiter(rate_limit=rate_limit, rate_window=rate_window)
