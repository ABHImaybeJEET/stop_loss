"""Long-lived pools and resilience at each HTTP request, not at batch boundaries."""

import asyncio
from typing import Any

import httpx

from fin_terminal.config import Settings
from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.resilience import RateLimitedError, SourceGuard, TokenBucket
from fin_terminal.schemas import StreamStatus


class HTTPConnector(AsyncConnector):
    provider = "http"
    manages_requests = True

    def setup_http(self, settings: Settings, bucket: TokenBucket | None = None) -> None:
        policy = settings.connector_policy(self.provider)
        self.timeout = policy.timeout_seconds
        guarded = settings.model_copy(
            update={
                "http_timeout_seconds": policy.timeout_seconds,
                "source_rate_per_second": policy.rate_per_second,
                "source_burst": policy.burst,
                "retry_attempts": policy.retries,
            }
        )
        self._guard = SourceGuard(guarded)
        self._guard.semaphore = asyncio.Semaphore(policy.concurrency)
        if bucket is not None:
            self._guard.bucket = bucket

    async def connect(self) -> None:
        if not hasattr(self, "_guard"):
            self.setup_http(Settings(_env_file=None, http_timeout_seconds=self.timeout))
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            )
            self._owns_client = True

    async def request_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        await self.connect()

        async def request() -> dict[str, Any]:
            try:
                response = await self._client.get(url, params=params, timeout=self.timeout)
                if response.status_code == 429:
                    raise RateLimitedError("provider_rate_limited")
                if response.status_code >= 400:
                    raise ConnectorError(
                        f"http_{response.status_code}", retryable=response.status_code >= 500
                    )
                data = response.json()
                if not isinstance(data, dict):
                    raise ConnectorError("invalid_envelope")
                note = str(data.get("Note") or data.get("Information") or "")
                if note:
                    if any(term in note.lower() for term in ("rate", "frequency", "api call")):
                        raise RateLimitedError("provider_rate_limited")
                    raise ConnectorError("provider_information_error")
                if "Error Message" in data or "error_code" in data or data.get("error"):
                    raise ConnectorError("provider_error")
                return data
            except httpx.TransportError as exc:
                raise ConnectorError(type(exc).__name__, retryable=True) from None
            except ValueError:
                raise ConnectorError("invalid_json") from None

        try:
            result = await self._guard.call(request)
        except Exception as exc:
            self._last_health = StreamStatus(
                source=self.source,
                status="rate_limited" if isinstance(exc, RateLimitedError) else "failed",
                message=type(exc).__name__,
            )
            raise
        self._last_health = StreamStatus(source=self.source, status="ok")
        return result

    async def health(self) -> StreamStatus:
        return getattr(
            self,
            "_last_health",
            StreamStatus(
                source=self.source,
                status="degraded",
                message="unavailable: no successful request yet",
            ),
        )

    async def close(self) -> None:
        if getattr(self, "_owns_client", False) and self._client is not None:
            await self._client.aclose()
            self._client = None
