"""Deterministic cleaning and dead letters, with no numeric imputation."""

import asyncio
import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from html import unescape

from pydantic import JsonValue

from fin_terminal.evidence import EvidenceLog
from fin_terminal.grounding import require_provenance
from fin_terminal.schemas import RECORD_ADAPTER, Document, EvidenceLogEntry


def clean_record(record: Document) -> Document:
    payload = record.model_dump(mode="json")
    for field in ("text", "title"):
        if isinstance(payload.get(field), str):
            text = re.sub(r"<[^>]*>", " ", payload[field])
            payload[field] = " ".join(unicodedata.normalize("NFC", unescape(text)).split())
    payload["content_hash"] = ""
    payload["transformations"] = ["validate:v1", "html_strip", "unicode:NFC", "timezone:UTC"]
    if isinstance(payload.get("price"), (int, float)) and payload["price"] < 0:
        payload["data_quality"] = "suspect"
    return require_provenance(RECORD_ADAPTER.validate_python(payload))


class DeadLetters:
    def __init__(self, log: EvidenceLog) -> None:
        self.log = log
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dead-letters")

    async def reject(
        self, source: str, run_id: str, stage: str, raw: JsonValue, error: str
    ) -> None:
        raw_hash = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
        # Store references rather than possibly secret-bearing external payloads.
        entry = EvidenceLogEntry(
            ingest_run_id=run_id,
            source=source,
            stage=stage,
            event="rejected",
            details={"raw_reference": f"sha256:{raw_hash}", "error": error},
        )
        await asyncio.get_running_loop().run_in_executor(self.executor, self.log.append, entry)

    def close(self) -> None:
        self.executor.shutdown(wait=False)
