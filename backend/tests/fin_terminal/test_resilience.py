import asyncio

import httpx
import pytest

from fin_terminal import resilience
from fin_terminal.config import Settings
from fin_terminal.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    RateLimitedError,
    SourceGuards,
    TokenBucket,
    TTLCache,
)


def test_bucket_waits_without_holding_lock_and_sources_are_independent(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
):
    now = [0.0]
    delays = []
    monkeypatch.setattr(resilience.time, "monotonic", lambda: now[0])

    async def sleep(delay):
        delays.append(delay)
        now[0] += delay

    monkeypatch.setattr(resilience.asyncio, "sleep", sleep)
    guards = SourceGuards(settings)
    assert guards.for_source("a") is guards.for_source("a")
    assert guards.for_source("a") is not guards.for_source("b")

    async def exercise():
        bucket = TokenBucket(rate=2, capacity=1)
        await bucket.acquire()
        await bucket.acquire()
        assert delays == [0.5]

    asyncio.run(exercise())


def test_circuit_opens_allows_single_probe_and_recovers(monkeypatch: pytest.MonkeyPatch):
    now = [0.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: now[0])
    breaker = CircuitBreaker(threshold=2, reset_seconds=10)
    breaker.failure()
    breaker.check()
    breaker.failure()
    with pytest.raises(CircuitOpenError):
        breaker.check()
    now[0] = 11
    breaker.check()
    with pytest.raises(CircuitOpenError):
        breaker.check()
    breaker.failure()
    with pytest.raises(CircuitOpenError):
        breaker.check()
    now[0] = 22
    breaker.check()
    breaker.success()
    breaker.check()
    assert breaker.failures == 0


def test_cache_expiry_and_bounded_eviction(monkeypatch: pytest.MonkeyPatch):
    now = [0.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: now[0])
    cache = TTLCache[int](5, max_entries=2)
    cache.put("a", 0)
    assert cache.get("a") == 0
    cache.put("b", 1)
    cache.put("c", 2)
    assert cache.get("a") is None
    now[0] = 6
    assert cache.get("b") is None
    assert cache.get("c") is None


def test_retry_transient_but_not_auth_or_invalid_response(settings: Settings):
    async def exercise():
        calls = 0

        async def transient():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RateLimitedError()
            return "ok"

        guards = SourceGuards(settings)
        assert await guards.for_source("a").call(transient) == "ok"
        assert calls == 3
        calls = 0

        async def authentication_failure():
            nonlocal calls
            calls += 1
            response = httpx.Response(401, request=httpx.Request("GET", "https://example.invalid"))
            response.raise_for_status()

        with pytest.raises(httpx.HTTPStatusError):
            await guards.for_source("b").call(authentication_failure)
        assert calls == 1

    asyncio.run(exercise())


def test_cancellation_does_not_count_as_failure(settings: Settings):
    async def exercise():
        guard = SourceGuards(settings).for_source("a")

        async def cancel():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await guard.call(cancel)
        assert guard.breaker.failures == 0

    asyncio.run(exercise())
