"""Continuous live ingestion into the Pinecone `live` namespace (`stop-loss-vectors live`).

One task per source (news, GDACS, USGS, weather forecasts), each on its own interval with
its own circuit breaker and exponential backoff: a failing source is marked degraded/down
in SourceHealthStore and never stops the others. Per micro-batch: dedupe by content_hash
(the same DocumentStore as the history backfill) → embed → upsert → mark stored. Records
reuse the history `Record` shape and `document_metadata`, so filters work across both
namespaces. Fetch and process latency are stamped on every stored Document."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.resilience import CircuitBreaker, CircuitOpenError
from fin_terminal.schemas import Document, NewsArticle, utcnow
from fin_terminal.storage import DocumentStore
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter, document_metadata
from stop_loss.analytics.exposure import SECTOR_HUBS
from stop_loss.analytics.hazards import (
    GDACS,
    USGS_WEEK,
    HazardAlert,
    HazardClient,
    parse_gdacs_global,
    parse_usgs,
)
from stop_loss.analytics.models import NewsItem, WeatherOutlook
from stop_loss.analytics.news import NewsClient, dedupe_news
from stop_loss.analytics.themes import tag_themes
from stop_loss.analytics.weather import WeatherClient
from stop_loss.retrieval.datasets import Record
from stop_loss.retrieval.source_health import SourceHealthStore
from stop_loss.settings import TerminalSettings

logger = logging.getLogger("stop_loss.retrieval")
FORECAST_HORIZON_DAYS = 5
VISIBILITY_POLL_SECONDS = 0.25
VISIBILITY_TIMEOUT_SECONDS = 60.0
# Coastal refining/port clusters exposed to Arabian Sea and Bay of Bengal cyclones. Sector
# hubs come from analytics.exposure; the rest are major ports (labelled as such).
LIVE_WEATHER_POINTS: list[tuple[str, float, float]] = [
    *(hub for hubs in SECTOR_HUBS.values() for hub in hubs),
    ("Mundra/Kandla ports, Gujarat", 22.84, 69.70),
    ("Mumbai port, Maharashtra", 18.95, 72.84),
    ("Chennai port, Tamil Nadu", 13.08, 80.29),
    ("Visakhapatnam port, Andhra Pradesh", 17.69, 83.22),
    ("Haldia port, West Bengal", 22.03, 88.06),
]
HAZARD_DOC_TYPES = {"tropical cyclone": "cyclone", "earthquake": "earthquake"}


@dataclass(frozen=True)
class LiveSource:
    name: str
    interval_seconds: float
    fetch: Callable[[str], Awaitable[list[Record]]]  # ingest_run_id -> records


@dataclass(frozen=True)
class RecordTiming:
    source: str
    content_hash: str
    fetch_ms: float
    embed_ms: float
    upsert_ms: float
    queryable_ms: float | None  # upsert ack -> visible to a filtered query (None: not measured)

    @property
    def process_ms(self) -> float:
        """The latency invariant: process + embed + index for one item (< 1 s)."""
        return self.embed_ms + self.upsert_ms


# ---- records (same Record/metadata shape as the history datasets) ----


def news_records(items: list[NewsItem], run_id: str, query: str) -> list[Record]:
    out: list[Record] = []
    for item in items:
        body = item.title if not item.summary else f"{item.title}. {item.summary}"
        doc = NewsArticle(
            source="live_news",
            provider=item.provider,
            title=item.title,
            text=body,
            source_url=item.url,
            published_at=item.published_at,
            observed_at=item.observed_at or item.published_at,
            fetched_at=utcnow(),
            ingest_run_id=run_id,
            theme_tags=tag_themes(body),
        )
        meta = {
            "doc_type": "news",
            "dataset": "live_news",
            "publisher": item.publisher,
            "query": query,
            "tickers": item.related_tickers,
        }
        out.append(Record(doc, body, meta))
    return out


def _gdacs_time(value: str | None) -> datetime | None:
    """GDACS dates are UTC without an offset (provider convention)."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def hazard_records(alerts: list[HazardAlert], run_id: str) -> list[Record]:
    out: list[Record] = []
    for a in alerts:
        started = _gdacs_time(a.started_at)
        parts = [f"{a.event_type.capitalize()} {a.name}"]
        if a.country:
            parts[0] += f" ({a.country})"
        if a.magnitude is not None:
            parts.append(f"magnitude {a.magnitude:g}")
        if a.alert_level:
            parts.append(f"{a.source.upper()} {a.alert_level} alert")
        if a.severity:
            parts.append(a.severity)
        if started:
            parts.append(f"from {started:%Y-%m-%d %H:%M} UTC")
        body = ", ".join(parts) + f", near {a.latitude:.1f}, {a.longitude:.1f}."
        doc = Document(
            source=f"live_{a.source}",
            provider=a.source,
            text=body,
            source_url=a.url,
            published_at=started,
            observed_at=started,
            fetched_at=utcnow(),
            ingest_run_id=run_id,
            theme_tags=tag_themes(f"{a.event_type} {body}"),
        )
        meta = {
            "doc_type": HAZARD_DOC_TYPES.get(a.event_type, "hazard"),
            "dataset": f"live_{a.source}",
            "title": a.name,
            "event_type": a.event_type,
            "alert_level": a.alert_level,
            "country": a.country,
            "magnitude": a.magnitude,
            "lat": a.latitude,
            "lon": a.longitude,
        }
        out.append(Record(doc, body, meta))
    return out


def weather_records(
    outlook: WeatherOutlook, run_id: str, horizon_days: int = FORECAST_HORIZON_DAYS
) -> list[Record]:
    """One document per forecast day; a revised forecast is new content (new hash)."""
    out: list[Record] = []
    for day in outlook.days[:horizon_days]:
        fields = {
            "max wind": (day.wind_speed_max, "km/h"),
            "max gusts": (day.wind_gust_max, "km/h"),
            "precipitation": (day.precipitation_sum, "mm"),
        }
        known = [f"{k} {v:g} {u}" for k, (v, u) in fields.items() if v is not None]
        if not known:
            continue  # nothing observed: index nothing rather than an empty forecast
        body = f"Weather forecast for {outlook.location} on {day.date}: " + ", ".join(known) + "."
        when = datetime.combine(date.fromisoformat(day.date), datetime.min.time(), tzinfo=UTC)
        doc = Document(
            source="live_weather",
            provider="open-meteo",
            text=body,
            source_url=outlook.source_url,
            published_at=None,
            observed_at=when,
            fetched_at=utcnow(),
            ingest_run_id=run_id,
            theme_tags=tag_themes(f"weather {body}"),
        )
        meta = {
            "doc_type": "weather_forecast",
            "dataset": "live_open_meteo",
            "title": f"{outlook.location} {day.date}",
            "location": outlook.location,
            "lat": outlook.latitude,
            "lon": outlook.longitude,
            "wind_max_kmh": day.wind_speed_max,
            "gust_max_kmh": day.wind_gust_max,
            "precip_mm": day.precipitation_sum,
            "forecast_date": day.date,
        }
        out.append(Record(doc, body, meta))
    return out


def default_sources(
    settings: TerminalSettings, news: NewsClient, hazards: HazardClient, weather: WeatherClient
) -> list[LiveSource]:
    """Live fetchers bypass the agents' response caches (they call the guarded HTTP layer
    or are built with near-zero cache TTLs by `live_clients`)."""

    async def fetch_news(run_id: str) -> list[Record]:
        out: list[Record] = []
        for query in settings.live_news_queries:
            out += news_records(dedupe_news(await news.google_news(query)), run_id, query)
        return out

    async def fetch_gdacs(run_id: str) -> list[Record]:
        params = {"eventlist": "TC;FL;EQ;DR;WF", "alertlevel": "Green;Orange;Red"}
        return hazard_records(
            parse_gdacs_global(await hazards.http.get_json(GDACS, params)), run_id
        )

    async def fetch_usgs(run_id: str) -> list[Record]:
        payload = await hazards.http.get_json(USGS_WEEK)
        return hazard_records(parse_usgs(payload, region_only=False), run_id)

    async def fetch_weather(run_id: str) -> list[Record]:
        outlooks = await asyncio.gather(
            *(
                weather.outlook(lat, lon, location=label, reason="live monitoring")
                for label, lat, lon in LIVE_WEATHER_POINTS
            )
        )
        return [r for outlook in outlooks for r in weather_records(outlook, run_id)]

    fetchers = {
        "news": fetch_news,
        "gdacs": fetch_gdacs,
        "usgs": fetch_usgs,
        "weather": fetch_weather,
    }
    return [
        LiveSource(name, interval, fetchers[name])
        for name, interval in source_intervals(settings).items()
    ]


def source_intervals(settings: TerminalSettings) -> dict[str, float]:
    """The live sources and their poll intervals (also what /health/sources expects)."""
    return {
        "news": settings.live_news_seconds,
        "gdacs": settings.live_gdacs_seconds,
        "usgs": settings.live_usgs_seconds,
        "weather": settings.live_weather_seconds,
    }


def live_clients(settings: TerminalSettings) -> tuple[NewsClient, HazardClient, WeatherClient]:
    fresh = settings.model_copy(update={"news_cache_seconds": 1, "weather_cache_seconds": 1})
    return NewsClient(fresh), HazardClient(fresh), WeatherClient(fresh)


# ---- ingestor ----


class LiveIngestor:
    def __init__(
        self,
        settings: TerminalSettings,
        *,
        embedder: LazyEmbeddings,
        adapter: PineconeVectorAdapter,
        store: DocumentStore | None,
        health: SourceHealthStore,
        sources: list[LiveSource],
        namespace: str,
        measure_visibility: bool = False,
        on_timing: Callable[[RecordTiming], None] | None = None,
        limit_per_poll: int | None = None,
    ) -> None:
        self.settings = settings
        self.embedder = embedder
        self.adapter = adapter
        self.store = store  # None: no dedupe (latency probes into a scratch namespace)
        self.health = health
        self.sources = sources
        self.namespace = namespace
        self.measure_visibility = measure_visibility
        self.on_timing = on_timing
        self.limit_per_poll = limit_per_poll
        self.breakers = {
            s.name: CircuitBreaker(
                settings.circuit_failure_threshold, settings.circuit_reset_seconds
            )
            for s in sources
        }
        for source in sources:
            health.register(source.name, source.interval_seconds)

    async def ensure_semantic(self) -> None:
        await asyncio.to_thread(lambda: self.embedder.model)
        if not self.embedder.semantic:
            raise RuntimeError(
                "Refusing live indexing: no semantic embedding model (install the "
                "'onnx-embeddings' or 'local-embeddings' extra)."
            )

    async def run(self, *, duration_seconds: float | None = None) -> None:
        await self.ensure_semantic()
        tasks = [asyncio.create_task(self._loop(s), name=f"live-{s.name}") for s in self.sources]
        try:
            if duration_seconds is None:
                await asyncio.gather(*tasks)
            else:
                await asyncio.wait(tasks, timeout=duration_seconds)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def backoff(self, source: LiveSource, failures: int) -> float:
        """Exponential backoff with full jitter in [interval, cap]."""
        base = min(
            self.settings.live_backoff_max_seconds, source.interval_seconds * 2 ** max(0, failures)
        )
        return max(1.0, random.uniform(source.interval_seconds, base))

    async def _loop(self, source: LiveSource) -> None:
        failures = 0
        while True:
            try:
                await self.poll(source)
                failures = 0
                delay = source.interval_seconds
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - one source failing never stops the loop
                failures += 1
                delay = self.backoff(source, failures)
            await asyncio.sleep(delay)

    async def poll(self, source: LiveSource) -> int:
        """One fetch + index cycle. Raises on failure (after recording source health)."""
        breaker = self.breakers[source.name]
        run_id = f"live-{source.name}-{uuid4().hex[:12]}"
        try:
            breaker.check()
            started = time.perf_counter()
            records = await source.fetch(run_id)
            fetch_ms = (time.perf_counter() - started) * 1000
            indexed = await self._index(source.name, records, fetch_ms)
        except asyncio.CancelledError:
            breaker.cancel_probe()
            raise
        except Exception as exc:
            if not isinstance(exc, CircuitOpenError):  # an open circuit is not a new failure
                breaker.failure()
            error = f"{type(exc).__name__}: {getattr(exc, 'code', '') or exc}"[:300]
            await asyncio.to_thread(self.health.failure, source.name, error)
            logger.warning("live source %s failed: %s", source.name, error)
            raise
        breaker.success()
        await asyncio.to_thread(self.health.success, source.name, indexed)
        logger.info(
            "live %s: %d fetched, %d new indexed (fetch %.0f ms)",
            source.name,
            len(records),
            indexed,
            fetch_ms,
        )
        return indexed

    async def _fresh(self, records: list[Record]) -> list[Record]:
        unique: dict[str, Record] = {}
        for record in records:  # also dedupes repeats inside one poll
            unique.setdefault(record.document.content_hash, record)
        if self.store is None:
            return list(unique.values())
        missing = await asyncio.to_thread(self.store.missing, list(unique))
        return [r for h, r in unique.items() if h in missing]

    async def _index(self, source: str, records: list[Record], fetch_ms: float) -> int:
        fresh = (await self._fresh(records))[: self.limit_per_poll]
        size = self.settings.live_microbatch
        for start in range(0, len(fresh), size):
            await self._index_batch(source, fresh[start : start + size], fetch_ms)
        return len(fresh)

    async def _index_batch(self, source: str, batch: list[Record], fetch_ms: float) -> None:
        t0 = time.perf_counter()
        vectors = await self.embedder.embed_batch([r.embed_text for r in batch])
        t1 = time.perf_counter()
        items = [
            (r.document.content_hash, v, document_metadata(r.document, **r.metadata))
            for r, v in zip(batch, vectors, strict=True)
        ]
        await self.adapter.upsert_many(items, namespace=self.namespace)
        t2 = time.perf_counter()
        embed_ms, upsert_ms = (t1 - t0) * 1000, (t2 - t1) * 1000
        visible: dict[str, float | None] = {r.document.content_hash: None for r in batch}
        if self.measure_visibility:
            seen = await asyncio.gather(
                *(
                    self._visible_after(r.document.content_hash, v, t2)
                    for r, v in zip(batch, vectors, strict=True)
                )
            )
            visible = dict(zip(visible, seen, strict=True))
        docs = [
            r.document.model_copy(
                update={
                    "fetch_latency_ms": round(fetch_ms, 2),
                    "process_latency_ms": round((t2 - t0) * 1000, 2),
                }
            )
            for r in batch
        ]
        if self.store is not None:  # marked stored only after the upsert succeeded
            await asyncio.to_thread(self.store.insert_many, docs)
        if self.on_timing:
            for record in batch:
                h = record.document.content_hash
                self.on_timing(RecordTiming(source, h, fetch_ms, embed_ms, upsert_ms, visible[h]))

    async def _visible_after(
        self, content_hash: str, vector: list[float], acked: float
    ) -> float | None:
        deadline = acked + VISIBILITY_TIMEOUT_SECONDS
        while time.perf_counter() < deadline:
            matches = await self.adapter.query(
                vector,
                top_k=1,
                filter={"content_hash": {"$eq": content_hash}},
                namespace=self.namespace,
            )
            if matches:
                return (time.perf_counter() - acked) * 1000
            await asyncio.sleep(VISIBILITY_POLL_SECONDS)
        return None  # never fabricated: an unobserved visibility stays unknown
