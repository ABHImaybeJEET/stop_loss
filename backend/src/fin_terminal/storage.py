"""Durable content-hash dedupe. Mark complete only after vector upsert succeeds."""

import sqlite3
from pathlib import Path

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

    def contains(self, content_hash: str) -> bool:
        return (
            self.connection.execute(
                "SELECT 1 FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            is not None
        )

    def insert(self, document: Document) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO documents VALUES (?, ?)",
                (document.content_hash, document.model_dump_json()),
            )

    def close(self) -> None:
        self.connection.close()
