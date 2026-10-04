"""Per-source health of the live ingestion loop: SQLite (WAL) shared by the ingest
process (writer) and the API (reader, GET /health/sources)."""

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

HealthStatus = Literal["ok", "degraded", "down"]
# A source counts as stale (degraded) when it has not succeeded for this many intervals.
STALE_INTERVALS = 3


class SourceHealth(BaseModel):
    source: str
    status: HealthStatus
    last_success: str | None = None
    staleness_seconds: float | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    interval_seconds: float
    last_attempt: str | None = None
    records_indexed: int = 0


def _now() -> datetime:
    return datetime.now(UTC)


class SourceHealthStore:
    def __init__(self, path: Path, *, down_after: int = 3) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.down_after = down_after
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS source_health (
                    source TEXT PRIMARY KEY, interval_seconds REAL NOT NULL,
                    last_success TEXT, last_attempt TEXT, last_error TEXT,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    records_indexed INTEGER NOT NULL DEFAULT 0)"""
            )
            self._conn.commit()

    def register(self, source: str, interval_seconds: float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO source_health (source, interval_seconds) VALUES (?, ?) "
                "ON CONFLICT(source) DO UPDATE SET interval_seconds=excluded.interval_seconds",
                (source, interval_seconds),
            )
            self._conn.commit()

    def success(self, source: str, indexed: int, at: datetime | None = None) -> None:
        when = (at or _now()).isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE source_health SET last_success=?, last_attempt=?, last_error=NULL, "
                "consecutive_failures=0, records_indexed=records_indexed+? WHERE source=?",
                (when, when, indexed, source),
            )
            self._conn.commit()

    def failure(self, source: str, error: str, at: datetime | None = None) -> None:
        when = (at or _now()).isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE source_health SET last_attempt=?, last_error=?, "
                "consecutive_failures=consecutive_failures+1 WHERE source=?",
                (when, error[:300], source),
            )
            self._conn.commit()

    def snapshot(self, now: datetime | None = None) -> list[SourceHealth]:
        now = now or _now()
        with self._lock:
            rows = self._conn.execute(
                "SELECT source, interval_seconds, last_success, last_attempt, last_error, "
                "consecutive_failures, records_indexed FROM source_health ORDER BY source"
            ).fetchall()
        return [self._health(row, now) for row in rows]

    def _health(self, row: tuple, now: datetime) -> SourceHealth:
        source, interval, last_success, last_attempt, last_error, failures, indexed = row
        staleness = (
            (now - datetime.fromisoformat(last_success)).total_seconds() if last_success else None
        )
        if failures >= self.down_after or (last_success is None and failures > 0):
            status: HealthStatus = "down"
        elif failures > 0 or staleness is None or staleness > STALE_INTERVALS * interval:
            status = "degraded"
        else:
            status = "ok"
        return SourceHealth(
            source=source,
            status=status,
            last_success=last_success,
            staleness_seconds=round(staleness, 1) if staleness is not None else None,
            last_error=last_error,
            consecutive_failures=failures,
            interval_seconds=interval,
            last_attempt=last_attempt,
            records_indexed=indexed,
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
