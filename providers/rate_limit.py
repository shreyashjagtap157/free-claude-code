"""Global rate limiter with circuit breaker for API requests."""

import asyncio
import enum
import random
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any, ClassVar, TypeVar

import httpx
import openai
import tenacity
from loguru import logger

from core.rate_limit import TokenBucketRateLimiter
from core.trace import trace_event

T = TypeVar("T")


# =============================================================================
# Circuit Breaker — fail-fast when upstream is degraded
# =============================================================================


class CircuitState(enum.Enum):
    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"  # Degraded — requests fail-fast, no upstream call
    HALF_OPEN = "half_open"  # Recovery probe — limited requests allowed


class CircuitBreaker:
    """Per-provider circuit breaker for fail-fast upstream degradation.

    Tracks consecutive failures. When the threshold is exceeded, the
    circuit opens and new requests fail immediately without calling
    the upstream. After a recovery timeout, the circuit transitions to
    half-open, allowing a limited number of probe requests. If probes
    succeed, the circuit resets to closed; a single failure re-opens it.

    Thread-safe for the asyncio event loop (all access from one thread).
    """

    def __init__(
        self,
        scope: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 3,
    ):
        self._scope = scope
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_requests = half_open_max_requests
        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._opened_at: float = 0.0  # monotonic time when circuit opened
        self._half_open_requests: int = 0
        self._half_open_successes: int = 0

    @property
    def state(self) -> CircuitState:
        """Return the current effective state.

        Transitions from OPEN to HALF_OPEN automatically when the recovery
        timeout has elapsed.
        """
        if self._state == CircuitState.OPEN and self._is_recovery_due():
            self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def recovery_timeout(self) -> float:
        return self._recovery_timeout

    def _is_recovery_due(self) -> bool:
        return (time.monotonic() - self._opened_at) >= self._recovery_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        logger.warning(
            "CircuitBreaker[{}] state transition: {} -> {}",
            self._scope,
            old_state.value,
            new_state.value,
        )
        trace_event(
            stage="provider",
            event="provider.circuit_breaker.transition",
            source="provider",
            provider=self._scope,
            old_state=old_state.value,
            new_state=new_state.value,
            consecutive_failures=self._consecutive_failures,
        )
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
        elif new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._half_open_requests = 0
            self._half_open_successes = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_requests = 0
            self._half_open_successes = 0

    def _is_half_open_exhausted(self) -> bool:
        """Return True when the half-open probe limit has been reached."""
        return self._half_open_requests >= self._half_open_max_requests

    def may_proceed(self) -> bool:
        """Check whether the caller may attempt an upstream request.

        Returns ``False`` when the circuit is open (fail-fast). In
        half-open state, returns ``True`` for probe requests up to
        ``half_open_max_requests``, then ``False``.
        """
        effective_state = self.state  # triggers OPEN -> HALF_OPEN transition
        if effective_state == CircuitState.CLOSED:
            return True
        if effective_state == CircuitState.OPEN:
            return False
        # Half-open: allow up to half_open_max_requests probe requests.
        if self._is_half_open_exhausted():
            return False
        self._half_open_requests += 1
        return True

    def on_success(self) -> None:
        """Report a successful upstream call.

        In CLOSED state: resets consecutive failure counter. In HALF_OPEN
        state: increments success counter. When enough consecutive probes
        succeed, transitions back to CLOSED.
        """
        if self._state == CircuitState.CLOSED:
            self._consecutive_failures = 0
        elif self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            # Require all probe requests to succeed before closing.
            if self._half_open_successes >= self._half_open_max_requests:
                self._transition_to(CircuitState.CLOSED)
        # OPEN state does not call on_success (requests are blocked upstream).

    def on_failure(self) -> None:
        """Report an upstream failure.

        Increments consecutive failure counter. When threshold is
        exceeded, transitions to OPEN (or re-opens if already HALF_OPEN).
        """
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._transition_to(CircuitState.OPEN)


class CircuitBreakerOpenError(Exception):
    """Raised when a request is rejected by an open circuit breaker.

    The upstream provider is degraded and the circuit is open; callers
    should fail fast rather than retrying. The circuit will automatically
    transition to half-open after the recovery timeout.
    """

    def __init__(self, scope: str, retry_after: float) -> None:
        self.scope = scope
        self.retry_after = retry_after
        super().__init__(
            f"Provider '{scope}' circuit breaker is open; "
            f"retry after {retry_after:.0f}s"
        )


def _upstream_http_retryable(code: int) -> bool:
    """True for rate limit / upstream server failures that should backoff-retry."""
    return code == 429 or code == 408 or 500 <= code <= 599


def retryable_upstream_status(exc: BaseException) -> int | None:
    """Return HTTP-like status codes that qualify for reactive backoff retries.

    ``429`` plus any upstream ``5xx`` use the same exponential backoff and scoped
    limiter blocking semantics as today's rate-limit path.
    """
    if isinstance(exc, openai.RateLimitError):
        return 429
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if _upstream_http_retryable(status):
            return status
        return None
    if isinstance(exc, openai.APIError):
        status = getattr(exc, "status_code", None)
        if isinstance(status, int) and 500 <= status <= 599:
            return status
    if isinstance(exc, (httpx.TimeoutException, openai.APITimeoutError)):
        return 408
    return None


class GlobalRateLimiter:
    """
    Global singleton rate limiter that blocks all requests
    when a rate limit error is encountered (reactive) and
    throttles requests (proactive) using a strict rolling window.

    Optionally enforces a max_concurrency cap: at most N provider streams
    may be open simultaneously, independent of the sliding window.

    Proactive limits - throttles requests to stay within API limits.
    Reactive limits - pauses all requests when a 429 or 5xx retry backoff is active.
    Concurrency limit - caps simultaneously open streams.
    """

    _instance: ClassVar[GlobalRateLimiter | None] = None
    _scoped_instances: ClassVar[dict[str, GlobalRateLimiter]] = {}

    def __init__(
        self,
        rate_limit: int = 40,
        rate_window: float = 60.0,
        max_concurrency: int = 3,
        *,
        scope: str = "default",
    ):
        # Prevent re-initialization on singleton reuse
        if hasattr(self, "_initialized"):
            return

        if rate_limit <= 0:
            raise ValueError("rate_limit must be > 0")
        if rate_window <= 0:
            raise ValueError("rate_window must be > 0")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be > 0")

        self._rate_limit = rate_limit
        self._rate_window = float(rate_window)
        self._max_concurrency = max_concurrency
        self._proactive_limiter = TokenBucketRateLimiter(
            self._rate_limit, self._rate_window
        )
        self._blocked_until: float = 0
        self._concurrency_sem = asyncio.Semaphore(max_concurrency)
        self._circuit_breaker = CircuitBreaker(scope)
        self._initialized = True

        logger.info(
            f"GlobalRateLimiter (Provider) initialized ({rate_limit} req / {rate_window}s, max_concurrency={max_concurrency})"
        )

    @classmethod
    def get_instance(
        cls,
        rate_limit: int | None = None,
        rate_window: float | None = None,
        max_concurrency: int = 3,
    ) -> GlobalRateLimiter:
        """Get or create the singleton instance.

        Args:
            rate_limit: Requests per window (only used on first creation)
            rate_window: Window in seconds (only used on first creation)
            max_concurrency: Max simultaneous open streams (only used on first creation)
        """
        if cls._instance is None:
            cls._instance = cls(
                rate_limit=rate_limit or 40,
                rate_window=rate_window or 60.0,
                max_concurrency=max_concurrency,
            )
        return cls._instance

    @classmethod
    def get_scoped_instance(
        cls,
        scope: str,
        *,
        rate_limit: int | None = None,
        rate_window: float | None = None,
        max_concurrency: int = 3,
    ) -> GlobalRateLimiter:
        """Get or create a provider-scoped limiter instance."""
        if not scope:
            raise ValueError("scope must be non-empty")
        desired_rate_limit = rate_limit or 40
        desired_rate_window = float(rate_window or 60.0)
        existing = cls._scoped_instances.get(scope)
        if existing and existing.matches_config(
            desired_rate_limit, desired_rate_window, max_concurrency
        ):
            return existing
        if existing:
            logger.info(
                "Rebuilding provider rate limiter for updated scope '{}'", scope
            )
        cls._scoped_instances[scope] = cls(
            rate_limit=desired_rate_limit,
            rate_window=desired_rate_window,
            max_concurrency=max_concurrency,
            scope=scope,
        )
        return cls._scoped_instances[scope]

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
        cls._scoped_instances = {}

    async def wait_if_blocked(self) -> bool:
        """
        Wait if currently rate limited or throttle to meet quota.

        Returns:
            True if was reactively blocked and waited, False otherwise.
        """
        # 1. Reactive check: Wait if someone hit a reactive backoff (429/5xx retries)
        waited_reactively = False
        now = time.monotonic()
        if now < self._blocked_until:
            wait_time = self._blocked_until - now
            logger.warning(
                f"Global provider rate limit active (reactive), waiting {wait_time:.1f}s..."
            )
            await asyncio.sleep(wait_time)
            waited_reactively = True

        # 2. Proactive check: strict rolling window (no bursts beyond N in last W seconds)
        await self._acquire_proactive_slot()
        return waited_reactively

    async def _acquire_proactive_slot(self) -> None:
        """
        Acquire a proactive slot enforcing a strict rolling window.

        Guarantees: at most `self._rate_limit` acquisitions in any interval of length
        `self._rate_window` (seconds).
        """
        await self._proactive_limiter.acquire()

    def set_blocked(self, seconds: float = 60) -> None:
        """
        Set global block for specified seconds (reactive).

        Args:
            seconds: How long to block (default 60s)
        """
        self._blocked_until = time.monotonic() + seconds
        logger.warning(f"Global provider rate limit set for {seconds:.1f}s (reactive)")

    def set_blocked_from_response(
        self, seconds: int = 60, *, response: httpx.Response | None = None
    ) -> None:
        """
        Set global block, preferring ``Retry-After`` header from *response*.

        Args:
            seconds: Default block duration if no header or header unparseable.
            response: Optional HTTP response whose ``Retry-After`` header is used
                      instead of *seconds* when present and parseable.
        """
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                with suppress(ValueError, TypeError):
                    seconds = int(retry_after)
        self.set_blocked(seconds)

    def is_blocked(self) -> bool:
        """Check if currently reactively blocked."""
        return time.monotonic() < self._blocked_until

    def matches_config(
        self, rate_limit: int, rate_window: float, max_concurrency: int
    ) -> bool:
        """Return whether this limiter matches the requested runtime config."""
        return (
            self._rate_limit == rate_limit
            and self._rate_window == float(rate_window)
            and self._max_concurrency == max_concurrency
        )

    def remaining_wait(self) -> float:
        """Get remaining reactive wait time in seconds."""
        return max(0.0, self._blocked_until - time.monotonic())

    @asynccontextmanager
    async def concurrency_slot(self) -> AsyncIterator[None]:
        """Async context manager that holds one concurrency slot for a stream.

        Blocks until a slot is available (controlled by max_concurrency).
        """
        await self._concurrency_sem.acquire()
        try:
            yield
        finally:
            self._concurrency_sem.release()

    async def execute_with_retry(
        self,
        fn: Callable[..., Any],
        *args: Any,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        jitter: float = 1.0,
        **kwargs: Any,
    ) -> Any:
        """Execute an async callable with rate limiting, circuit breaker, and tenacity retry.

        Before the first attempt, checks the circuit breaker. If the circuit is open,
        raises :exc:`CircuitBreakerOpenError` immediately (fail-fast). Otherwise,
        waits for the proactive limiter and executes the callable.

        On ``429`` (rate limit) or upstream ``5xx`` server errors, uses tenacity's
        declarative retry with exponential backoff and jitter, sets the reactive
        block, and retries.

        On success, reports success to the circuit breaker (may reset the failure
        counter and transition back to CLOSED from HALF_OPEN).

        Args:
            fn: Async callable to execute.
            max_retries: Maximum number of retry attempts after the first failure.
            base_delay: Base delay in seconds for exponential backoff.
            max_delay: Maximum delay cap in seconds.
            jitter: Maximum random jitter in seconds added to each delay.

        Returns:
            The result of the callable.

        Raises:
            CircuitBreakerOpenError: When the circuit is open (fail-fast).
            The last exception from the callable if all retries are exhausted.
        """
        # Circuit breaker: fail-fast when the upstream is degraded.
        if not self._circuit_breaker.may_proceed():
            raise CircuitBreakerOpenError(
                scope=self._circuit_breaker.scope,
                retry_after=self._circuit_breaker.recovery_timeout,
            )

        max_attempts = 1 + max_retries
        retrier = tenacity.AsyncRetrying(
            stop=tenacity.stop_after_attempt(max_attempts),
            wait=tenacity.wait_exponential(
                multiplier=base_delay, min=base_delay, max=max_delay
            )
            + tenacity.wait_random(0, jitter),
            retry=tenacity.retry_if_exception(
                lambda e: retryable_upstream_status(e) is not None
            ),
            reraise=True,
            before_sleep=self._make_before_retry_callback(
                base_delay, max_delay, jitter, max_attempts
            ),
        )

        try:
            async for attempt in retrier:
                with attempt:
                    await self.wait_if_blocked()
                    result = await fn(*args, **kwargs)
                    self._circuit_breaker.on_success()
                    return result
        except Exception:
            self._circuit_breaker.on_failure()
            raise

    def _make_before_retry_callback(
        self,
        base_delay: float,
        max_delay: float,
        jitter: float,
        max_attempts: int,
    ) -> Callable:
        """Build the ``before_sleep`` callback for tenacity retry logging.

        Called by tenacity before each retry sleep to log the attempt and
        set the reactive block from the upstream response (``Retry-After``).
        """

        def _before_sleep(retry_state: tenacity.RetryCallState) -> None:
            attempt = retry_state.attempt_number
            outcome = retry_state.outcome
            if outcome is None:
                return
            exc = outcome.exception()
            if exc is None:
                return
            status = retryable_upstream_status(exc)
            if status is None:
                return

            label = (
                "Rate limited (429)"
                if status == 429
                else f"Upstream server error ({status})"
            )
            response = getattr(exc, "response", None)
            # Replicate the same exponential backoff formula for logging clarity.
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay += random.uniform(0, jitter)

            logger.warning(
                "{}, attempt {}/{}. Retrying in {:.2f}s...",
                label,
                attempt,
                max_attempts,
                delay,
            )
            trace_event(
                stage="provider",
                event="provider.retry.scheduled",
                source="provider",
                status_code=status,
                attempt=attempt,
                max_attempts=max_attempts,
                delay_s=round(delay, 3),
            )
            # Prefer Retry-After header when available (PRV-01)
            self.set_blocked_from_response(int(delay), response=response)

        return _before_sleep
