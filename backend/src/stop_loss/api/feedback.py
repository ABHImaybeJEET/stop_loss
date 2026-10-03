"""Feedback on analysis messages: SQLite (WAL), one editable row per user+message."""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

FeedbackTag = Literal[
    "Accurate", "Helpful", "Too vague", "Outdated data", "Wrong asset", "Risky advice"
]


class FeedbackIn(BaseModel):
    thread_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    rating: Literal["up", "down"]
    tags: list[FeedbackTag] = Field(default_factory=list, max_length=6)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackOut(FeedbackIn):
    created_at: str
    updated_at: str


class FeedbackStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS feedback (
                    user_id TEXT NOT NULL, message_id TEXT NOT NULL, thread_id TEXT NOT NULL,
                    rating TEXT NOT NULL, tags TEXT NOT NULL, comment TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, message_id))"""
            )
            self._conn.commit()

    def upsert(self, user_id: str, item: FeedbackIn) -> FeedbackOut:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, message_id) DO UPDATE SET rating=excluded.rating,
                   tags=excluded.tags, comment=excluded.comment, updated_at=excluded.updated_at""",
                (
                    user_id,
                    item.message_id,
                    item.thread_id,
                    item.rating,
                    json.dumps(item.tags),
                    item.comment,
                    now,
                    now,
                ),
            )
            self._conn.commit()
        found = self.get(user_id, item.message_id)
        assert found is not None
        return found

    def get(self, user_id: str, message_id: str) -> FeedbackOut | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT thread_id, message_id, rating, tags, comment, created_at, updated_at "
                "FROM feedback WHERE user_id=? AND message_id=?",
                (user_id, message_id),
            ).fetchone()
        if row is None:
            return None
        return FeedbackOut(
            thread_id=row[0],
            message_id=row[1],
            rating=row[2],
            tags=json.loads(row[3]),
            comment=row[4],
            created_at=row[5],
            updated_at=row[6],
        )

    def delete(self, user_id: str, message_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM feedback WHERE user_id=? AND message_id=?", (user_id, message_id)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()
