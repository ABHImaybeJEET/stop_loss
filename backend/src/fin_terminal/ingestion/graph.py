"""Parallel source fetches, one explicit barrier, and auditable pipeline stages."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Protocol, TypedDict, TypeVar

import httpx
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import JsonValue

from fin_terminal.config import Settings
from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.connectors.stub import StubConnector
from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.evidence import EvidenceLog
from fin_terminal.observability import LatencyTimer, logger, render_report
from fin_terminal.resilience import CircuitOpenError, RateLimitedError, SourceGuards
from fin_terminal.schemas import (
    RECORD_ADAPTER,
    EvidenceLogEntry,
    StreamStatus,
    Theme,
    utcnow,
)
from fin_terminal.storage import DocumentStore
from fin_terminal.vectorstore import VectorStoreAdapter, create_vectorstore

SOURCES = ("prices", "macro", "weather", "news_tariff", "news_banktax", "news_war")
SOURCE_THEMES = {
    "news_tariff": Theme.TARIFF,
    "news_banktax": Theme.BANK_TAX,
    "news_war": Theme.WAR_CRISIS,
}
JSONDict = dict[str, JsonValue]
T = TypeVar("T")


def merge_maps(left: dict[str, T], right: dict[str, T]) -> dict[str, T]:
    return {**left, **right}


class FetchBatch(TypedDict):
    items: list[JsonValue]
    fetched_at: str
    fetch_latency_ms: float


class IngestionState(TypedDict, total=False):
    ingest_run_id: str
    langsmith_run_id: str | None
    sources: list[str]
    raw: Annotated[dict[str, FetchBatch], merge_maps]
    statuses: Annotated[dict[str, JSONDict], merge_maps]
    documents: list[JSONDict]
    process_started: dict[str, float]
    duplicates: int
    indexed: int
    report: str


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


Node = Callable[[IngestionState], Awaitable[IngestionState]]


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        connectors: Mapping[str, AsyncConnector] | None = None,
        *,
        embedder: Embedder | None = None,
        vectorstore: VectorStoreAdapter | None = None,
    ) -> None:
        self.settings = settings
        if settings.stub_fail_source and settings.stub_fail_source not in SOURCES:
            raise ValueError(f"STUB_FAIL_SOURCE must be one of {SOURCES}")
        self.connectors = (
            dict(connectors)
            if connectors is not None
            else {
                source: StubConnector(
                    source,
                    settings.stub_failure_mode if settings.stub_fail_source == source else None,
                )
                for source in SOURCES
            }
        )
        if set(self.connectors) != set(SOURCES):
            raise ValueError(f"connectors must supply exactly {SOURCES}")
        self.evidence = EvidenceLog(settings.evidence_path)
        self.store = DocumentStore(settings.database_path)
        self.guards = SourceGuards(settings)
        self.embedder = embedder or LazyEmbeddings(settings)
        self.vectorstore = vectorstore

    async def close(self) -> None:
        try:
            if self.vectorstore is not None:
                await self.vectorstore.close()
        finally:
            self.store.close()

    async def audit(
        self,
        state: IngestionState,
        stage: str,
        event: str,
        *,
        source: str | None = None,
        details: JSONDict | None = None,
    ) -> None:
        await asyncio.to_thread(
            self.evidence.append,
            EvidenceLogEntry(
                ingest_run_id=state["ingest_run_id"],
                stage=stage,
                event=event,
                source=source,
                langsmith_run_id=state.get("langsmith_run_id"),
                details=details or {},
            ),
        )

    def node(self, name: str, action: Node, source: str | None = None) -> RunnableLambda:
        async def execute(state: IngestionState) -> IngestionState:
            await self.audit(state, name, "started", source=source)
            timer = LatencyTimer()
            try:
                result = await action(state)
            except Exception as exc:
                await self.audit(
                    state, name, "failed", source=source, details={"error_type": type(exc).__name__}
                )
                raise
            await self.audit(
                state, name, "completed", source=source, details={"duration_ms": timer.elapsed_ms}
            )
            return result

        def execute_sync(state: IngestionState) -> IngestionState:
            # SqliteSaver supports synchronous invoke; async runtimes use afunc.
            return asyncio.run(execute(state))

        return RunnableLambda(execute_sync, afunc=execute, name=name)

    async def plan_sources(self, state: IngestionState) -> IngestionState:
        return {"sources": list(SOURCES)}

    def fetch_node(self, source: str) -> Node:
        async def fetch(state: IngestionState) -> IngestionState:
            timer = LatencyTimer()
            connector = self.connectors[source]
            items: list[JsonValue] = []
            status = StreamStatus(source=source)
            try:
                items = await self.guards.for_source(connector.source).call(connector.fetch)
                status = status.model_copy(update={"records_fetched": len(items)})
                async with asyncio.timeout(self.settings.http_timeout_seconds):
                    health = await connector.health()
                status = status.model_copy(
                    update={
                        "status": health.status,
                        "message": health.message,
                    }
                )
            except Exception as exc:
                limited = isinstance(exc, RateLimitedError) or (
                    isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429
                )
                status = status.model_copy(
                    update={
                        "status": "rate_limited"
                        if limited
                        else (
                            "degraded" if items or isinstance(exc, CircuitOpenError) else "failed"
                        ),
                        # Do not serialize URLs/request headers/API keys from provider exceptions.
                        "message": type(exc).__name__,
                    }
                )
            status = status.model_copy(update={"fetch_latency_ms": timer.elapsed_ms})
            await self.audit(
                state,
                f"fetch_{source}",
                "stream_status",
                source=source,
                details=status.model_dump(mode="json"),
            )
            return {
                "raw": {
                    source: {
                        "items": items,
                        "fetched_at": utcnow().isoformat(),
                        "fetch_latency_ms": status.fetch_latency_ms,
                    }
                },
                "statuses": {source: status.model_dump(mode="json")},
            }

        return fetch

    async def normalize(self, state: IngestionState) -> IngestionState:
        import time

        documents: list[JSONDict] = []
        statuses: dict[str, JSONDict] = {}
        started: dict[str, float] = {}
        for source in SOURCES:
            status = StreamStatus.model_validate(state["statuses"][source])
            batch = state["raw"][source]
            if not batch["items"]:
                continue
            started[source] = time.perf_counter()
            try:
                async with asyncio.timeout(self.settings.http_timeout_seconds):
                    records = await self.connectors[source].normalize(batch["items"])
                normalized: list[JSONDict] = []
                for record in records:
                    payload = record.model_dump(mode="json")
                    payload.update(
                        {
                            "source": source,
                            "ingest_run_id": state["ingest_run_id"],
                            "langsmith_run_id": state.get("langsmith_run_id"),
                            "fetched_at": batch["fetched_at"],
                            "fetch_latency_ms": batch["fetch_latency_ms"],
                            "content_hash": "",
                        }
                    )
                    normalized.append(
                        RECORD_ADAPTER.validate_python(payload).model_dump(mode="json")
                    )
                documents.extend(normalized)
                status = status.model_copy(update={"records_normalized": len(normalized)})
            except Exception as exc:
                status = status.model_copy(
                    update={
                        "status": "degraded",
                        "message": f"normalize: {type(exc).__name__}",
                    }
                )
            statuses[source] = status.model_dump(mode="json")
        return {"documents": documents, "statuses": statuses, "process_started": started}

    async def dedupe(self, state: IngestionState) -> IngestionState:
        seen: set[str] = set()
        documents: list[JSONDict] = []
        duplicates = 0
        for payload in state["documents"]:
            record = RECORD_ADAPTER.validate_python(payload)
            if record.content_hash in seen or self.store.contains(record.content_hash):
                duplicates += 1
                continue
            seen.add(record.content_hash)
            documents.append(payload)
        return {"documents": documents, "duplicates": duplicates}

    async def enrich_tags(self, state: IngestionState) -> IngestionState:
        documents: list[JSONDict] = []
        for payload in state["documents"]:
            record = RECORD_ADAPTER.validate_python(payload)
            tags = set(record.theme_tags)
            if record.source in SOURCE_THEMES:
                tags.add(SOURCE_THEMES[record.source])
            # Weather measurements alone are not evidence of an extreme event.
            documents.append(
                record.model_copy(update={"theme_tags": sorted(tags)}).model_dump(mode="json")
            )
        return {"documents": documents}

    async def embed_and_index(self, state: IngestionState) -> IngestionState:
        import time

        indexed = 0
        statuses: dict[str, JSONDict] = {}
        documents: list[JSONDict] = []
        for payload in state["documents"]:
            record = RECORD_ADAPTER.validate_python(payload)
            started = state["process_started"][record.source]
            error: str | None = None
            try:
                if self.vectorstore is None:
                    self.vectorstore = create_vectorstore(self.settings)
                # Includes parsing, barrier/queue delay, embedding and indexing. Enforce
                # remaining budget rather than falsely claiming a slow item met the SLA.
                remaining = self.settings.process_budget_ms / 1000 - (time.perf_counter() - started)
                async with asyncio.timeout(max(0, remaining)):
                    vector = await self.embedder.embed(record.text or record.model_dump_json())
                    record = record.model_copy(
                        update={
                            "process_latency_ms": (time.perf_counter() - started) * 1000,
                        }
                    )
                    await self.vectorstore.upsert(record, vector)
            except Exception as exc:
                error = type(exc).__name__
            elapsed = (time.perf_counter() - started) * 1000
            if elapsed >= self.settings.process_budget_ms:
                error = error or "process_budget_exceeded"
            record = record.model_copy(
                update={
                    "process_latency_ms": elapsed,
                    "data_quality": "degraded" if error else record.data_quality,
                }
            )
            if not error:
                try:
                    self.store.insert(record)
                    indexed += 1
                except Exception as exc:
                    error = f"persist: {type(exc).__name__}"
                    record = record.model_copy(update={"data_quality": "degraded"})
            if error:
                status = StreamStatus.model_validate(
                    statuses.get(record.source, state["statuses"][record.source])
                ).model_copy(update={"status": "degraded", "message": error})
                statuses[record.source] = status.model_dump(mode="json")
            await self.audit(
                state,
                "embed_and_index",
                "record_processed",
                source=record.source,
                details={
                    "content_hash": record.content_hash,
                    "error": error,
                    "fetch_latency_ms": record.fetch_latency_ms,
                    "process_latency_ms": record.process_latency_ms,
                },
            )
            logger.info(
                "record=%s fetch_latency_ms=%.3f process_latency_ms=%.3f error=%s",
                record.content_hash,
                record.fetch_latency_ms,
                record.process_latency_ms,
                error,
            )
            documents.append(record.model_dump(mode="json"))
        return {"indexed": indexed, "statuses": statuses, "documents": documents}

    async def write_evidence(self, state: IngestionState) -> IngestionState:
        await self.audit(
            state,
            "write_evidence",
            "run_summary",
            details={
                "indexed": state["indexed"],
                "duplicates": state["duplicates"],
                "statuses": dict(state["statuses"]),
            },
        )
        return {}

    async def report(self, state: IngestionState) -> IngestionState:
        return {"report": render_report(state["statuses"], state["indexed"], state["duplicates"])}

    def build_graph(self, checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
        builder = StateGraph(IngestionState)
        builder.add_node("plan_sources", self.node("plan_sources", self.plan_sources))
        builder.add_edge(START, "plan_sources")
        fetch_nodes = []
        for source in SOURCES:
            name = f"fetch_{source}"
            fetch_nodes.append(name)
            builder.add_node(name, self.node(name, self.fetch_node(source), source))
            builder.add_edge("plan_sources", name)
        actions: dict[str, Node] = {
            "normalize": self.normalize,
            "dedupe": self.dedupe,
            "enrich_tags": self.enrich_tags,
            "embed_and_index": self.embed_and_index,
            "write_evidence": self.write_evidence,
            "report": self.report,
        }
        stages = list(actions)
        for name, action in actions.items():
            builder.add_node(name, self.node(name, action))
        # A list-valued edge is a barrier: normalize runs once after all six fetches.
        builder.add_edge(fetch_nodes, "normalize")
        for left, right in zip(stages, stages[1:], strict=False):
            builder.add_edge(left, right)
        builder.add_edge("report", END)
        return builder.compile(checkpointer=checkpointer)
