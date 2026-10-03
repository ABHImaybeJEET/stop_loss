"""Per-source flow control; cancellation always propagates to the caller."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from fin_terminal.config import Settings

T = TypeVar("T")


class RateLimitedError(Exception):
    pass


class CircuitOpenError(Exception):
    pass


class TokenBucket:
    def __init__(self, rate: float, capacity: int = 1) -> None:
        if rate <= 0 or capacity < 1:
            raise ValueError("rate must be positive and capacity at least one")
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                delay = (1 - self.tokens) / self.rate
            await asyncio.sleep(delay)


class CircuitBreaker:
    def __init__(self, threshold: int = 3, reset_seconds: float = 60) -> None:
        if threshold < 1 or reset_seconds <= 0:
            raise ValueError("threshold and reset_seconds must be positive")
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.opened_at: float | None = None
        self.probing = False

    def check(self) -> None:
        if self.opened_at is None:
            return
        if self.probing or time.monotonic() - self.opened_at < self.reset_seconds:
            raise CircuitOpenError("source circuit is open")
        self.probing = True

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None
        self.probing = False

    def failure(self) -> None:
        self.failures += 1
        if self.probing or self.failures >= self.threshold:
            self.opened_at = time.monotonic()
        self.probing = False

    def cancel_probe(self) -> None:
        self.probing = False


class TTLCache(Generic[T]):
    """Bounded cache; expiry and eviction never turn absent data into a value."""

    def __init__(self, ttl_seconds: float, max_entries: int = 256) -> None:
        if ttl_seconds <= 0 or max_entries < 1:
            raise ValueError("ttl_seconds and max_entries must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._values: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        item = self._values.get(key)
        if item is None:
            return None
        expiry, value = item
        if expiry <= time.monotonic():
            del self._values[key]
            return None
        return value

    def put(self, key: str, value: T) -> None:
        now = time.monotonic()
        self._values = {k: v for k, v in self._values.items() if v[0] > now and k != key}
        if len(self._values) >= self.max_entries:
            del self._values[next(iter(self._values))]
        self._values[key] = (now + self.ttl_seconds, value)


def is_transient(exc: BaseException) -> bool:
    return (
        isinstance(exc, (RateLimitedError, httpx.TransportError, TimeoutError))
        or isinstance(exc, httpx.HTTPStatusError)
        and (exc.response.status_code == 429 or exc.response.status_code >= 500)
    )


class SourceGuard:
    def __init__(self, settings: Settings) -> None:
        self.bucket = TokenBucket(settings.source_rate_per_second, settings.source_burst)
        self.breaker = CircuitBreaker(
            settings.circuit_failure_threshold, settings.circuit_reset_seconds
        )
        self.attempts = settings.retry_attempts
        self.max_wait = settings.retry_max_wait_seconds
        self.timeout = settings.http_timeout_seconds

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        self.breaker.check()
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.attempts),
                wait=wait_random_exponential(multiplier=0.25, max=self.max_wait),
                retry=retry_if_exception(is_transient),
                reraise=True,
            ):
                with attempt:
                    await self.bucket.acquire()
                    async with asyncio.timeout(self.timeout):
                        result = await operation()
                    self.breaker.success()
                    return result
        except asyncio.CancelledError:
            self.breaker.cancel_probe()
            raise
        except Exception:
            self.breaker.failure()
            raise
        raise RuntimeError("retry loop ended without a result")


class SourceGuards:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sources: dict[str, SourceGuard] = {}

    def for_source(self, source: str) -> SourceGuard:
        if source not in self._sources:
            self._sources[source] = SourceGuard(self.settings)
        return self._sources[source]
