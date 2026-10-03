"""Append-only, one JSON record per write, shared by concurrent graph nodes."""

import os
import threading
from pathlib import Path

from fin_terminal.schemas import EvidenceLogEntry


class EvidenceLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: EvidenceLogEntry) -> None:
        data = (entry.model_dump_json() + "\n").encode("utf-8")
        with self._lock:
            with self.path.open("ab", buffering=0) as handle:
                handle.write(data)
                os.fsync(handle.fileno())
