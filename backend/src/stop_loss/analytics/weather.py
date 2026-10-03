"""Open-Meteo geocoding + 7-day forecast with explicit, documented extreme thresholds."""

from typing import Any

import httpx

from fin_terminal.connectors.errors import ConnectorError
from stop_loss.analytics.http import Cached, GuardedHTTP
from stop_loss.analytics.models import WeatherDay, WeatherExtreme, WeatherOutlook
from stop_loss.analytics.yahoo import num, text
from stop_loss.settings import TerminalSettings

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "wind_speed_10m_max,wind_gusts_10m_max"
)

# Thresholds (docs/DECISIONS.md ADR-T05): gusts >= 90 km/h (severe gale / storm force),
# >= 64.5 mm/day (IMD "heavy rain"), Tmax >= 40 C (heatwave), Tmin <= -15 C (hard freeze),
# WMO codes 95/96/99 (thunderstorm, with hail).
THRESHOLDS = {
    "wind_gust_max": (90.0, "km/h", "Severe wind gusts"),
    "precipitation_sum": (64.5, "mm", "Heavy rainfall"),
    "temp_max": (40.0, "°C", "Extreme heat"),
}
FREEZE_C = -15.0
THUNDERSTORM_CODES = {95, 96, 99}


def parse_geocode(payload: dict[str, Any]) -> tuple[float, float, str] | None:
    results = payload.get("results") or []
    if not results or not isinstance(results[0], dict):
        return None
    top = results[0]
    lat, lon = num(top.get("latitude")), num(top.get("longitude"))
    if lat is None or lon is None:
        return None
    label = ", ".join(p for p in (text(top.get("name")), text(top.get("country"))) if p)
    return lat, lon, label or "Unknown location"


def parse_forecast(
    payload: dict[str, Any], *, location: str, latitude: float, longitude: float, reason: str
) -> WeatherOutlook:
    daily = payload.get("daily")
    if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
        raise ConnectorError("unavailable_weather")

    def col(name: str, i: int) -> float | None:
        values = daily.get(name) or []
        return num(values[i]) if i < len(values) else None

    days: list[WeatherDay] = []
    extremes: list[WeatherExtreme] = []
    for i, date in enumerate(daily["time"]):
        code = col("weather_code", i)
        day = WeatherDay(
            date=str(date),
            weather_code=int(code) if code is not None else None,
            temp_max=col("temperature_2m_max", i),
            temp_min=col("temperature_2m_min", i),
            precipitation_sum=col("precipitation_sum", i),
            wind_speed_max=col("wind_speed_10m_max", i),
            wind_gust_max=col("wind_gusts_10m_max", i),
        )
        days.append(day)
        for field, (threshold, unit, label) in THRESHOLDS.items():
            value = getattr(day, field)
            if value is not None and value >= threshold:
                extremes.append(
                    WeatherExtreme(
                        date=day.date,
                        metric=field,
                        value=value,
                        threshold=threshold,
                        unit=unit,
                        description=f"{label}: {value:g} {unit} (≥ {threshold:g})",
                    )
                )
        if day.temp_min is not None and day.temp_min <= FREEZE_C:
            extremes.append(
                WeatherExtreme(
                    date=day.date,
                    metric="temp_min",
                    value=day.temp_min,
                    threshold=FREEZE_C,
                    unit="°C",
                    description=f"Hard freeze: {day.temp_min:g} °C (≤ {FREEZE_C:g})",
                )
            )
        if day.weather_code in THUNDERSTORM_CODES:
            extremes.append(
                WeatherExtreme(
                    date=day.date,
                    metric="weather_code",
                    value=float(day.weather_code),
                    threshold=95,
                    unit="WMO",
                    description="Thunderstorm forecast (WMO 95-99)",
                )
            )
    return WeatherOutlook(
        location=location,
        latitude=latitude,
        longitude=longitude,
        reason=reason,
        days=days,
        extremes=extremes,
        source_url=f"{FORECAST}?latitude={latitude}&longitude={longitude}&daily={DAILY_FIELDS}",
    )


class WeatherClient:
    def __init__(self, settings: TerminalSettings, client: httpx.AsyncClient | None = None) -> None:
        self.http = GuardedHTTP(settings, rate_per_second=4, burst=4, client=client)
        self._cache = Cached(settings.weather_cache_seconds)

    async def geocode(self, place: str) -> tuple[float, float, str] | None:
        key = f"geo|{place.lower()}"
        if (hit := self._cache.get(key)) is not None:
            return hit
        payload = await self.http.get_json(GEOCODE, {"name": place, "count": 1})
        result = parse_geocode(payload)
        if result is not None:
            self._cache.put(key, result)
        return result

    async def outlook(
        self, latitude: float, longitude: float, *, location: str, reason: str
    ) -> WeatherOutlook:
        key = f"fc|{latitude:.3f}|{longitude:.3f}"
        if (hit := self._cache.get(key)) is not None:
            return hit.model_copy(update={"reason": reason, "location": location})
        payload = await self.http.get_json(
            FORECAST,
            {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "UTC",
                "forecast_days": 7,
                "daily": DAILY_FIELDS,
            },
        )
        outlook = parse_forecast(
            payload, location=location, latitude=latitude, longitude=longitude, reason=reason
        )
        self._cache.put(key, outlook)
        return outlook

    async def aclose(self) -> None:
        await self.http.aclose()
