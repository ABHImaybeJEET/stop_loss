"""NSE stock observations from the same yfinance client used by the terminal."""

import asyncio

from pydantic import JsonValue

from fin_terminal.config import Settings
from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.schemas import Document, PricePoint, StreamStatus, utcnow
from stop_loss.analytics.models import ChartSeries
from stop_loss.analytics.yahoo import YahooFinanceClient
from stop_loss.symbols import nse_symbol


class YFinanceMarketConnector(AsyncConnector):
    provider = "yfinance"
    source = "prices"

    def __init__(self, settings: Settings, client: YahooFinanceClient | None = None) -> None:
        self.client = client or YahooFinanceClient(settings)
        self.tickers = [nse_symbol(s) for s in settings.market_tickers]
        self._status = StreamStatus(source=self.source, status="degraded", message="not_fetched")

    async def fetch(self) -> list[JsonValue]:
        results = await asyncio.gather(
            *(self.client.quote(symbol) for symbol in self.tickers), return_exceptions=True
        )
        successes: list[JsonValue] = []
        errors = 0
        for value in results:
            if isinstance(value, Exception):
                errors += 1
            elif isinstance(value, BaseException):
                raise value
            else:
                successes.append(value.model_dump(mode="json"))
        self._status = StreamStatus(
            source=self.source,
            status="failed"
            if errors and not successes
            else ("degraded" if errors or not self.tickers else "ok"),
            records_fetched=len(successes),
            message=f"{errors} tickers unavailable" if errors else None,
        )
        return successes

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for item in raw:
            series = ChartSeries.model_validate(item)
            records.append(
                PricePoint(
                    source=self.source,
                    provider=self.provider,
                    symbol=nse_symbol(series.symbol),
                    price=series.price,
                    currency=series.currency,
                    volume=series.volume,
                    observed_at=series.market_time,
                    fetched_at=series.fetched_at,
                    source_url=series.source_url,
                    ingest_run_id="pending",
                    text=f"NSE quote {series.symbol}",
                    data_quality=series.data_quality,
                )
            )
        return records

    async def health(self) -> StreamStatus:
        return self._status.model_copy(update={"checked_at": utcnow()})

    async def close(self) -> None:
        await self.client.aclose()
