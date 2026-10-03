import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import JsonValue

from fin_terminal.schemas import Document, StreamStatus


class AsyncConnector(ABC):
    """A source owns fetch/normalization/health, never graph orchestration.

    normalize must preserve source timestamps and missing values. The graph owns
    run IDs, fetch timing, retries, tagging, persistence and evidence.
    """

    @property
    @abstractmethod
    def source(self) -> str: ...

    @abstractmethod
    async def fetch(self) -> list[JsonValue]: ...

    @abstractmethod
    async def normalize(self, raw: list[JsonValue]) -> list[Document]: ...

    @abstractmethod
    async def health(self) -> StreamStatus: ...

    async def connect(self) -> None:
        """Acquire resources lazily; compatibility default for injected connectors."""
        return None

    async def health_check(self) -> StreamStatus:
        return await self.health()

    async def stream(self, poll_seconds: float = 1.0) -> AsyncIterator[list[JsonValue]]:
        """Polling sources share the same cancellable stream interface as sockets."""
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        await self.connect()
        while True:
            yield await self.fetch()
            await asyncio.sleep(poll_seconds)

    async def close(self) -> None:
        """Release owned resources; injected clients remain caller-owned."""
        return None
