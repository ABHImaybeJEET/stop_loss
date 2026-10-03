from pydantic import JsonValue

from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.connectors.errors import UnavailableError
from fin_terminal.schemas import Document, StreamStatus


class UnavailableConnector(AsyncConnector):
    def __init__(self, source: str) -> None:
        self._source = source

    @property
    def source(self) -> str:
        return self._source

    async def fetch(self) -> list[JsonValue]:
        raise UnavailableError()

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        return []

    async def health(self) -> StreamStatus:
        return StreamStatus(
            source=self.source, status="failed", message="unavailable: missing configuration"
        )
