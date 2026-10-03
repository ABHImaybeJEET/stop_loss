from pydantic import JsonValue

from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.resilience import RateLimitedError
from fin_terminal.schemas import Document, StreamHealth, StreamStatus


class StubConnector(AsyncConnector):
    """Explicitly empty source: no manufactured market observations."""

    def __init__(self, source: str, failure: StreamHealth | None = None) -> None:
        self._source = source
        self.failure = failure

    @property
    def source(self) -> str:
        return self._source

    async def fetch(self) -> list[JsonValue]:
        if self.failure == "rate_limited":
            raise RateLimitedError("forced stub rate limit")
        if self.failure == "failed":
            raise RuntimeError("forced stub failure")
        return []

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        return []

    async def health(self) -> StreamStatus:
        return StreamStatus(
            source=self.source,
            status="degraded" if self.failure == "degraded" else "ok",
            message="stub: no live data fetched",
        )
