"""FRED (Federal Reserve Economic Data) async connector for macroeconomic series."""

import logging
from datetime import UTC, datetime

import httpx
from pydantic import JsonValue

from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.resilience import RateLimitedError
from fin_terminal.schemas import Document, MacroIndicator, StreamStatus

logger = logging.getLogger("fin_terminal")

SERIES_UNITS: dict[str, str] = {
    "DCOILWTICO": "USD/bbl",
    "CPIAUCSL": "Index 1982-1984=100",
    "FEDFUNDS": "Percent",
    "T10Y2Y": "Percent Spread",
}


class FredMacroConnector(AsyncConnector):
    """Fetches macroeconomic indicators via Federal Reserve Economic Data (FRED) API."""

    def __init__(
        self,
        api_key: str,
        series: list[str] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        limit: int = 5,
        timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key
        self.series = series or ["DCOILWTICO", "CPIAUCSL", "FEDFUNDS"]
        self.limit = limit
        self._client = client
        self.timeout = timeout

    @property
    def source(self) -> str:
        return "macro"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    async def fetch(self) -> list[JsonValue]:
        results: list[JsonValue] = []
        client = await self._get_client()
        should_close = self._client is None
        try:
            for sid in self.series:
                url = (
                    f"https://api.stlouisfed.org/fred/series/observations?"
                    f"series_id={sid}&api_key={self.api_key}&file_type=json&sort_order=desc&limit={self.limit}"
                )
                response = await client.get(url)
                if response.status_code == 429:
                    raise RateLimitedError("FRED API rate limited (HTTP 429)")
                response.raise_for_status()
                data = response.json()
                results.append({"series_id": sid, "observations": data.get("observations", [])})
        finally:
            if should_close:
                await client.aclose()
        return results

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for batch in raw:
            if not isinstance(batch, dict):
                continue
            series_id = batch.get("series_id")
            observations = batch.get("observations", [])
            unit = SERIES_UNITS.get(str(series_id), "units")

            for obs in observations:
                if not isinstance(obs, dict):
                    continue
                raw_val = obs.get("value")
                # Zero-fabrication: FRED returns "." for missing or holiday data points
                value: float | None = None
                if raw_val is not None and raw_val != ".":
                    try:
                        value = float(raw_val)
                    except (ValueError, TypeError):
                        value = None

                date_str = obs.get("date")
                observed_at: datetime | None = None
                if date_str:
                    try:
                        observed_at = datetime.fromisoformat(f"{date_str}T00:00:00+00:00")
                    except ValueError:
                        observed_at = None

                record = MacroIndicator(
                    kind="macro",
                    source="macro",
                    provider="fred",
                    series_id=str(series_id),
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                    source_url=f"https://fred.stlouisfed.org/series/{series_id}",
                    text=f"FRED macro observation {series_id}: {value} {unit} on {date_str}",
                    fetched_at=datetime.now(UTC),
                    ingest_run_id="init",
                )
                records.append(record)
        return records

    async def health(self) -> StreamStatus:
        return StreamStatus(
            source=self.source,
            status="ok",
            message=f"FRED macro feed active for {','.join(self.series)}",
        )
