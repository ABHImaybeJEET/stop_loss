from datetime import datetime

import httpx
from pydantic import JsonValue

from fin_terminal.connectors.alphavantage import optional_number
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.connectors.http import HTTPConnector
from fin_terminal.schemas import Document, MacroIndicator, utcnow

SERIES_UNITS = {
    "DCOILWTICO": "USD/bbl",
    "CPIAUCSL": "Index 1982-1984=100",
    "FEDFUNDS": "Percent",
    "T10Y2Y": "Percent Spread",
}


class FredMacroConnector(HTTPConnector):
    provider = "fred"

    def __init__(
        self,
        api_key: str,
        series: list[str] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        limit: int = 5,
        timeout: float = 15.0,
    ) -> None:
        self.api_key, self._client, self.timeout = api_key, client, timeout
        self.series, self.limit = series if series is not None else [], limit

    @property
    def source(self) -> str:
        return "macro"

    async def fetch(self) -> list[JsonValue]:
        results: list[JsonValue] = []
        for sid in self.series:
            data = await self.request_json(
                "https://api.stlouisfed.org/fred/series/observations",
                {
                    "series_id": sid,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": self.limit,
                },
            )
            if not isinstance(data.get("observations"), list):
                raise ConnectorError("unavailable_observations")
            results.extend(
                {"series_id": sid, "observations": [obs]} for obs in data["observations"]
            )
        return results

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for batch in raw:
            if not isinstance(batch, dict) or not batch.get("series_id"):
                raise ConnectorError("missing_series")
            sid = str(batch["series_id"])
            for obs in batch.get("observations", []):
                if not isinstance(obs, dict):
                    raise ConnectorError("invalid_observation")
                date = obs.get("date")
                value = optional_number(obs.get("value"))
                records.append(
                    MacroIndicator(
                        source=self.source,
                        provider=self.provider,
                        series_id=sid,
                        value=value,
                        unit=SERIES_UNITS.get(sid),
                        observed_at=datetime.fromisoformat(f"{date}T00:00:00+00:00")
                        if date
                        else None,
                        source_url=f"https://fred.stlouisfed.org/series/{sid}",
                        text=f"FRED {sid}: {value} on {date}",
                        fetched_at=utcnow(),
                        ingest_run_id="pending",
                    )
                )
        return records
