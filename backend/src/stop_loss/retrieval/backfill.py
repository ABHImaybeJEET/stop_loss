"""Resumable bulk indexing of data/processed into the Pinecone history namespace.

Flow per chunk: dedupe by content_hash (SQLite) → batch-embed on GPU → concurrent
Pinecone upserts (retry/backoff) → mark stored → checkpoint the source line.
A record is only marked stored after its vector upsert succeeded, so a crash or
quota stop resumes without gaps; re-upserts are harmless (ids are content hashes).
"""

import asyncio
import logging
import sqlite3
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.storage import DocumentStore
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter, document_metadata
from stop_loss.retrieval.datasets import Record

logger = logging.getLogger("stop_loss.retrieval")
UPSERT_BATCH = 100
UPSERT_CONCURRENCY = 8
# fp16 GPU vectors carry ~3 significant digits; 5 decimals halves the JSON upload size.
VECTOR_DECIMALS = 5


@dataclass
class BackfillStats:
    source: str
    seen: int = 0
    skipped_existing: int = 0
    upserted: int = 0
    resumed_from_line: int = 0
    seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.upserted / self.seconds if self.seconds else 0.0


class Progress:
    """Last fully indexed source line per dataset (separate tiny SQLite file)."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS progress (source TEXT PRIMARY KEY, line INTEGER NOT NULL,"
            " upserted INTEGER NOT NULL, updated_at TEXT NOT NULL)"
        )
        self.conn.commit()

    def get(self, source: str) -> int:
        row = self.conn.execute("SELECT line FROM progress WHERE source=?", (source,)).fetchone()
        return int(row[0]) if row else 0

    def set(self, source: str, line: int, upserted: int) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO progress VALUES (?, ?, ?, datetime('now')) ON CONFLICT(source) DO "
                "UPDATE SET line=excluded.line, upserted=progress.upserted+excluded.upserted, "
                "updated_at=excluded.updated_at",
                (source, line, upserted),
            )

    def reset(self, source: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM progress WHERE source=?", (source,))

    def close(self) -> None:
        self.conn.close()


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError | TimeoutError)


class Backfill:
    def __init__(
        self,
        embedder: LazyEmbeddings,
        adapter: PineconeVectorAdapter,
        store: DocumentStore,
        progress: Progress,
        *,
        namespace: str,
        chunk_size: int = 1600,
    ) -> None:
        self.embedder = embedder
        self.adapter = adapter
        self.store = store
        self.progress = progress
        self.namespace = namespace
        self.chunk_size = chunk_size

    async def _upsert(self, items: list[tuple[str, list[float], dict]]) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(6),
            wait=wait_random_exponential(multiplier=0.5, max=30),
            retry=retry_if_exception(is_retryable),
            reraise=True,
        ):
            with attempt:
                await self.adapter.upsert_many(items, namespace=self.namespace)

    async def _flush(self, chunk: list[Record], stats: BackfillStats) -> None:
        new = self.store.missing([r.document.content_hash for r in chunk])
        fresh: dict[str, Record] = {}
        for record in chunk:  # also dedupes repeats inside the chunk
            if record.document.content_hash in new:
                fresh.setdefault(record.document.content_hash, record)
        stats.skipped_existing += len(chunk) - len(fresh)
        if not fresh:
            return
        records = list(fresh.values())
        vectors = await self.embedder.embed_batch([r.embed_text for r in records])
        items = [
            (
                r.document.content_hash,
                [round(x, VECTOR_DECIMALS) for x in v],
                document_metadata(r.document, **r.metadata),
            )
            for r, v in zip(records, vectors, strict=True)
        ]
        gate = asyncio.Semaphore(UPSERT_CONCURRENCY)

        async def send(batch: list[tuple[str, list[float], dict]]) -> None:
            async with gate:
                await self._upsert(batch)

        await asyncio.gather(
            *(send(items[i : i + UPSERT_BATCH]) for i in range(0, len(items), UPSERT_BATCH))
        )
        self.store.insert_many([r.document for r in records])
        stats.upserted += len(records)

    async def run(
        self,
        source: str,
        records: Iterator[Record],
        *,
        limit: int | None = None,
        on_progress: Callable[[BackfillStats], None] | None = None,
    ) -> BackfillStats:
        if not self.embedder.semantic or not await self._model_is_semantic():
            raise RuntimeError(
                "Refusing to index: no semantic embedding model loaded (install the "
                "'local-embeddings' extra)."
            )
        stats = BackfillStats(source=source, resumed_from_line=self.progress.get(source))
        started = time.perf_counter()
        chunk: list[Record] = []
        for record in records:
            if record.line <= stats.resumed_from_line:
                continue
            chunk.append(record)
            stats.seen += 1
            if len(chunk) >= self.chunk_size:
                await self._flush(chunk, stats)
                self.progress.set(source, chunk[-1].line, 0)
                chunk = []
                stats.seconds = time.perf_counter() - started
                if on_progress:
                    on_progress(stats)
            if limit is not None and stats.seen >= limit:
                break
        if chunk:
            await self._flush(chunk, stats)
            self.progress.set(source, chunk[-1].line, 0)
        stats.seconds = time.perf_counter() - started
        return stats

    async def _model_is_semantic(self) -> bool:
        await asyncio.to_thread(lambda: self.embedder.model)
        return self.embedder.semantic
