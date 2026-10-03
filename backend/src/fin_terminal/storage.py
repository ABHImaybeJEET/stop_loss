"""Durable content-hash dedupe. Mark complete only after vector upsert succeeds."""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock

from fin_terminal.schemas import Document


class DocumentStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS documents "
            "(content_hash TEXT PRIMARY KEY, document_json TEXT NOT NULL)"
        )
        self.connection.commit()
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingestion-sqlite")

    def contains(self, content_hash: str) -> bool:
        return (
            self.connection.execute(
                "SELECT 1 FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            is not None
        )

    def insert(self, document: Document) -> bool:
        with self._lock, self.connection:
            cursor = self.connection.execute(
                "INSERT OR IGNORE INTO documents VALUES (?, ?)",
                (document.content_hash, document.model_dump_json()),
            )
            return cursor.rowcount == 1

    def missing(self, content_hashes: list[str]) -> set[str]:
        """Subset of hashes not stored yet (bulk dedupe for backfills)."""
        found: set[str] = set()
        for start in range(0, len(content_hashes), 500):
            chunk = content_hashes[start : start + 500]
            marks = ",".join("?" * len(chunk))
            rows = self.connection.execute(
                f"SELECT content_hash FROM documents WHERE content_hash IN ({marks})", chunk
            ).fetchall()
            found.update(row[0] for row in rows)
        return set(content_hashes) - found

    def insert_many(self, documents: list[Document]) -> int:
        """One transaction for a whole batch; call only after the vector upsert succeeded."""
        with self._lock, self.connection:
            cursor = self.connection.executemany(
                "INSERT OR IGNORE INTO documents VALUES (?, ?)",
                [(d.content_hash, d.model_dump_json()) for d in documents],
            )
            return cursor.rowcount

    def delete_run(self, ingest_run_id: str) -> int:
        """Forget every document written by one ingest run (e.g. before a re-index)."""
        with self._lock, self.connection:
            cursor = self.connection.execute(
                "DELETE FROM documents WHERE json_extract(document_json, '$.ingest_run_id') = ?",
                (ingest_run_id,),
            )
            return cursor.rowcount

    async def acontains(self, content_hash: str) -> bool:
        return await asyncio.get_running_loop().run_in_executor(
            self._executor, self.contains, content_hash
        )

    async def ainsert(self, document: Document) -> bool:
        return await asyncio.get_running_loop().run_in_executor(
            self._executor, self.insert, document
        )

    async def aclose(self) -> None:
        await asyncio.get_running_loop().run_in_executor(self._executor, self.connection.close)
        self._executor.shutdown(wait=False)

    def close(self) -> None:
        self._executor.shutdown(wait=True)
        self.connection.close()
