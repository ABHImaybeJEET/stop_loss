import asyncio
import json
import sqlite3
from uuid import uuid4

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import JsonValue

from fin_terminal.config import Settings
from fin_terminal.connectors.stub import StubConnector
from fin_terminal.ingest import run
from fin_terminal.ingestion.graph import SOURCES, IngestionPipeline
from fin_terminal.observability import run_config
from fin_terminal.schemas import Document, Theme
from fin_terminal.vectorstore.base import VectorStoreAdapter


class FixtureConnector(StubConnector):
    def __init__(self, document: Document, *, invalid: bool = False) -> None:
        super().__init__(document.source)
        self.document = document
        self.invalid = invalid

    async def fetch(self) -> list[JsonValue]:
        return [self.document.model_dump(mode="json")] * 2

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        if self.invalid:
            raise ValueError("invalid fixture")
        return [self.document] * len(raw)


class FixtureEmbedder:
    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2]  # Explicit test vector, never a financial metric.


class FixtureVectors(VectorStoreAdapter):
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.fail = False

    async def upsert(self, document: Document, vector: list[float]) -> None:
        if self.fail:
            raise OSError("vector service down")
        self.ids.append(document.content_hash)

    async def health(self) -> bool:
        return not self.fail

    async def close(self) -> None:
        pass


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("failure", ["failed", "rate_limited", "degraded"])
def test_fetch_failure_still_reports_every_stream(settings: Settings, source: str, failure: str):
    settings = settings.model_copy(
        update={"stub_fail_source": source, "stub_failure_mode": failure}
    )
    result = asyncio.run(run(settings))[0]
    assert set(result["statuses"]) == set(SOURCES)
    assert result["statuses"][source]["status"] == failure
    assert all(s["status"] == "ok" for name, s in result["statuses"].items() if name != source)
    assert source in result["report"]
    assert result["indexed"] == 0


def test_parallel_barrier_evidence_and_checkpoint_reload(settings: Settings):
    async def exercise():
        arrived = set()
        barrier = asyncio.Event()

        class BarrierConnector(StubConnector):
            async def fetch(self):
                arrived.add(self.source)
                if len(arrived) == 6:
                    barrier.set()
                await asyncio.wait_for(barrier.wait(), timeout=2)
                return []

        pipeline = IngestionPipeline(settings, {s: BarrierConnector(s) for s in SOURCES})
        config = run_config("barrier-run", uuid4(), list(SOURCES))
        try:
            async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_path)) as saver:
                graph = pipeline.build_graph(saver)
                result = await graph.ainvoke({"ingest_run_id": "barrier-run"}, config=config)
                assert all(s["status"] == "ok" for s in result["statuses"].values())
            async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_path)) as saver:
                snapshot = await pipeline.build_graph(saver).aget_state(config)
                assert snapshot.next == ()
                assert snapshot.values["report"] == result["report"]
        finally:
            await pipeline.close()

    asyncio.run(exercise())
    entries = [json.loads(line) for line in settings.evidence_path.read_text().splitlines()]
    completed = [e["stage"] for e in entries if e["event"] == "completed"]
    assert len(completed) == 13  # plan + six fetches + six processing nodes
    assert completed.count("normalize") == 1
    assert all(completed.index(f"fetch_{s}") < completed.index("normalize") for s in SOURCES)
    assert all(e["ingest_run_id"] == "barrier-run" for e in entries)
    with sqlite3.connect(settings.checkpoint_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_sync_sqlite_saver_supported(settings: Settings):
    pipeline = IngestionPipeline(settings)
    try:
        with SqliteSaver.from_conn_string(str(settings.checkpoint_path)) as saver:
            graph = pipeline.build_graph(saver)
            result = graph.invoke(
                {"ingest_run_id": "sync"}, config=run_config("sync", uuid4(), list(SOURCES))
            )
            assert len(result["statuses"]) == 6
            assert graph.get_state({"configurable": {"thread_id": "sync"}}).next == ()
    finally:
        asyncio.run(pipeline.close())


def test_dedupe_across_restarts_and_lineage(settings: Settings, document: Document):
    vectors = FixtureVectors()

    async def cycle(run_id):
        connectors = {s: StubConnector(s) for s in SOURCES}
        connectors[document.source] = FixtureConnector(document)
        pipeline = IngestionPipeline(
            settings, connectors, embedder=FixtureEmbedder(), vectorstore=vectors
        )
        try:
            async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_path)) as saver:
                return await pipeline.build_graph(saver).ainvoke(
                    {"ingest_run_id": run_id}, config=run_config(run_id, uuid4(), list(SOURCES))
                )
        finally:
            await pipeline.close()

    first = asyncio.run(cycle("first"))
    second = asyncio.run(cycle("second"))
    assert first["indexed"] == 1 and first["duplicates"] == 1
    assert second["indexed"] == 0 and second["duplicates"] == 2
    assert len(vectors.ids) == 1
    assert first["documents"][0]["theme_tags"] == [Theme.TARIFF.value]
    with sqlite3.connect(settings.database_path) as connection:
        rows = connection.execute("SELECT document_json FROM documents").fetchall()
        assert len(rows) == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    stored = json.loads(rows[0][0])
    assert stored["ingest_run_id"] == "first"
    assert stored["provider"] == "test_fixture"
    assert stored["fetch_latency_ms"] >= 0
    assert 0 < stored["process_latency_ms"] < 1000


@pytest.mark.parametrize("failure", ["index", "normalize", "timeout"])
def test_processing_failure_can_retry_without_poisoning_dedupe(
    settings: Settings, document: Document, failure: str
):
    async def exercise():
        vectors = FixtureVectors()
        vectors.fail = failure == "index"
        connector = FixtureConnector(document, invalid=failure == "normalize")
        connectors = {s: StubConnector(s) for s in SOURCES}
        connectors[document.source] = connector

        class SlowEmbedder(FixtureEmbedder):
            slow = failure == "timeout"

            async def embed(self, text):
                if self.slow:
                    await asyncio.sleep(2)
                return await super().embed(text)

        embedder = SlowEmbedder()
        pipeline = IngestionPipeline(settings, connectors, embedder=embedder, vectorstore=vectors)
        try:
            async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_path)) as saver:
                graph = pipeline.build_graph(saver)
                first = await graph.ainvoke(
                    {"ingest_run_id": "failure"},
                    config=run_config("failure", uuid4(), list(SOURCES)),
                )
                assert first["indexed"] == 0
                assert first["statuses"][document.source]["status"] == "degraded"
                assert not pipeline.store.contains(document.content_hash)
                vectors.fail = connector.invalid = embedder.slow = False
                second = await graph.ainvoke(
                    {"ingest_run_id": "recovery"},
                    config=run_config("recovery", uuid4(), list(SOURCES)),
                )
                assert second["indexed"] == 1
        finally:
            await pipeline.close()

    asyncio.run(exercise())


def test_bounded_stream_uses_distinct_runs(settings: Settings):
    settings = settings.model_copy(update={"ingestion_poll_seconds": 0.001})
    results = asyncio.run(run(settings, stream=True, max_cycles=2))
    assert len(results) == 1
    entries = [json.loads(line) for line in settings.evidence_path.read_text().splitlines()]
    assert len({entry["ingest_run_id"] for entry in entries}) == 2
