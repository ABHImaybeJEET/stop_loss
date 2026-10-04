"""FastAPI service for the terminal. Intended to sit behind the Next.js route handlers,
which verify the Firebase session and forward the user id (X-User-Id)."""

import asyncio
import hmac
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from fin_terminal.config import secret_value
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.resilience import CircuitOpenError, RateLimitedError
from fin_terminal.schemas import EvidenceLogEntry
from stop_loss.agents.models import ChatRequest
from stop_loss.agents.run_events import RunRecord
from stop_loss.agents.service import AnalysisService
from stop_loss.analytics.http import Cached
from stop_loss.analytics.yahoo import VALID_INTERVALS, VALID_RANGES, SymbolNotFoundError
from stop_loss.api.feedback import FeedbackIn, FeedbackOut, FeedbackStore
from stop_loss.api.graph_runs import GraphRunRegistry
from stop_loss.api.newsfeed import build_feed
from stop_loss.api.portfolio import PortfolioData, parse_holdings, parse_symbols
from stop_loss.api.run_store import RunStore
from stop_loss.api.runs import Run, RunRegistry, ThreadBusyError
from stop_loss.retrieval.live import source_intervals
from stop_loss.retrieval.source_health import SourceHealth, SourceHealthStore
from stop_loss.settings import TerminalSettings, get_terminal_settings
from stop_loss.symbols import is_nse_symbol, nse_symbol

logger = logging.getLogger("stop_loss.api")
SYMBOL_PATTERN = r"^[A-Za-z0-9.&_\-^]{1,32}$"
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


def create_app(
    settings: TerminalSettings | None = None, service: AnalysisService | None = None
) -> FastAPI:
    settings = settings or get_terminal_settings()
    service = service or AnalysisService(settings)
    registry = RunRegistry(service, settings)
    run_store = RunStore(settings.runs_db_path)
    graph_runs = GraphRunRegistry(service, settings, run_store)
    feedback = FeedbackStore(settings.feedback_db_path)
    source_health = SourceHealthStore(
        settings.source_health_db_path, down_after=settings.live_down_after_failures
    )
    feed_cache = Cached(300)
    token = secret_value(settings.api_internal_token)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await service.start()
        yield
        await registry.aclose()
        await graph_runs.aclose()
        await service.aclose()
        feedback.close()
        run_store.close()
        source_health.close()

    app = FastAPI(title="StopLoss Terminal API", version="0.2.0", lifespan=lifespan)

    async def internal(x_internal_token: Annotated[str | None, Header()] = None) -> None:
        if token and not hmac.compare_digest(x_internal_token or "", token):
            raise HTTPException(status_code=401, detail="invalid_internal_token")

    async def user(
        x_user_id: Annotated[str, Header(min_length=1, max_length=128)],
        _: None = Depends(internal),
    ) -> str:
        return x_user_id

    @app.exception_handler(SymbolNotFoundError)
    async def not_found(_: Request, exc: SymbolNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": "symbol_not_found", "symbol": exc.symbol}
        )

    @app.exception_handler(RateLimitedError)
    @app.exception_handler(CircuitOpenError)
    async def throttled(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "provider_unavailable"},
            headers={"Retry-After": "15"},
        )

    @app.exception_handler(ConnectorError)
    async def upstream(_: Request, exc: ConnectorError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": exc.code})

    @app.get("/health", dependencies=[Depends(internal)])
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "llm_enabled": service.llm_enabled,
            "model": (
                settings.groq_chat_model
                if settings.llm_provider == "groq"
                else settings.openai_chat_model
            )
            if service.llm_enabled
            else None,
        }

    @app.get("/health/sources", dependencies=[Depends(internal)])
    async def health_sources() -> dict[str, Any]:
        """Live-ingestion source health (written by `stop-loss-vectors live`). A source the
        loop has never run is reported down, never assumed healthy."""
        known = {h.source: h for h in await asyncio.to_thread(source_health.snapshot)}
        sources = [
            known.get(name)
            or SourceHealth(
                source=name, status="down", last_error="never_run", interval_seconds=interval
            )
            for name, interval in source_intervals(settings).items()
        ]
        sources += [h for name, h in known.items() if name not in source_intervals(settings)]
        return {"sources": [s.model_dump() for s in sources]}

    @app.get("/assets/search", dependencies=[Depends(internal)])
    async def search(
        q: Annotated[str, Query(min_length=1, max_length=64)],
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> dict[str, Any]:
        query_str = q.strip()
        matches, _ = await service.kit.yahoo.search(query_str, quotes=limit, news=0)
        return {
            "results": [
                {
                    "symbol": m.symbol,
                    "name": m.name,
                    "shortname": m.name,
                    "longname": m.name,
                    "exchange": m.exchange or "NSE",
                    "quoteType": m.quote_type or "EQUITY",
                    "sector": m.sector,
                }
                for m in matches
            ]
        }

    @app.get("/market/chart", dependencies=[Depends(internal)])
    async def chart(
        symbol: Annotated[str, Query(pattern=SYMBOL_PATTERN)],
        range: Annotated[str, Query()] = "1d",  # noqa: A002 - public API name
        interval: Annotated[str, Query()] = "5m",
    ) -> dict[str, Any]:
        if range not in VALID_RANGES or interval not in VALID_INTERVALS:
            raise HTTPException(status_code=422, detail="invalid_range_or_interval")
        try:
            symbol = nse_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        series = await service.kit.yahoo.chart(symbol, range, interval)
        return series.model_dump(mode="json")

    @app.get("/market/quote", dependencies=[Depends(internal)])
    async def quote(symbol: Annotated[str, Query(pattern=SYMBOL_PATTERN)]) -> dict[str, Any]:
        try:
            symbol = nse_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        series = await service.kit.yahoo.quote(symbol)
        last = series.bars[-1] if series.bars else None
        return {
            "symbol": series.symbol,
            "price": series.price,
            "change_pct": series.change_pct,
            "previous_close": series.previous_close,
            "currency": series.currency,
            "market_state": series.market_state,
            "market_time": series.market_time.isoformat() if series.market_time else None,
            "last_bar": last.model_dump(mode="json") if last else None,
            "fetched_at": series.fetched_at.isoformat(),
        }

    portfolio = PortfolioData(service)

    @app.get("/portfolio/quotes", dependencies=[Depends(internal)])
    async def portfolio_quotes(symbols: Annotated[str, Query(max_length=600)]) -> dict[str, Any]:
        return await portfolio.quotes(parse_symbols(symbols))

    @app.get("/portfolio/news", dependencies=[Depends(internal)])
    async def portfolio_news(symbols: Annotated[str, Query(max_length=600)]) -> dict[str, Any]:
        return await portfolio.news(parse_symbols(symbols))

    @app.get("/portfolio/weather", dependencies=[Depends(internal)])
    async def portfolio_weather(symbols: Annotated[str, Query(max_length=600)]) -> dict[str, Any]:
        return await portfolio.weather(parse_symbols(symbols))

    @app.get("/portfolio/performance", dependencies=[Depends(internal)])
    async def portfolio_performance(
        holdings: Annotated[str, Query(max_length=900)],
        range: str = "6mo",  # noqa: A002
    ) -> dict[str, Any]:
        return await portfolio.performance(parse_holdings(holdings), range)

    @app.get("/news/feed", dependencies=[Depends(internal)])
    async def news_feed() -> dict[str, Any]:
        if (hit := feed_cache.get("feed")) is not None:
            return hit
        feed = await build_feed(service.kit.yahoo, service.kit.news, settings.feed_indian_tickers)
        if not feed.get("topStories"):
            print("WARNING: build_feed returned empty topStories:", feed)
        else:
            feed_cache.put("feed", feed)
        return feed

    def sse(run: Run, after: int, source: RunRegistry = registry) -> StreamingResponse:
        async def body() -> AsyncIterator[str]:
            yield f": run {run.run_id}\n\n"
            async for event in source.subscribe(run, after):
                if event is None:
                    yield ": ping\n\n"
                    continue
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {event['seq']}\ndata: {payload}\n\n"

        return StreamingResponse(body(), media_type="text/event-stream", headers=SSE_HEADERS)

    def start_run(source: RunRegistry, request: ChatRequest, user_id: str) -> Run:
        # Both registries drive the same checkpointed thread: one active run per thread.
        for other in (registry, graph_runs):
            busy = other.active_for_thread(user_id, request.thread_id)
            if other is not source and busy is not None:
                raise ThreadBusyError(busy)
        return source.start(request, user_id)

    @app.post("/chat")
    async def chat(request: ChatRequest, user_id: Annotated[str, Depends(user)]):
        try:
            run = start_run(registry, request, user_id)
        except ThreadBusyError as busy:
            raise HTTPException(
                status_code=409, detail={"code": "thread_busy", "run_id": busy.run.run_id}
            ) from None
        return sse(run, -1)

    @app.post("/runs")
    async def start_graph_run(request: ChatRequest, user_id: Annotated[str, Depends(user)]):
        """Ticker or portfolio run streamed as typed node lifecycle events (run_events.py)."""
        try:
            run = start_run(graph_runs, request, user_id)
        except ThreadBusyError as busy:
            raise HTTPException(
                status_code=409, detail={"code": "thread_busy", "run_id": busy.run.run_id}
            ) from None
        return sse(run, -1, graph_runs)

    @app.get("/runs/{run_id}")
    async def replay_run(run_id: str, user_id: Annotated[str, Depends(user)]) -> RunRecord:
        """Persisted run with every event in order (also works while the run is live)."""
        record = await asyncio.to_thread(run_store.get, run_id, user_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run_not_found")
        return record

    def owned(run_id: str, user_id: str) -> Run:
        run = registry.get(run_id, user_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run_not_found")
        return run

    @app.get("/chat/runs/{run_id}/events")
    async def resume(
        run_id: str,
        user_id: Annotated[str, Depends(user)],
        after: Annotated[int, Query(ge=-1)] = -1,
    ):
        return sse(owned(run_id, user_id), after)

    @app.post("/chat/runs/{run_id}/cancel")
    async def cancel(run_id: str, user_id: Annotated[str, Depends(user)]) -> dict[str, str]:
        await registry.cancel(owned(run_id, user_id))
        return {"status": "cancelled"}

    @app.get("/chat/threads/{thread_id}/active-run")
    async def active_run(
        thread_id: str, user_id: Annotated[str, Depends(user)]
    ) -> dict[str, str | None]:
        run = registry.active_for_thread(user_id, thread_id)
        return {
            "run_id": run.run_id if run else None,
            "message_id": run.message_id if run else None,
        }

    @app.post("/feedback")
    async def submit_feedback(
        item: FeedbackIn, user_id: Annotated[str, Depends(user)]
    ) -> FeedbackOut:
        saved = await asyncio.to_thread(feedback.upsert, user_id, item)
        _log_feedback(
            service,
            item.thread_id,
            item.message_id,
            "feedback_saved",
            {"rating": item.rating, "tags": list(item.tags)},
        )
        return saved

    @app.get("/feedback/{message_id}")
    async def get_feedback(message_id: str, user_id: Annotated[str, Depends(user)]) -> FeedbackOut:
        found = await asyncio.to_thread(feedback.get, user_id, message_id)
        if found is None:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return found

    @app.delete("/feedback/{message_id}")
    async def delete_feedback(message_id: str, user_id: Annotated[str, Depends(user)]):
        removed = await asyncio.to_thread(feedback.delete, user_id, message_id)
        if removed:
            _log_feedback(service, None, message_id, "feedback_removed", {})
        return {"removed": removed}

    return app


def _log_feedback(
    service: AnalysisService,
    thread_id: str | None,
    message_id: str,
    event: str,
    details: dict[str, Any],
) -> None:
    try:
        service.kit.evidence_log.append(
            EvidenceLogEntry(
                ingest_run_id=message_id,
                stage="feedback",
                event=event,
                details={"thread_id": thread_id, **details},
            )
        )
    except OSError as exc:
        logger.warning("evidence log append failed: %s", exc)


def main() -> None:
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("stop_loss.api.app:create_app", factory=True, host="0.0.0.0", port=port)
