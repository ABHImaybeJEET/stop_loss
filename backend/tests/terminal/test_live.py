import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from terminal_fixtures import load_json, load_text
from test_agents import make_service
from test_retrieval import FakeEmbedder

import fin_terminal.connectors  # noqa: F401  (import before resilience: package import cycle)
from fin_terminal import embeddings as embeddings_module
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.resilience import CircuitOpenError
from fin_terminal.storage import DocumentStore
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter
from stop_loss.analytics.hazards import parse_gdacs_global, parse_usgs
from stop_loss.analytics.news import parse_google_news_rss
from stop_loss.analytics.weather import parse_forecast
from stop_loss.api.app import create_app
from stop_loss.retrieval.latency import percentile, render_report, summarize
from stop_loss.retrieval.live import (
    LiveIngestor,
    LiveSource,
    RecordTiming,
    hazard_records,
    news_records,
    weather_records,
)
from stop_loss.retrieval.search import HistoricalRetriever
from stop_loss.retrieval.source_health import SourceHealthStore

USER = {"X-User-Id": "user-1"}


class FakePinecone:
    """Records upserts; a query sees an upserted id only after `visible_after` queries."""

    def __init__(self, visible_after: int = 0, fail_namespace: str | None = None) -> None:
        self.upserts: list[dict] = []
        self.queries: list[dict] = []
        self.visible_after = visible_after
        self.fail_namespace = fail_namespace
        self.by_namespace: dict[str, list[dict]] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        if request.url.path == "/vectors/upsert":
            self.upserts.append(body)
            return httpx.Response(200, json={"upsertedCount": len(body["vectors"])})
        if request.url.path == "/query":
            self.queries.append(body)
            if body["namespace"] == self.fail_namespace:
                return httpx.Response(503)
            wanted = ((body.get("filter") or {}).get("content_hash") or {}).get("$eq")
            if wanted is not None:
                seen = len([q for q in self.queries if q.get("filter") == body["filter"]])
                stored = any(v["id"] == wanted for u in self.upserts for v in u["vectors"])
                ok = stored and seen > self.visible_after
                return httpx.Response(200, json={"matches": [{"id": wanted}] if ok else []})
            return httpx.Response(
                200, json={"matches": self.by_namespace.get(body["namespace"], [])}
            )
        return httpx.Response(200, json={})


def adapter_for(fake: FakePinecone) -> PineconeVectorAdapter:
    client = httpx.AsyncClient(base_url="https://x.invalid", transport=httpx.MockTransport(fake))
    return PineconeVectorAdapter(client, "live")


def gdacs_records(run_id: str = "r"):
    return hazard_records(parse_gdacs_global(load_json("gdacs_events.json")), run_id)


def forecast():
    return parse_forecast(
        load_json("openmeteo_forecast_mumbai.json"),
        location="Mumbai port",
        latitude=18.95,
        longitude=72.84,
        reason="live monitoring",
    )


def test_live_records_share_history_metadata_shape_and_stable_hashes() -> None:
    news = news_records(parse_google_news_rss(load_text("google_news_reliance.xml")), "r1", "q")
    assert news and all(r.metadata["doc_type"] == "news" for r in news)
    assert all(r.document.source_url.startswith("http") for r in news)
    again = news_records(parse_google_news_rss(load_text("google_news_reliance.xml")), "r2", "q")
    # The hash ignores run ids and fetch times: a re-poll dedupes.
    assert [r.document.content_hash for r in news] == [r.document.content_hash for r in again]

    hazards = gdacs_records()
    kinds = {r.metadata["doc_type"] for r in hazards}
    assert {"cyclone", "earthquake", "hazard"} <= kinds
    assert all(r.document.published_at is None or r.document.published_at.tzinfo for r in hazards)
    quakes = hazard_records(parse_usgs(load_json("usgs_4.5_week.json"), region_only=False), "r")
    assert len(quakes) == 5 and all(q.metadata["magnitude"] is not None for q in quakes)

    days = weather_records(forecast(), "r")
    assert len(days) == 5 and days[0].metadata["doc_type"] == "weather_forecast"
    assert "max gusts" in days[0].embed_text and days[0].metadata["lat"] == 18.95


@pytest.mark.asyncio
async def test_poll_dedupes_stamps_latency_and_measures_visibility(settings, tmp_path) -> None:
    fake = FakePinecone(visible_after=2)
    store = DocumentStore(tmp_path / "docs.sqlite")
    health = SourceHealthStore(tmp_path / "health.sqlite")
    timings: list[RecordTiming] = []

    async def fetch(run_id: str):
        return weather_records(forecast(), run_id)

    ingestor = LiveIngestor(
        settings,
        embedder=FakeEmbedder(settings),
        adapter=adapter_for(fake),
        store=store,
        health=health,
        sources=[LiveSource("weather", 60, fetch)],
        namespace="live",
        measure_visibility=True,
        on_timing=timings.append,
    )
    source = ingestor.sources[0]
    assert await ingestor.poll(source) == 5
    assert await ingestor.poll(source) == 0  # second poll: everything already stored
    assert sum(len(u["vectors"]) for u in fake.upserts) == 5
    assert all(u["namespace"] == "live" for u in fake.upserts)
    meta = fake.upserts[0]["vectors"][0]["metadata"]
    assert meta["doc_type"] == "weather_forecast" and meta["content_hash"]
    assert len(timings) == 5 and all(t.queryable_ms is not None for t in timings)
    stored = json.loads(
        store.connection.execute("SELECT document_json FROM documents LIMIT 1").fetchone()[0]
    )
    assert stored["process_latency_ms"] > 0 and "fetch_latency_ms" in stored
    [snap] = health.snapshot()
    assert snap.status == "ok" and snap.records_indexed == 5 and snap.last_error is None
    store.close()
    health.close()


@pytest.mark.asyncio
async def test_failing_source_is_isolated_and_trips_its_breaker(settings, tmp_path) -> None:
    calls = {"bad": 0}

    async def bad(run_id: str):
        calls["bad"] += 1
        raise ConnectorError("http_503")

    async def good(run_id: str):
        return gdacs_records(run_id)

    health = SourceHealthStore(tmp_path / "health.sqlite", down_after=3)
    ingestor = LiveIngestor(
        settings,
        embedder=FakeEmbedder(settings),
        adapter=adapter_for(FakePinecone()),
        store=DocumentStore(tmp_path / "docs.sqlite"),
        health=health,
        sources=[LiveSource("news", 60, bad), LiveSource("gdacs", 60, good)],
        namespace="live",
    )
    news, gdacs = ingestor.sources
    for _ in range(settings.circuit_failure_threshold):
        with pytest.raises(ConnectorError):
            await ingestor.poll(news)
    with pytest.raises(CircuitOpenError):  # open circuit: the provider is not called again
        await ingestor.poll(news)
    assert calls["bad"] == settings.circuit_failure_threshold
    assert await ingestor.poll(gdacs) == 10
    status = {h.source: h for h in health.snapshot()}
    assert status["news"].status == "down" and "CircuitOpenError" in status["news"].last_error
    assert status["gdacs"].status == "ok"
    # The loop keeps running: a failed poll schedules a backoff >= the interval, capped.
    assert news.interval_seconds <= ingestor.backoff(news, 5) <= settings.live_backoff_max_seconds


def test_source_health_staleness_and_degradation(tmp_path: Path) -> None:
    store = SourceHealthStore(tmp_path / "h.sqlite", down_after=3)
    now = datetime(2026, 10, 4, 12, tzinfo=UTC)
    store.register("news", 60)
    store.success("news", 3, at=now - timedelta(seconds=30))
    assert store.snapshot(now)[0].status == "ok"
    assert store.snapshot(now + timedelta(seconds=200))[0].status == "degraded"  # > 3 intervals
    store.failure("news", "timeout", at=now)
    snap = store.snapshot(now)[0]
    assert snap.status == "degraded" and snap.consecutive_failures == 1
    assert snap.staleness_seconds == 30.0 and snap.last_error == "timeout"
    store.close()


@pytest.mark.asyncio
async def test_retriever_merges_namespaces_by_score_and_tags_them(settings) -> None:
    fake = FakePinecone()
    fake.by_namespace = {
        "history": [{"id": "h1", "score": 0.7, "metadata": {"title": "old"}}],
        "live": [{"id": "l1", "score": 0.9, "metadata": {"title": "new"}}],
    }
    adapter = adapter_for(fake)
    retriever = HistoricalRetriever(FakeEmbedder(settings), adapter, "history", "live")
    hits = await retriever.search("cyclone", top_k=5)
    assert [(h.id, h.namespace) for h in hits] == [("l1", "live"), ("h1", "history")]
    assert {q["namespace"] for q in fake.queries} == {"history", "live"}
    # A failing live namespace degrades to history only.
    fake.fail_namespace = "live"
    hits = await retriever.search("cyclone", top_k=5)
    assert [h.id for h in hits] == ["h1"]
    fake.fail_namespace = None
    single = await HistoricalRetriever(FakeEmbedder(settings), adapter, "history").search("x")
    assert [h.namespace for h in single] == ["history"]
    await adapter.close()


def test_latency_percentiles_and_report() -> None:
    assert percentile([], 50) is None
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], 50) == 3.0
    assert percentile(list(map(float, range(1, 101))), 95) == 95.0
    timings = [
        RecordTiming("news", "a", 100, 20, 80, 400),
        RecordTiming("news", "b", 100, 30, 90, None),
        RecordTiming("usgs", "c", 50, 10, 60, 300),
    ]
    stats = summarize(timings)
    assert stats["all"]["process_ms"]["n"] == 3 and stats["all"]["queryable_ms"]["n"] == 2
    assert stats["usgs"]["end_to_end_ms"]["p50"] == 50 + 70 + 300
    report = render_report(
        timings, embedder="E", namespace="live-latency", failures={"gdacs": "X"}, duration_seconds=3
    )
    assert "| process = embed + upsert | 3 |" in report and "## usgs" in report
    assert "Within budget" in report and "`gdacs`: X" in report and "1 record(s)" in report


def test_health_sources_endpoint_reports_every_live_source(settings) -> None:
    store = SourceHealthStore(settings.source_health_db_path)
    store.register("news", settings.live_news_seconds)
    store.success("news", 4)
    store.close()
    with TestClient(create_app(settings, make_service(settings))) as client:
        body = client.get("/health/sources").json()
    by_name = {s["source"]: s for s in body["sources"]}
    assert set(by_name) == {"news", "gdacs", "usgs", "weather"}
    assert by_name["news"]["status"] == "ok" and by_name["news"]["staleness_seconds"] >= 0
    assert by_name["gdacs"]["status"] == "down" and by_name["gdacs"]["last_error"] == "never_run"


def test_embedder_prefers_onnx_when_torch_is_missing(settings, monkeypatch) -> None:
    class StubOnnx:
        def __init__(self, name, *, batch_size, query_instruction, threads) -> None:
            self.name, self.instruction = name, query_instruction

    monkeypatch.setitem(sys.modules, "torch", None)  # import torch -> ImportError
    monkeypatch.setattr(embeddings_module, "OnnxEmbeddings", StubOnnx)
    embedder = LazyEmbeddings(settings)
    assert isinstance(embedder.model, StubOnnx) and embedder.semantic
    assert embedder.model.name == settings.embedding_model_name
    explicit = LazyEmbeddings(settings.model_copy(update={"embedding_backend": "onnx"}))
    assert isinstance(explicit.model, StubOnnx)
