"""Alpha Vantage async connectors for real-time market prices and news feeds."""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import JsonValue

from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.resilience import RateLimitedError
from fin_terminal.schemas import Document, NewsArticle, PricePoint, StreamStatus

logger = logging.getLogger("fin_terminal")

THEME_QUERY_PARAMS: dict[str, dict[str, str]] = {
    "news_tariff": {
        "topics": "economy_macro,manufacturing",
    },
    "news_banktax": {
        "topics": "financial_markets",
    },
    "news_war": {
        "topics": "energy_transportation",
    },
}


class AlphaVantageMarketConnector(AsyncConnector):
    """Fetches real-time equity/ETF quotes via Alpha Vantage GLOBAL_QUOTE."""

    def __init__(
        self,
        api_key: str,
        tickers: list[str] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key
        self.tickers = tickers or ["SPY", "XOM"]
        self._client = client
        self.timeout = timeout

    @property
    def source(self) -> str:
        return "prices"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    async def fetch(self) -> list[JsonValue]:
        quotes: list[JsonValue] = []
        client = await self._get_client()
        should_close = self._client is None
        try:
            for symbol in self.tickers:
                url = (
                    f"https://www.alphavantage.co/query?"
                    f"function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.api_key}"
                )
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                # Detect Alpha Vantage rate limit notifications
                note = data.get("Note") or data.get("Information")
                if note and (
                    "rate limit" in note.lower()
                    or "frequency" in note.lower()
                    or "api call" in note.lower()
                ):
                    raise RateLimitedError(f"Alpha Vantage rate limited: {note}")

                if "Global Quote" in data and data["Global Quote"]:
                    quotes.append(data["Global Quote"])
        finally:
            if should_close:
                await client.aclose()
        return quotes

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            symbol = item.get("01. symbol")
            if not symbol:
                continue

            raw_price = item.get("05. price")
            try:
                price = float(raw_price) if raw_price is not None else None
            except (ValueError, TypeError):
                price = None

            raw_volume = item.get("06. volume")
            try:
                volume = float(raw_volume) if raw_volume is not None else None
            except (ValueError, TypeError):
                volume = None

            day_str = item.get("07. latest trading day")
            observed_at: datetime | None = None
            if day_str:
                try:
                    observed_at = datetime.fromisoformat(f"{day_str}T00:00:00+00:00")
                except ValueError:
                    observed_at = None

            record = PricePoint(
                kind="price",
                source="prices",
                provider="alpha_vantage",
                symbol=symbol,
                price=price,
                volume=volume,
                currency="USD",
                observed_at=observed_at,
                source_url=f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}",
                text=f"Alpha Vantage market quote {symbol}: ${price} (vol: {volume}) on {day_str}",
                fetched_at=datetime.now(UTC),
                ingest_run_id="init",
            )
            records.append(record)
        return records

    async def health(self) -> StreamStatus:
        return StreamStatus(
            source=self.source,
            status="ok",
            message=f"Alpha Vantage market quotes active for {','.join(self.tickers)}",
        )


class AlphaVantageNewsConnector(AsyncConnector):
    """Fetches real-time news intelligence via Alpha Vantage NEWS_SENTIMENT."""

    def __init__(
        self,
        source: str,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        limit: int = 5,
        timeout: float = 15.0,
    ) -> None:
        if source not in THEME_QUERY_PARAMS:
            raise ValueError(f"source {source} must be one of {list(THEME_QUERY_PARAMS)}")
        self._source = source
        self.api_key = api_key
        self.limit = limit
        self._client = client
        self.timeout = timeout

    @property
    def source(self) -> str:
        return self._source

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    async def fetch(self) -> list[JsonValue]:
        params = THEME_QUERY_PARAMS[self.source]
        topics = params["topics"]
        url = (
            f"https://www.alphavantage.co/query?"
            f"function=NEWS_SENTIMENT&topics={topics}&limit={self.limit}&apikey={self.api_key}"
        )
        client = await self._get_client()
        should_close = self._client is None
        try:
            response = await client.get(url)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

            note = data.get("Note") or data.get("Information")
            if note and (
                "rate limit" in note.lower()
                or "frequency" in note.lower()
                or "api call" in note.lower()
            ):
                raise RateLimitedError(f"Alpha Vantage rate limited: {note}")

            feed: list[JsonValue] = data.get("feed", [])
            return feed
        finally:
            if should_close:
                await client.aclose()

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            if not title:
                continue

            summary = item.get("summary") or title
            url = item.get("url")
            time_pub = item.get("time_published")
            published_at: datetime | None = None
            if time_pub:
                try:
                    published_at = datetime.strptime(time_pub, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
                except ValueError:
                    published_at = None

            record = NewsArticle(
                kind="news",
                source=self.source,
                provider="alpha_vantage_news",
                title=title,
                text=summary,
                source_url=url,
                published_at=published_at,
                observed_at=published_at,
                fetched_at=datetime.now(UTC),
                ingest_run_id="init",
            )
            records.append(record)
        return records

    async def health(self) -> StreamStatus:
        return StreamStatus(
            source=self.source,
            status="ok",
            message=f"Alpha Vantage news connected for {self.source}",
        )
