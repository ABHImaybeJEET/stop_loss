import json
from pathlib import Path

import httpx
import pytest
from terminal_fixtures import TERMINAL

import fin_terminal.connectors  # noqa: F401  (import before resilience: package import cycle)
from fin_terminal.embeddings import LazyEmbeddings, LightweightFeatureEmbeddings
from fin_terminal.storage import DocumentStore
from fin_terminal.vectorstore.pinecone import (
    PineconeVectorAdapter,
    clean_metadata,
    document_metadata,
)
from fin_terminal.vectorstore.pinecone_control import ensure_index
from stop_loss.retrieval import datasets
from stop_loss.retrieval.backfill import Backfill, Progress
from stop_loss.retrieval.search import HistoricalRetriever, build_filter

ROOT = TERMINAL / "datasets"


def test_stock_news_reader_keeps_provenance_and_drops_untitled_rows() -> None:
    records = list(datasets.stock_news(ROOT))
    assert len(records) == 2
    first, second = records
    assert first.document.source_url.startswith("http://www.moneycontrol.com/")
    assert first.embed_text == first.document.title  # identical description not duplicated
    assert first.metadata["impact_tier"] == "MEDIUM" and first.metadata["doc_type"] == "news"
    assert second.document.source_url is None
    assert second.document.data_quality == "missing_fields"  # no URL: flagged, not invented
    assert second.document.raw_reference.endswith("#L3")
    assert second.metadata["categories"] == ["trade", "macro"]
    assert second.metadata["relevance_score"] is None
    assert [t.value for t in second.document.theme_tags] == ["TARIFF"]


def test_india_news_filters_by_year_and_finance_relevance() -> None:
    titles = [r.document.title for r in datasets.india_news(ROOT, min_year=2015)]
    assert titles == ["Company announces new plant", "Sensex climbs as RBI holds repo rate"]


def test_company_cyclone_and_earthquake_readers() -> None:
    companies = list(datasets.companies(ROOT))
    assert companies[0].metadata["tickers"] == ["20MICRONS.NS"]
    assert "micronized industrial minerals" in companies[0].embed_text
    assert companies[1].embed_text == "BARE.NS (BARE.NS)"
    assert companies[1].metadata["sector"] is None
    storms = {r.metadata["title"]: r for r in datasets.cyclones(ROOT)}
    ilsa = storms["Ilsa (2000)"]
    assert ilsa.metadata["max_wind_kt"] == 45 and ilsa.metadata["min_pressure_hpa"] == 990
    assert "South Indian basin" in ilsa.embed_text and "2 track points" in ilsa.embed_text
    unnamed = storms["Unnamed storm (2020)"]
    assert unnamed.metadata["max_wind_kt"] is None and "Peak sustained" not in unnamed.embed_text
    # Blank basin in the cleaned file = pandas-parsed "NA" (North Atlantic): restored + audited.
    harvey = storms["Harvey (2017)"]
    assert harvey.metadata["basin"] == "NA" and harvey.metadata["region"] == "Gulf of Mexico"
    assert harvey.metadata["intensity_category"] == 4
    assert harvey.document.transformations == ["basin_na_restored_from_pandas_nan"]
    assert "Category 4-equivalent major hurricane-strength" in harvey.embed_text
    quakes = list(datasets.earthquakes(ROOT))
    assert len(quakes) == 1 and quakes[0].metadata["magnitude"] == 6.0


def test_cyclone_region_and_intensity_labels() -> None:
    assert datasets.cyclone_region("NI", 19.0, 86.0) == "Bay of Bengal"
    assert datasets.cyclone_region("NI", 15.0, 65.0) == "Arabian Sea"
    assert datasets.cyclone_region("WP", 15.0, 115.0) == "South China Sea"
    assert datasets.cyclone_region("NA", 14.0, -70.0) == "Caribbean Sea"
    assert datasets.cyclone_region("NA", None, -90.0) is None
    assert datasets.cyclone_intensity(None) == ("intensity not reported", None)
    assert datasets.cyclone_intensity(50)[1] == 0
    assert datasets.cyclone_intensity(83)[1] == 2 and datasets.cyclone_intensity(137)[1] == 5


def test_metadata_drops_nulls_and_adds_filterable_dates() -> None:
    assert clean_metadata({"a": None, "b": "", "c": [], "d": 0, "e": ["x", None]}) == {
        "d": 0,
        "e": ["x"],
    }
    record = next(datasets.stock_news(ROOT))
    meta = document_metadata(record.document, **record.metadata)
    assert meta["year"] == 2017 and isinstance(meta["published_ts"], int)
    assert meta["content_hash"] == record.document.content_hash
    assert "relevance_score" in meta and len(meta["text"]) <= 600


def test_build_filter() -> None:
    assert build_filter() is None
    assert build_filter(regions=["Gulf of Mexico"], min_category=4) == {
        "$and": [{"region": {"$in": ["Gulf of Mexico"]}}, {"intensity_category": {"$gte": 4}}]
    }
    assert build_filter(doc_types=["news"]) == {"doc_type": {"$in": ["news"]}}
    combined = build_filter(doc_types=["cyclone"], year_from=2010, tickers=["XOM"])
    assert combined == {
        "$and": [
            {"doc_type": {"$in": ["cyclone"]}},
            {"year": {"$gte": 2010}},
            {"tickers": {"$in": ["XOM"]}},
        ]
    }


class RecordingPinecone:
    def __init__(self, fail_first: int = 0) -> None:
        self.requests: list[dict] = []
        self.fail_first = fail_first

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.requests.append({"path": request.url.path, **body})
        if request.url.path == "/vectors/upsert" and self.fail_first:
            self.fail_first -= 1
            return httpx.Response(429, json={"message": "rate limited"})
        if request.url.path == "/query":
            return httpx.Response(
                200,
                json={
                    "matches": [
                        {"id": "h1", "score": 0.9, "metadata": {"doc_type": "news", "title": "T"}}
                    ]
                },
            )
        return httpx.Response(200, json={"upsertedCount": len(body.get("vectors", []))})


class FakeEmbedder(LazyEmbeddings):
    def __init__(self, settings, semantic: bool = True) -> None:
        super().__init__(settings)
        self.semantic = semantic
        self.batches: list[int] = []
        self.queries: list[str] = []

    def _load_model(self):
        return LightweightFeatureEmbeddings(dimensions=8)

    async def embed_batch(self, texts):
        self.batches.append(len(texts))
        return [[0.1] * 8 for _ in texts]

    async def embed_query(self, text):
        self.queries.append(text)
        return [0.2] * 8


@pytest.mark.asyncio
async def test_backfill_batches_retries_dedupes_and_resumes(settings, tmp_path: Path) -> None:
    transport = RecordingPinecone(fail_first=1)
    adapter = PineconeVectorAdapter(
        httpx.AsyncClient(base_url="https://x.invalid", transport=httpx.MockTransport(transport)),
        "live",
    )
    store = DocumentStore(tmp_path / "docs.sqlite")
    progress = Progress(tmp_path / "progress.sqlite")
    embedder = FakeEmbedder(settings)
    runner = Backfill(embedder, adapter, store, progress, namespace="history", chunk_size=2)

    stats = await runner.run("stock_news", datasets.stock_news(ROOT))
    assert stats.upserted == 2 and embedder.batches == [2]
    upserts = [r for r in transport.requests if r["path"] == "/vectors/upsert"]
    assert len(upserts) == 2  # first attempt 429, retried
    assert upserts[-1]["namespace"] == "history" and len(upserts[-1]["vectors"]) == 2
    assert progress.get("stock_news") == 3

    # Resume: nothing new past the checkpoint. Reset: rows are re-read but deduped by hash.
    assert (await runner.run("stock_news", datasets.stock_news(ROOT))).upserted == 0
    progress.reset("stock_news")
    again = await runner.run("stock_news", datasets.stock_news(ROOT))
    assert again.upserted == 0 and again.skipped_existing == 2
    assert store.delete_run(datasets.RUN_ID) == 2
    await adapter.close()
    store.close()
    progress.close()


@pytest.mark.asyncio
async def test_backfill_refuses_non_semantic_vectors(settings, tmp_path: Path) -> None:
    adapter = PineconeVectorAdapter(httpx.AsyncClient(base_url="https://x.invalid"), "live")
    runner = Backfill(
        FakeEmbedder(settings, semantic=False),
        adapter,
        DocumentStore(tmp_path / "d.sqlite"),
        Progress(tmp_path / "p.sqlite"),
        namespace="history",
    )
    with pytest.raises(RuntimeError, match="semantic"):
        await runner.run("stock_news", datasets.stock_news(ROOT))
    await adapter.close()


@pytest.mark.asyncio
async def test_retriever_embeds_query_and_filters(settings) -> None:
    transport = RecordingPinecone()
    adapter = PineconeVectorAdapter(
        httpx.AsyncClient(base_url="https://x.invalid", transport=httpx.MockTransport(transport)),
        "live",
    )
    embedder = FakeEmbedder(settings)
    hits = await HistoricalRetriever(embedder, adapter, "history").search(
        "gulf hurricane", top_k=3, doc_types=["cyclone"], year_from=2005
    )
    assert hits[0].id == "h1" and hits[0].text == "T"
    query = transport.requests[-1]
    assert query["namespace"] == "history" and query["topK"] == 3
    assert query["filter"]["$and"][0] == {"doc_type": {"$in": ["cyclone"]}}
    assert embedder.queries == ["gulf hurricane"]
    await adapter.close()


def test_ensure_index_creates_then_validates_dimension(settings) -> None:
    calls: list[str] = []
    state: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST":
            state.update(json.loads(request.content), status={"ready": True}, host="h.io")
            return httpx.Response(201, json=state)
        return httpx.Response(200, json=state) if state else httpx.Response(404)

    configured = settings.model_copy(update={"pinecone_api_key": "k", "embedding_dimensions": 768})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        created = ensure_index(configured, client=client)
        assert created["dimension"] == 768 and created["metric"] == "cosine"
        assert created["spec"] == {"serverless": {"cloud": "aws", "region": "us-east-1"}}
        mismatched = configured.model_copy(update={"embedding_dimensions": 384})
        with pytest.raises(ValueError, match="dimension"):
            ensure_index(mismatched, client=client)
    assert calls[:2] == ["GET /indexes/stop-loss-records", "POST /indexes"]
