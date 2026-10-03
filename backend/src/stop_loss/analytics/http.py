"""Shared resilient HTTP access: token bucket + retry/backoff + circuit breaker + TTL cache."""

from typing import Any

import httpx

from fin_terminal.config import Settings
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.resilience import RateLimitedError, SourceGuard, TTLCache

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


class GuardedHTTP:
    """One provider's pooled client. Every request goes through the provider's SourceGuard."""

    def __init__(
        self,
        settings: Settings,
        *,
        rate_per_second: float,
        burst: int = 4,
        client: httpx.AsyncClient | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        guarded = settings.model_copy(
            update={"source_rate_per_second": rate_per_second, "source_burst": burst}
        )
        self.guard = SourceGuard(guarded)
        self.timeout = settings.http_timeout_seconds
        self._owns = client is None
        self.client = client or httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": BROWSER_UA, **(headers or {})},
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=8),
        )

    async def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def request() -> httpx.Response:
            try:
                response = await self.client.get(url, params=params)
            except httpx.TransportError as exc:
                raise ConnectorError(type(exc).__name__, retryable=True) from None
            if response.status_code == 429:
                raise RateLimitedError("provider_rate_limited")
            if response.status_code >= 500:
                raise ConnectorError(f"http_{response.status_code}", retryable=True)
            return response

        return await self.guard.call(request)

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self.get(url, params)
        try:
            data = response.json()
        except ValueError:
            raise ConnectorError("invalid_json") from None
        if not isinstance(data, dict):
            raise ConnectorError("invalid_envelope")
        return data

    async def aclose(self) -> None:
        if self._owns:
            await self.client.aclose()


class Cached:
    """Small async memoizer on top of the ingestion TTLCache."""

    def __init__(self, ttl_seconds: float, max_entries: int = 512) -> None:
        self._cache: TTLCache[Any] = TTLCache(ttl_seconds, max_entries)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def put(self, key: str, value: Any) -> None:
        self._cache.put(key, value)
