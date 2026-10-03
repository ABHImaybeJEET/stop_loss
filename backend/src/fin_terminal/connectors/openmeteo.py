"""Open-Meteo async connector for weather patterns and extreme telemetry."""

import logging
from datetime import UTC, datetime

import httpx
from pydantic import JsonValue

from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.connectors.http import HTTPConnector
from fin_terminal.schemas import Document, WeatherEvent

logger = logging.getLogger("fin_terminal")


class OpenMeteoWeatherConnector(HTTPConnector):
    """Fetches real-time atmospheric conditions via Open-Meteo API."""

    provider = "open_meteo"

    def __init__(
        self,
        latitude: float = 27.8006,
        longitude: float = -97.3964,
        location_name: str = "Corpus Christi, Texas",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.location_name = location_name
        self._client = client
        self.timeout = timeout

    @property
    def source(self) -> str:
        return "weather"

    async def fetch(self) -> list[JsonValue]:
        data = await self.request_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "timezone": "UTC",
                "current": "temperature_2m,wind_speed_10m,precipitation",
            },
        )
        if not isinstance(data.get("current"), dict):
            raise ConnectorError("unavailable_weather")
        return [data]

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            current = item.get("current", {})
            current_units = item.get("current_units", {})
            time_str = current.get("time")

            observed_at: datetime | None = None
            if time_str:
                try:
                    parsed = datetime.fromisoformat(str(time_str))
                    observed_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
                except ValueError:
                    observed_at = None

            metrics = ["wind_speed_10m", "temperature_2m", "precipitation"]
            for metric in metrics:
                val = current.get(metric)
                value: float | None = float(val) if val is not None else None
                unit = current_units.get(metric)

                record = WeatherEvent(
                    kind="weather",
                    source="weather",
                    provider="open_meteo",
                    location=self.location_name,
                    metric=metric,
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                    source_url=(
                        f"https://api.open-meteo.com/v1/forecast?latitude={self.latitude}"
                        f"&longitude={self.longitude}&timezone=UTC"
                    ),
                    text=f"Weather at {self.location_name}: {metric}={value} {unit} at {time_str}",
                    fetched_at=datetime.now(UTC),
                    ingest_run_id="init",
                )
                records.append(record)
        return records
