"""Graph runs and their typed events: SQLite (WAL), append-only per run, for replay."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from stop_loss.agents.run_events import RunMode, RunRecord, RunStatus


class RunStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mode TEXT NOT NULL,
                    thread_id TEXT NOT NULL, message_id TEXT NOT NULL, label TEXT NOT NULL,
                    status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT)"""
            )
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS run_events (
                    run_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY (run_id, seq))"""
            )
            self._conn.commit()

    def create(
        self,
        *,
        run_id: str,
        user_id: str,
        mode: RunMode,
        thread_id: str,
        message_id: str,
        label: str,
        started_at: str,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?, ?, ?, 'running', ?, NULL)",
                (run_id, user_id, mode, thread_id, message_id, label, started_at),
            )
            self._conn.commit()

    def append(self, run_id: str, event: dict[str, Any]) -> None:
        """Idempotent on (run_id, seq): a retried write never duplicates an event."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO run_events VALUES (?, ?, ?, ?)",
                (
                    run_id,
                    event["seq"],
                    event["type"],
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            self._conn.commit()

    def finish(self, run_id: str, status: RunStatus, finished_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status=?, finished_at=? WHERE run_id=?",
                (status, finished_at, run_id),
            )
            self._conn.commit()

    def get(self, run_id: str, user_id: str) -> RunRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT run_id, mode, thread_id, message_id, label, status, started_at, "
                "finished_at FROM runs WHERE run_id=? AND user_id=?",
                (run_id, user_id),
            ).fetchone()
            if row is None:
                return None
            payloads = self._conn.execute(
                "SELECT payload FROM run_events WHERE run_id=? ORDER BY seq", (run_id,)
            ).fetchall()
        keys = ("run_id", "mode", "thread_id", "message_id", "label", "status", "started_at")
        return RunRecord.model_validate(
            {
                **dict(zip(keys, row[:7], strict=True)),
                "finished_at": row[7],
                "events": [json.loads(p) for (p,) in payloads],
            }
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
