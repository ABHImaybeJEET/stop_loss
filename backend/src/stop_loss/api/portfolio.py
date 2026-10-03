"""Dashboard endpoints for a user's NSE holdings. Holdings live in Firestore (client side);
these endpoints only receive symbols/quantities per request and return live data."""

import asyncio
import logging
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from stop_loss.agents.llm import classify_headlines
from stop_loss.agents.service import AnalysisService
from stop_loss.analytics.exposure import ExposurePoint, exposure_points
from stop_loss.analytics.hazards import near
from stop_loss.analytics.models import ChartSeries, NewsItem, Sentiment
from stop_loss.analytics.news import company_terms
from stop_loss.symbols import nse_symbol
from stop_loss.universe import Company, NseUniverse, get_universe

logger = logging.getLogger("stop_loss.api")
MAX_SYMBOLS = 30
MAX_NEWS_SYMBOLS = 8
MAX_WEATHER_LOCATIONS = 10
PERFORMANCE_RANGES = {"1mo", "3mo", "6mo", "1y"}
BENCHMARK = "^NSEI"


def parse_symbols(raw: str) -> list[str]:
    symbols: list[str] = []
    for part in raw.split(","):
        if not part.strip():
            continue
        try:
            symbol = nse_symbol(part, allow_index=False)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        if symbol not in symbols:
            symbols.append(symbol)
    if not symbols or len(symbols) > MAX_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"1-{MAX_SYMBOLS} NSE symbols required")
    return symbols


def parse_holdings(raw: str) -> dict[str, float]:
    holdings: dict[str, float] = {}
    for part in raw.split(","):
        symbol, _, qty = part.partition(":")
        try:
            quantity = float(qty)
        except ValueError:
            raise HTTPException(status_code=422, detail="holdings must be SYMBOL:QTY") from None
        if quantity <= 0:
            raise HTTPException(status_code=422, detail="quantities must be positive")
        normalized = parse_symbols(symbol)[0]
        holdings[normalized] = holdings.get(normalized, 0) + quantity
    if not holdings or len(holdings) > MAX_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"1-{MAX_SYMBOLS} holdings required")
    return holdings


def company_json(company: Company | None, symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": company.name if company else symbol.removesuffix(".NS"),
        "sector": company.sector if company else None,
        "industry": company.industry if company else None,
        "city": company.city if company else None,
    }


class SentimentCache:
    """Headline id -> model label; bounded so the dashboard never re-classifies."""

    def __init__(self, size: int = 4000) -> None:
        self._labels: OrderedDict[str, Sentiment] = OrderedDict()
        self.size = size

    def get(self, item_id: str) -> Sentiment | None:
        return self._labels.get(item_id)

    def put(self, labels: dict[str, Sentiment]) -> None:
        self._labels.update(labels)
        while len(self._labels) > self.size:
            self._labels.popitem(last=False)


class PortfolioData:
    def __init__(self, service: AnalysisService, universe: NseUniverse | None = None) -> None:
        self.service = service
        self.kit = service.kit
        self.universe = universe or get_universe()
        self.sentiment = SentimentCache()

    async def _company(self, symbol: str) -> Company | None:
        return await self.universe.ensure_profile(symbol, self.kit.yahoo)

    async def quotes(self, symbols: list[str]) -> dict[str, Any]:
        async def one(symbol: str) -> dict[str, Any]:
            company, series = await asyncio.gather(
                self._company(symbol), self.kit.yahoo.quote(symbol), return_exceptions=True
            )
            row = company_json(None if isinstance(company, BaseException) else company, symbol)
            if isinstance(series, BaseException):
                return {**row, "status": "unavailable", "error": type(series).__name__}
            return {
                **row,
                "status": "ok",
                "price": series.price,
                "change_pct": series.change_pct,
                "previous_close": series.previous_close,
                "currency": series.currency,
                "market_state": series.market_state,
                "market_time": series.market_time.isoformat() if series.market_time else None,
            }

        rows = await asyncio.gather(*(one(s) for s in symbols))
        return {"quotes": rows, "fetched_at": datetime.now(UTC).isoformat()}

    async def news(self, symbols: list[str]) -> dict[str, Any]:
        """Headlines per holding (Google News RSS, Indian publisher RSS, GDELT, yfinance)."""
        merged: dict[str, NewsItem] = {}
        tags: dict[str, list[str]] = {}
        failures: dict[str, str] = {}

        async def one(symbol: str) -> None:
            company = await self._company(symbol)
            name = company.name if company and company.name != symbol[:-3] else symbol[:-3]
            try:
                items, failed = await self.kit.news.collect(
                    f'"{name}"',
                    yahoo=self.kit.yahoo,
                    symbol=symbol,
                    terms=company_terms(name, symbol),
                )
            except Exception as exc:  # noqa: BLE001 - one holding's feed never fails the rest
                failures[symbol] = type(exc).__name__
                return
            failures.update({f"{symbol}:{k}": v for k, v in failed.items()})
            for item in items[:8]:
                merged.setdefault(item.id, item)
                tags.setdefault(item.id, []).append(symbol)
            await self._classify(name, items[:8])

        await asyncio.gather(*(one(s) for s in symbols[:MAX_NEWS_SYMBOLS]))
        far_past = datetime.min.replace(tzinfo=UTC)
        ordered = sorted(merged.values(), key=lambda i: i.published_at or far_past, reverse=True)
        items = []
        for item in ordered[:40]:
            label = item.sentiment or self.sentiment.get(item.id)
            items.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "publisher": item.publisher,
                    "url": item.url,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "sentiment": label,
                    "sentiment_source": item.sentiment_source or ("llm" if label else None),
                    "themes": [t.value for t in item.themes],
                    "symbols": tags.get(item.id, []),
                    "provider": item.provider,
                }
            )
        return {"items": items, "failures": failures}

    async def _classify(self, company: str, items: list[NewsItem]) -> None:
        model = self.kit.model_for("news")
        pending = [i for i in items if i.sentiment is None and self.sentiment.get(i.id) is None]
        if model is None or not pending:
            return
        labels = await classify_headlines(model, company, pending)
        if labels:
            self.sentiment.put(labels)

    async def weather(self, symbols: list[str]) -> dict[str, Any]:
        """7-day forecasts at each holding's exposure points (head office + sector hubs),
        plus live GDACS/USGS hazard alerts within 600 km of any of them."""
        companies = await asyncio.gather(*(self._company(s) for s in symbols))
        point_lists = await asyncio.gather(
            *(exposure_points(c, self.kit.weather) if c else _no_points() for c in companies)
        )
        places: dict[str, dict[str, Any]] = {}
        for symbol, points in zip(symbols, point_lists, strict=True):
            for p in points:
                entry = places.setdefault(p.label, {"point": p, "symbols": []})
                entry["symbols"].append(symbol)

        async def one(entry: dict[str, Any]) -> dict[str, Any]:
            p = entry["point"]
            try:
                outlook = await self.kit.weather.outlook(
                    p.latitude, p.longitude, location=p.label, reason=p.reason
                )
            except Exception as exc:  # noqa: BLE001 - one location failing never fails the rest
                logger.warning("weather unavailable for %s: %s", p.label, type(exc).__name__)
                return {
                    "location": p.label,
                    "symbols": entry["symbols"],
                    "error": type(exc).__name__,
                }
            return {**outlook.model_dump(mode="json"), "symbols": entry["symbols"]}

        selected = list(places.values())[:MAX_WEATHER_LOCATIONS]
        results = await asyncio.gather(*(one(e) for e in selected))
        alerts: list[dict[str, Any]] = []
        alerts_status = "unavailable"
        if self.kit.hazards is not None:
            try:
                live = await self.kit.hazards.alerts()
                tracked = [
                    (e["point"].label, e["point"].latitude, e["point"].longitude) for e in selected
                ]
                alerts = [a.model_dump(mode="json") for a in near(live, tracked)]
                alerts_status = "ok"
            except Exception as exc:  # noqa: BLE001 - alerts are additive context
                logger.warning("hazard feeds unavailable: %s", type(exc).__name__)
        missing = [s for s, pts in zip(symbols, point_lists, strict=True) if not pts]
        return {
            "locations": [r for r in results if "error" not in r],
            "unavailable": [r for r in results if "error" in r],
            "without_location": missing,
            "alerts": alerts,
            "alerts_status": alerts_status,
        }

    async def performance(self, holdings: dict[str, float], range_: str) -> dict[str, Any]:
        """Daily portfolio value vs NIFTY 50 on dates where every included series traded."""
        if range_ not in PERFORMANCE_RANGES:
            raise HTTPException(status_code=422, detail="range must be 1mo, 3mo, 6mo or 1y")
        symbols = list(holdings)
        results = await asyncio.gather(
            *(self.kit.yahoo.chart(s, range_, "1d") for s in [*symbols, BENCHMARK]),
            return_exceptions=True,
        )
        closes: dict[str, dict[str, float]] = {}
        excluded: list[str] = []
        for symbol, series in zip([*symbols, BENCHMARK], results, strict=True):
            if isinstance(series, BaseException) or not isinstance(series, ChartSeries):
                excluded.append(symbol)
                continue
            closes[symbol] = {
                bar.t.date().isoformat(): bar.close for bar in series.bars if bar.close
            }
        included = [s for s in symbols if s in closes and closes[s]]
        if not included:
            return {"dates": [], "value": [], "portfolio": [], "nifty": [], "excluded": excluded}
        dates = sorted(set.intersection(*(set(closes[s]) for s in included)))
        value = [sum(holdings[s] * closes[s][d] for s in included) for d in dates]
        bench = closes.get(BENCHMARK, {})
        nifty = [bench.get(d) for d in dates]
        base_nifty = next((v for v in nifty if v), None)
        return {
            "dates": dates,
            "value": value,
            "portfolio": [v / value[0] * 100 for v in value] if value else [],
            # NIFTY has no close on some dates: those points stay null rather than filled.
            "nifty": [v / base_nifty * 100 if v and base_nifty else None for v in nifty],
            "excluded": [s for s in symbols if s not in included]
            + ([BENCHMARK] if BENCHMARK in excluded else []),
        }


async def _no_points() -> list[ExposurePoint]:
    return []
