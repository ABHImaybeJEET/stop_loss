from abc import ABC, abstractmethod

from fin_terminal.schemas import Document


class VectorStoreAdapter(ABC):
    """Caller supplies vectors; adapters use stable content-derived IDs."""

    @abstractmethod
    async def upsert(self, document: Document, vector: list[float]) -> None: ...

    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...
