from abc import ABC, abstractmethod

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
