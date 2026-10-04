"""Readers that turn data/processed files into provenance-carrying Documents.

Streaming (csv module, no pandas) so multi-hundred-MB files never load into memory.
Rows without a URL keep `raw_reference` (file + line) and are flagged `missing_fields`
by the schema; values absent in the source stay absent (never imputed).
"""

import csv
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fin_terminal.schemas import Document, NewsArticle, utcnow
from stop_loss.analytics.themes import tag_themes

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

BASINS = {
    "NA": "North Atlantic",
    "EP": "Eastern Pacific",
    "WP": "Western Pacific",
    "NI": "North Indian",
    "SI": "South Indian",
    "SP": "South Pacific",
    "SA": "South Atlantic",
}
FINANCE_TERMS = re.compile(
    r"\b(sensex|nifty|bse|nse|sebi|rbi|stocks?|shares?|market|rupee|inflation|gdp|banks?|"
    r"crude|oil|gold|ipo|earnings|profit|tariffs?|taxe?s?|fdi|econom\w*|fiscal|budget|"
    r"investors?|mutual funds?|bonds?|yields?|interest rates?|exports?|imports?|forex)\b",
    re.I,
)
RUN_ID = "backfill"
# Dataset name -> Document.source (used to purge/re-index a single dataset).
SOURCE_IDS = {
    "stock_news": "hist_stock_news",
    "india_news": "hist_india_news",
    "companies": "hist_company_profiles",
    "cyclones": "hist_cyclones",
    "earthquakes": "hist_earthquakes",
}


def cyclone_region(basin: str, lat: float | None, lon: float | None) -> str | None:
    """Coarse, deterministic sea/region label from basin + position (searchable words)."""
    if lat is None or lon is None:
        return None
    if basin == "NA":
        if 18 <= lat <= 31 and -98 <= lon <= -80:
            return "Gulf of Mexico"
        if 9 <= lat < 22 and -88 <= lon <= -60:
            return "Caribbean Sea"
        return "Atlantic Ocean, US East Coast" if lat >= 25 and lon > -82 else "Atlantic Ocean"
    if basin == "NI":
        return "Arabian Sea" if lon < 78 else "Bay of Bengal"
    if basin == "WP":
        if 0 <= lat <= 25 and 105 <= lon <= 121:
            return "South China Sea"
        return (
            "Western Pacific, near the Philippines, Japan and China"
            if lon < 150
            else ("Western Pacific")
        )
    if basin == "EP":
        return "Eastern Pacific, off Mexico" if lon < -100 else "Central and Eastern Pacific"
    if basin == "SI":
        if lon < 90:
            return "South-West Indian Ocean, near Madagascar and Mozambique"
        return "South-East Indian Ocean, off Australia"
    if basin == "SP":
        return "South Pacific, near Australia and Fiji"
    return None


def cyclone_intensity(wind_kt: float | None) -> tuple[str, int | None]:
    """Saffir-Simpson-equivalent class from peak wind (kt). Agencies differ in averaging
    period (1-min vs 10-min), so this is an equivalent label, not an official category."""
    if wind_kt is None:
        return "intensity not reported", None
    if wind_kt < 34:
        return "tropical depression", 0
    if wind_kt < 64:
        return "tropical storm", 0
    for floor, cat in ((137, 5), (113, 4), (96, 3), (83, 2), (64, 1)):
        if wind_kt >= floor:
            label = "major hurricane-strength" if cat >= 3 else "hurricane-strength"
            return f"Category {cat}-equivalent {label} cyclone", cat
    return "tropical storm", 0


@dataclass
class Record:
    """One document to embed plus extra filterable metadata and the text to embed."""

    document: Document
    embed_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    line: int = 0


def _dt(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None  # naive timestamps are ambiguous: leave unset


def _num(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if number == number else None


def _rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    with path.open(encoding="utf-8", newline="", errors="replace") as handle:
        yield from enumerate(csv.DictReader(handle), start=2)


def _ref(root: Path, path: Path, line: int) -> str:
    return f"data/processed/{path.relative_to(root).as_posix()}#L{line}"


def stock_news(root: Path) -> Iterator[Record]:
    path = root / "news" / "stock_news_2016_2026_cleaned.csv"
    for line, row in _rows(path):
        title = (row.get("title") or "").strip()
        if not title:
            continue
        description = (row.get("description") or "").strip()
        body = title if not description or description == title else f"{title}. {description}"
        url = (row.get("url") or "").strip()
        when = _dt(row.get("date"))
        doc = NewsArticle(
            source="hist_stock_news",
            provider="dataset:stock_news_2016_2026",
            title=title,
            text=body,
            source_url=url if url.startswith(("http://", "https://")) else None,
            raw_reference=_ref(root, path, line),
            published_at=when,
            observed_at=when,
            fetched_at=utcnow(),
            ingest_run_id=RUN_ID,
            theme_tags=tag_themes(body),
        )
        yield Record(
            doc,
            body,
            {
                "doc_type": "news",
                "dataset": "stock_news",
                "categories": [c for c in re.split(r"[|;,]", row.get("categories") or "") if c],
                "keywords": [k for k in re.split(r"[|;,]", row.get("matched_keywords") or "") if k],
                "impact_tier": (row.get("impact_tier") or "").strip() or None,
                "relevance_score": _num(row.get("relevance_score")),
            },
            line,
        )


def india_news(
    root: Path, *, min_year: int = 2015, categories: tuple[str, ...] = ("business",)
) -> Iterator[Record]:
    """Keeps finance-relevant headlines: a matching category OR finance/theme terms."""
    path = root / "news" / "india_news_cleaned.csv"
    wanted = tuple(c.lower() for c in categories)
    for line, row in _rows(path):
        when = _dt(row.get("publish_date"))
        if when is None or when.year < min_year:
            continue
        headline = (row.get("headline_text") or "").strip()
        category = (row.get("headline_category") or "").strip()
        if not headline:
            continue
        themes = tag_themes(headline)
        if not (
            any(w in category.lower() for w in wanted) or themes or FINANCE_TERMS.search(headline)
        ):
            continue
        doc = NewsArticle(
            source="hist_india_news",
            provider="dataset:india_news_headlines",
            title=headline,
            text=headline,
            raw_reference=_ref(root, path, line),
            published_at=when,
            observed_at=when,
            fetched_at=utcnow(),
            ingest_run_id=RUN_ID,
            theme_tags=themes,
        )
        yield Record(
            doc,
            headline,
            {"doc_type": "news", "dataset": "india_news", "category": category or None},
            line,
        )


def companies(root: Path) -> Iterator[Record]:
    path = root / "company_metadata_yfinance.json"
    data: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    for index, (ticker, info) in enumerate(data.items(), start=1):
        name = info.get("longName") or info.get("shortName") or ticker
        sector, industry = info.get("sector"), info.get("industry")
        summary = (info.get("longBusinessSummary") or "").strip()
        head = f"{name} ({ticker})" + (f", {sector} / {industry}" if sector or industry else "")
        body = f"{head}. {summary}" if summary else head
        doc = Document(
            source="hist_company_profiles",
            provider="dataset:company_metadata",
            text=body,
            raw_reference=f"data/processed/{path.name}#{ticker}",
            fetched_at=utcnow(),
            ingest_run_id=RUN_ID,
            theme_tags=tag_themes(summary),
        )
        market_cap = info.get("marketCap")
        yield Record(
            doc,
            body[:2000],
            {
                "doc_type": "company",
                "dataset": "company_metadata",
                "title": name,
                "tickers": [ticker],
                "sector": sector,
                "industry": industry,
                "market_cap": float(market_cap) if isinstance(market_cap, int | float) else None,
            },
            index,
        )


def raw_cyclone_basins(root: Path) -> dict[str, str]:
    """SID -> BASIN from the raw IBTrACS file.

    The pandas-based preprocessing read the North Atlantic code "NA" as missing, blanking
    the basin for every Atlantic storm in the cleaned file. The csv module keeps the literal.
    """
    raw = root.parent / "raw" / "calamity_historical_data" / "noaa_cyclones_since_2000.csv"
    if not raw.exists():
        return {}
    basins: dict[str, str] = {}
    for _, row in _rows(raw):
        sid, basin = (row.get("SID") or "").strip(), (row.get("BASIN") or "").strip()
        if sid and basin and sid not in basins:
            basins[sid] = basin
    return basins


def cyclones(root: Path) -> Iterator[Record]:
    """One document per storm (SID), aggregated from NOAA IBTrACS track points."""
    path = root / "calamities" / "cyclones_cleaned.csv"
    storms: dict[str, dict[str, Any]] = {}
    raw_basins: dict[str, str] | None = None
    for line, row in _rows(path):
        sid = (row.get("SID") or "").strip()
        when = _dt(row.get("ISO_TIME"))
        if not sid or when is None:
            continue
        storm = storms.setdefault(
            sid,
            {
                "name": (row.get("NAME") or "").strip(),
                "season": row.get("SEASON"),
                "basin": (row.get("BASIN") or "").strip(),
                "start": when,
                "end": when,
                "points": 0,
                "peak": None,
                "min_pres": None,
                "natures": set(),
                "first": (row.get("LAT"), row.get("LON")),
                "line": line,
            },
        )
        storm["start"], storm["end"] = min(storm["start"], when), max(storm["end"], when)
        storm["points"] += 1
        if nature := (row.get("NATURE") or "").strip():
            storm["natures"].add(nature)
        wind, pres = _num(row.get("WMO_WIND")), _num(row.get("WMO_PRES"))
        lat, lon = _num(row.get("LAT")), _num(row.get("LON"))
        if wind is not None and (storm["peak"] is None or wind > storm["peak"][0]):
            storm["peak"] = (wind, lat, lon, when)
        if pres is not None and (storm["min_pres"] is None or pres < storm["min_pres"]):
            storm["min_pres"] = pres
    if any(not s["basin"] for s in storms.values()):
        raw_basins = raw_cyclone_basins(root)
        for sid, s in storms.items():
            if not s["basin"] and sid in (raw_basins or {}):
                s["basin"] = raw_basins[sid]
                s["basin_restored"] = "basin_restored_from_raw_ibtracs"
            elif not s["basin"]:
                # pandas' default NA strings include "NA" but no other IBTrACS basin code
                # (IBTrACS itself writes "MM" for missing), so a blank basin was "NA".
                # Verified: 469/470 such storms start inside the North Atlantic box.
                s["basin"] = "NA"
                s["basin_restored"] = "basin_na_restored_from_pandas_nan"
    for sid, s in storms.items():
        named = s["name"] and s["name"].upper() not in {"UNNAMED", "NOT_NAMED", "NONAME"}
        name = s["name"].title() if named else "Unnamed storm"
        basin = BASINS.get(s["basin"], s["basin"] or "unknown basin")
        peak_lat, peak_lon = (s["peak"][1], s["peak"][2]) if s["peak"] else (None, None)
        first_lat, first_lon = _num(s["first"][0]), _num(s["first"][1])
        region = cyclone_region(s["basin"], peak_lat, peak_lon) or cyclone_region(
            s["basin"], first_lat, first_lon
        )
        intensity, category = cyclone_intensity(s["peak"][0] if s["peak"] else None)
        parts = [
            f"Tropical cyclone {name}: {intensity}"
            + (f" in the {region}" if region else "")
            + f" ({basin} basin, {s['season']} season), "
            f"from {s['start']:%Y-%m-%d} to {s['end']:%Y-%m-%d}."
        ]
        if s["peak"]:
            wind, lat, lon, _ = s["peak"]
            where = f" near {lat:.1f}, {lon:.1f}" if lat is not None and lon is not None else ""
            parts.append(f"Peak sustained wind {wind:g} kt{where}.")
        if s["min_pres"] is not None:
            parts.append(f"Minimum central pressure {s['min_pres']:g} hPa.")
        parts.append(f"{s['points']} track points.")
        body = " ".join(parts)
        doc = Document(
            source="hist_cyclones",
            provider="dataset:noaa_ibtracs",
            text=body,
            raw_reference=f"data/processed/calamities/{path.name}#SID={sid}",
            observed_at=s["start"],
            published_at=s["start"],
            fetched_at=utcnow(),
            ingest_run_id=RUN_ID,
            theme_tags=tag_themes("cyclone storm"),
            transformations=[s["basin_restored"]] if s.get("basin_restored") else [],
        )
        yield Record(
            doc,
            body,
            {
                "doc_type": "cyclone",
                "dataset": "noaa_ibtracs",
                "title": f"{name} ({s['season']})",
                "basin": s["basin"] or None,
                "region": region,
                "intensity_category": category,
                "max_wind_kt": s["peak"][0] if s["peak"] else None,
                "min_pressure_hpa": s["min_pres"],
                "end_ts": int(s["end"].timestamp()),
                "lat": s["peak"][1] if s["peak"] and s["peak"][1] is not None else None,
                "lon": s["peak"][2] if s["peak"] and s["peak"][2] is not None else None,
            },
            s["line"],
        )


def earthquakes(root: Path) -> Iterator[Record]:
    path = root / "calamities" / "earthquakes_cleaned.csv"
    for line, row in _rows(path):
        when, mag = _dt(row.get("time")), _num(row.get("mag"))
        if when is None or mag is None:
            continue
        place = (row.get("place") or "").strip() or "unknown location"
        depth = _num(row.get("depth"))
        lat, lon = _num(row.get("latitude")), _num(row.get("longitude"))
        body = f"Magnitude {mag:g} earthquake, {place}, on {when:%Y-%m-%d %H:%M} UTC" + (
            f", depth {depth:g} km." if depth is not None else "."
        )
        doc = Document(
            source="hist_earthquakes",
            provider="dataset:usgs_earthquakes",
            text=body,
            raw_reference=_ref(root, path, line),
            observed_at=when,
            published_at=when,
            fetched_at=utcnow(),
            ingest_run_id=RUN_ID,
        )
        yield Record(
            doc,
            body,
            {
                "doc_type": "earthquake",
                "dataset": "usgs_earthquakes",
                "title": f"M{mag:g} {place}",
                "magnitude": mag,
                "lat": lat,
                "lon": lon,
            },
            line,
        )


SOURCES = ("stock_news", "companies", "cyclones", "earthquakes", "india_news")
