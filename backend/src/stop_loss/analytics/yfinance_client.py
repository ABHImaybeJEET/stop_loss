"""Bounded async adapter over the synchronous yfinance SDK, restricted to NSE."""

import asyncio
import hashlib
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, TypeVar

from fin_terminal.config import Settings
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.resilience import RateLimitedError, SourceGuard
from stop_loss.analytics.http import Cached
from stop_loss.analytics.models import AssetMatch, AssetProfile, ChartSeries, NewsItem
from stop_loss.analytics.yahoo_parsers import (
    INTRADAY_INTERVALS,
    VALID_INTERVALS,
    VALID_RANGES,
    SymbolNotFoundError,
    last_session,
    parse_chart,
    parse_quote_summary,
    text,
)
from stop_loss.symbols import is_nse_symbol, market_symbol, nse_symbol
from stop_loss.universe import get_universe

T = TypeVar("T")


def parse_yfinance_news(rows: list[dict[str, Any]]) -> list[NewsItem]:
    items: list[NewsItem] = []
    for row in rows:
        content = row.get("content") or row
        url = (content.get("canonicalUrl") or {}).get("url") or content.get("link")
        title = text(content.get("title"))
        if not title or not isinstance(url, str) or not url.startswith(("https://", "http://")):
            continue
        stamp = content.get("pubDate") or content.get("providerPublishTime")
        published = None
        try:
            if isinstance(stamp, (int, float)):
                published = datetime.fromtimestamp(stamp, UTC)
            elif isinstance(stamp, str):
                published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if published.tzinfo is None:
                    published = None
        except (ValueError, OverflowError, OSError):
            pass
        items.append(
            NewsItem(
                id=str(row.get("id") or hashlib.sha256(url.encode()).hexdigest()[:16]),
                publisher=(content.get("provider") or {}).get("displayName")
                or content.get("publisher")
                or "Yahoo Finance",
                title=title,
                url=url,
                published_at=published,
                summary=text(content.get("summary")),
                provider="yfinance",
                related_tickers=[s for s in row.get("relatedTickers", []) if is_nse_symbol(s)],
            )
        )
    return items


class YahooFinanceClient:
    def __init__(self, settings: Settings, *, sdk: Any = None) -> None:
        self.settings = settings
        self.sdk = sdk  # injectable SDK for offline fixture tests
        self.guard = SourceGuard(
            settings.model_copy(
                update={
                    "source_rate_per_second": settings.yahoo_rate_per_second,
                    "source_burst": 2,
                }
            )
        )
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yfinance")
        self._slots = asyncio.Semaphore(2)
        self._quotes = Cached(settings.quote_cache_seconds)
        self._history = Cached(settings.history_cache_seconds)
        self._profiles = Cached(settings.profile_cache_seconds)
        self._search = Cached(settings.news_cache_seconds)

    def _sdk(self) -> Any:
        if self.sdk is None:
            import yfinance

            self.sdk = yfinance
        return self.sdk

    async def _call(self, action: Callable[[], T]) -> T:
        async def operation() -> T:
            await self._slots.acquire()
            loop = asyncio.get_running_loop()
            try:
                future = self._executor.submit(action)
            except Exception:
                self._slots.release()
                raise

            # A cancelled await does not stop a blocking SDK request. Hold capacity
            # until the actual worker finishes, so timeouts cannot grow its queue.
            def finished(_: object) -> None:
                if not loop.is_closed():
                    loop.call_soon_threadsafe(self._slots.release)

            future.add_done_callback(finished)
            try:
                return await asyncio.wrap_future(future)
            except Exception as exc:
                if type(exc).__name__ == "YFRateLimitError":
                    raise RateLimitedError("yfinance_rate_limited") from None
                if isinstance(exc, (ConnectorError, ValueError)):
                    raise
                raise ConnectorError(f"yfinance_{type(exc).__name__}", retryable=True) from None

        return await self.guard.call(operation)

    def _history_payload(self, symbol: str, range_: str, interval: str) -> dict[str, Any]:
        ticker = self._sdk().Ticker(symbol)
        frame = ticker.history(
            period=range_,
            interval=interval,
            auto_adjust=False,
            back_adjust=False,
            repair=False,
            keepna=True,
            actions=False,
            raise_errors=True,
            timeout=self.settings.http_timeout_seconds,
        )
        meta = ticker.get_history_metadata()
        # pandas' JSON encoder turns NaN into null and preserves exchange timestamps.
        split = json.loads(frame.to_json(orient="split", date_unit="s"))
        columns = split.get("columns", [])
        data = split.get("data", [])
        quotes = {
            name.lower(): [row[columns.index(name)] for row in data]
            for name in ("Open", "High", "Low", "Close", "Volume")
            if name in columns
        }
        return {
            "chart": {
                "result": [
                    {
                        "meta": meta,
                        "timestamp": split.get("index", []),
                        "indicators": {"quote": [quotes]},
                    }
                ],
                "error": None,
            }
        }

    async def chart(self, symbol: str, range_: str, interval: str) -> ChartSeries:
        symbol = market_symbol(symbol)
        if range_ not in VALID_RANGES or interval not in VALID_INTERVALS:
            raise ValueError("invalid_range_or_interval")
        cache = self._quotes if interval in INTRADAY_INTERVALS else self._history
        key = f"{symbol}|{range_}|{interval}"
        if (hit := cache.get(key)) is not None:
            return hit

        async def fetch(period: str) -> ChartSeries:
            payload = await self._call(lambda: self._history_payload(symbol, period, interval))
            meta = payload["chart"]["result"][0].get("meta") or {}
            if not meta:
                raise SymbolNotFoundError(symbol)
            if meta.get("symbol") and meta["symbol"].upper() != symbol:
                raise ConnectorError("yfinance_symbol_mismatch")
            return parse_chart(payload, symbol, period, interval)

        # A 1-day request returns no rows on weekends/holidays and yfinance (raise_errors=True)
        # reports that as "possibly delisted", which also trips the circuit breaker. Always
        # fetch 5 days and keep the latest session: one call, and correct when closed.
        series = await fetch("5d" if range_ == "1d" else range_)
        if range_ == "1d":
            series = last_session(series)
        cache.put(key, series)
        return series

    async def quote(self, symbol: str) -> ChartSeries:
        return await self.chart(symbol, "1d", "1m")

    async def profile(self, symbol: str) -> AssetProfile:
        symbol = nse_symbol(symbol)
        if (hit := self._profiles.get(symbol)) is not None:
            return hit
        info = await self._call(lambda: self._sdk().Ticker(symbol).get_info())
        if not info:
            raise SymbolNotFoundError(symbol)
        if info.get("symbol") and info["symbol"].upper() != symbol:
            raise ConnectorError("yfinance_symbol_mismatch")
        profile = parse_quote_summary(
            {
                "quoteSummary": {
                    "result": [
                        {
                            "assetProfile": info,
                            "price": info,
                            "summaryDetail": info,
                            "defaultKeyStatistics": info,
                        }
                    ]
                }
            },
            symbol,
        )
        self._profiles.put(symbol, profile)
        return profile

    async def search(
        self, query: str, *, quotes: int = 50, news: int = 0
    ) -> tuple[list[AssetMatch], list[NewsItem]]:
        key = f"{query.lower()}|{quotes}|{news}"
        if (hit := self._search.get(key)) is not None and hit[0]:
            return hit

        # Asset search runs over the local NSE universe (instant, no Yahoo quota).
        matches = [
            AssetMatch(
                symbol=c.symbol,
                name=c.name,
                exchange="NSE",
                quote_type="EQUITY",
                sector=c.sector,
            )
            for c in get_universe().search(query, limit=quotes)
        ]
        result = (matches[:quotes], [])
        if matches:
            self._search.put(key, result)
        return result

    async def ticker_news(self, symbol: str) -> list[NewsItem]:
        symbol = nse_symbol(symbol)
        key = f"news:{symbol}"
        if (hit := self._search.get(key)) is not None:
            return hit
        rows = await self._call(lambda: self._sdk().Ticker(symbol).get_news(count=12))
        items = parse_yfinance_news(rows)
        self._search.put(key, items)
        return items

    async def aclose(self) -> None:
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=True)
