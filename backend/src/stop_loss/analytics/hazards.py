"""Live natural-hazard alerts near India: GDACS (cyclones, floods, quakes, ...) and USGS."""

import math
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import Field

from fin_terminal.config import Settings
from fin_terminal.connectors.errors import ConnectorError
from stop_loss.analytics.http import Cached, GuardedHTTP
from stop_loss.analytics.models import Frozen

GDACS = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
USGS_WEEK = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
# Indian subcontinent + surrounding seas (Arabian Sea, Bay of Bengal, Andaman Sea).
REGION = {"lat_min": 0.0, "lat_max": 38.0, "lon_min": 60.0, "lon_max": 100.0}
GDACS_TYPES = {
    "TC": "tropical cyclone",
    "FL": "flood",
    "EQ": "earthquake",
    "DR": "drought",
    "WF": "wildfire",
    "VO": "volcano",
}


class HazardAlert(Frozen):
    source: Literal["gdacs", "usgs"]
    event_type: str
    name: str
    alert_level: str | None = None
    country: str | None = None
    latitude: float
    longitude: float
    started_at: str | None = None
    ended_at: str | None = None
    current: bool | None = None
    magnitude: float | None = None
    severity: str | None = None
    url: str | None = None
    nearby: list[dict[str, Any]] = Field(default_factory=list)


def in_region(lat: float, lon: float) -> bool:
    return (
        REGION["lat_min"] <= lat <= REGION["lat_max"]
        and REGION["lon_min"] <= lon <= REGION["lon_max"]
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _point(feature: dict[str, Any]) -> tuple[float, float] | None:
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") if geometry.get("type") == "Point" else None
    if isinstance(coords, list) and len(coords) >= 2:
        try:
            return float(coords[1]), float(coords[0])
        except (TypeError, ValueError):
            return None
    return None


def parse_gdacs(payload: dict[str, Any]) -> list[HazardAlert]:
    alerts: list[HazardAlert] = []
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        point = _point(feature)
        if point is None or not in_region(*point):
            continue
        severity = props.get("severitydata") or {}
        url = props.get("url") or {}
        alerts.append(
            HazardAlert(
                source="gdacs",
                event_type=GDACS_TYPES.get(
                    str(props.get("eventtype")), str(props.get("eventtype"))
                ),
                name=str(props.get("name") or props.get("eventname") or "Unnamed event"),
                alert_level=props.get("alertlevel"),
                country=props.get("country"),
                latitude=point[0],
                longitude=point[1],
                started_at=props.get("fromdate"),
                ended_at=props.get("todate"),
                current=props.get("iscurrent") in (True, "true", "True"),
                severity=severity.get("severitytext") if isinstance(severity, dict) else None,
                url=url.get("report") if isinstance(url, dict) else None,
            )
        )
    return alerts


def parse_usgs(payload: dict[str, Any]) -> list[HazardAlert]:
    alerts: list[HazardAlert] = []
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        point = _point(feature)
        if point is None or not in_region(*point):
            continue
        when = props.get("time")
        started = (
            datetime.fromtimestamp(when / 1000, UTC).isoformat()
            if isinstance(when, int | float)
            else None
        )
        alerts.append(
            HazardAlert(
                source="usgs",
                event_type="earthquake",
                name=str(props.get("title") or props.get("place") or "Earthquake"),
                alert_level=props.get("alert"),
                latitude=point[0],
                longitude=point[1],
                started_at=started,
                magnitude=props.get("mag") if isinstance(props.get("mag"), int | float) else None,
                url=props.get("url"),
            )
        )
    return alerts


class HazardClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.http = GuardedHTTP(settings, rate_per_second=1, burst=2, client=client)
        self._cache = Cached(600)

    async def alerts(self) -> list[HazardAlert]:
        """Current alerts in the India region; a failing feed degrades to the other."""
        if (hit := self._cache.get("alerts")) is not None:
            return hit
        results: list[HazardAlert] = []
        failures = 0
        for url, params, parser in (
            (GDACS, {"eventlist": "TC;FL;EQ;DR;WF", "alertlevel": "Green;Orange;Red"}, parse_gdacs),
            (USGS_WEEK, None, parse_usgs),
        ):
            try:
                results.extend(parser(await self.http.get_json(url, params)))
            except Exception:  # noqa: BLE001 - one hazard feed failing never blocks the other
                failures += 1
        if failures == 2:
            raise ConnectorError("hazard_feeds_unavailable")
        self._cache.put("alerts", results)
        return results

    async def global_events(self) -> list[HazardAlert]:
        """Current GDACS events worldwide (a Gulf of Mexico hurricane matters to NSE
        energy names through crude prices even though it is far from India)."""
        if (hit := self._cache.get("global")) is not None:
            return hit
        payload = await self.http.get_json(
            GDACS, {"eventlist": "TC;FL;EQ;DR;WF", "alertlevel": "Green;Orange;Red"}
        )
        events: list[HazardAlert] = []
        for feature in payload.get("features") or []:
            props = feature.get("properties") or {}
            point = _point(feature)
            if point is None:
                continue
            severity = props.get("severitydata") or {}
            url = props.get("url") or {}
            events.append(
                HazardAlert(
                    source="gdacs",
                    event_type=GDACS_TYPES.get(
                        str(props.get("eventtype")), str(props.get("eventtype"))
                    ),
                    name=str(props.get("name") or props.get("eventname") or "Unnamed event"),
                    alert_level=props.get("alertlevel"),
                    country=props.get("country"),
                    latitude=point[0],
                    longitude=point[1],
                    started_at=props.get("fromdate"),
                    ended_at=props.get("todate"),
                    current=props.get("iscurrent") in (True, "true", "True"),
                    severity=severity.get("severitytext") if isinstance(severity, dict) else None,
                    url=url.get("report") if isinstance(url, dict) else None,
                )
            )
        self._cache.put("global", events)
        return events

    async def aclose(self) -> None:
        await self.http.aclose()


def near(
    alerts: list[HazardAlert], places: list[tuple[str, float, float]], radius_km: float = 600
) -> list[HazardAlert]:
    """Alerts annotated with the tracked places within radius_km (others dropped)."""
    out: list[HazardAlert] = []
    for alert in alerts:
        hits = [
            {
                "place": name,
                "distance_km": round(haversine_km(lat, lon, alert.latitude, alert.longitude)),
            }
            for name, lat, lon in places
            if haversine_km(lat, lon, alert.latitude, alert.longitude) <= radius_km
        ]
        if hits:
            out.append(
                alert.model_copy(update={"nearby": sorted(hits, key=lambda h: h["distance_km"])})
            )
    return out
