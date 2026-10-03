"""Provider observations; currency and absent values are never inferred."""

from datetime import UTC, datetime

import httpx
from pydantic import JsonValue

from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.connectors.http import HTTPConnector
from fin_terminal.schemas import Document, NewsArticle, PricePoint, utcnow

THEME_QUERY_PARAMS = {
    "news_tariff": {"topics": "economy_macro,manufacturing"},
    "news_banktax": {"topics": "financial_markets"},
    "news_war": {"topics": "energy_transportation"},
}


def optional_number(value: object) -> float | None:
    if value is None or value in ("", ".", "null", "N/A"):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class AlphaVantageMarketConnector(HTTPConnector):
    provider = "alpha_vantage"

    def __init__(
        self,
        api_key: str,
        tickers: list[str] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.api_key, self._client, self.timeout = api_key, client, timeout
        self.tickers = tickers if tickers is not None else []

    @property
    def source(self) -> str:
        return "prices"

    async def fetch(self) -> list[JsonValue]:
        quotes: list[JsonValue] = []
        for symbol in self.tickers:
            data = await self.request_json(
                "https://www.alphavantage.co/query",
                {
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": self.api_key,
                },
            )
            quote = data.get("Global Quote")
            if not isinstance(quote, dict) or not quote:
                raise ConnectorError("unavailable_quote")
            quotes.append(quote)
        return quotes

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("01. symbol"):
                raise ConnectorError("missing_symbol")
            symbol = str(item["01. symbol"])
            day = item.get("07. latest trading day")
            observed = datetime.fromisoformat(f"{day}T00:00:00+00:00") if day else None
            price = optional_number(item.get("05. price"))
            volume = optional_number(item.get("06. volume"))
            records.append(
                PricePoint(
                    source=self.source,
                    provider=self.provider,
                    symbol=symbol,
                    price=price,
                    volume=volume,
                    currency=None,
                    observed_at=observed,
                    source_url=f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}",
                    text=(f"Alpha Vantage quote {symbol}: price={price}; "
                          f"volume={volume}; date={day}"),
                    fetched_at=utcnow(),
                    ingest_run_id="pending",
                )
            )
        return records


class AlphaVantageNewsConnector(HTTPConnector):
    provider = "alpha_vantage"

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
            raise ValueError("unknown news source")
        self._source, self.api_key, self._client = source, api_key, client
        self.limit, self.timeout = limit, timeout

    @property
    def source(self) -> str:
        return self._source

    async def fetch(self) -> list[JsonValue]:
        data = await self.request_json(
            "https://www.alphavantage.co/query",
            {
                "function": "NEWS_SENTIMENT",
                **THEME_QUERY_PARAMS[self.source],
                "limit": self.limit,
                "apikey": self.api_key,
            },
        )
        if not isinstance(data.get("feed"), list):
            raise ConnectorError("unavailable_feed")
        return data["feed"]

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("title") or not item.get("url"):
                raise ConnectorError("unsourced_news")
            stamp = item.get("time_published")
            published = (
                datetime.strptime(str(stamp), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
                if stamp
                else None
            )
            records.append(
                NewsArticle(
                    source=self.source,
                    provider="alpha_vantage_news",
                    title=str(item["title"]),
                    text=str(item.get("summary") or item["title"]),
                    source_url=str(item["url"]),
                    published_at=published,
                    observed_at=published,
                    fetched_at=utcnow(),
                    ingest_run_id="pending",
                )
            )
        return records
