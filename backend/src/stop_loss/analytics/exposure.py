"""Physical exposure points for NSE companies: head office + sector hubs.

Sector hubs are labelled as *sector* exposure (where that industry's capacity is
concentrated), never as a specific company's facility, which the data does not record.
"""

from dataclasses import dataclass

from stop_loss.analytics.weather import WeatherClient
from stop_loss.universe import Company

# India's largest refining cluster (Jamnagar, Gujarat) for Energy-sector holdings.
SECTOR_HUBS: dict[str, list[tuple[str, float, float]]] = {
    "Energy": [("Jamnagar refining hub, Gujarat", 22.4707, 70.0577)],
}


@dataclass(frozen=True)
class ExposurePoint:
    label: str
    latitude: float
    longitude: float
    reason: str


async def exposure_points(company: Company, weather: WeatherClient) -> list[ExposurePoint]:
    points: list[ExposurePoint] = []
    if company.city:
        code = "IN" if (company.country or "India") == "India" else None
        try:
            place = await weather.geocode(company.city, code)
        except Exception:  # noqa: BLE001 - an unknown city just drops the head-office point
            place = None
        if place:
            lat, lon, label = place
            points.append(ExposurePoint(label, lat, lon, "Head office"))
    for label, lat, lon in SECTOR_HUBS.get(company.sector or "", []):
        points.append(ExposurePoint(label, lat, lon, f"{company.sector} sector hub"))
    return points
