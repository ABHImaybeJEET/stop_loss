"""Macro context from FRED via the existing ingestion connector (values never imputed)."""

import asyncio

from fin_terminal.config import secret_value
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.connectors.fred import FredMacroConnector
from fin_terminal.schemas import MacroIndicator
from stop_loss.analytics.http import Cached
from stop_loss.analytics.models import MacroIndicatorView, MacroSnapshot
from stop_loss.settings import TerminalSettings

LABELS = {
    "DCOILWTICO": "WTI crude oil",
    "CPIAUCSL": "US CPI (all items)",
    "FEDFUNDS": "Fed funds rate",
    "T10Y2Y": "10Y-2Y Treasury spread",
    "DGS10": "10Y Treasury yield",
}
UNITS = {"DGS10": "Percent"}


def summarize_series(series_id: str, records: list[MacroIndicator]) -> MacroIndicatorView:
    """records: newest first, as FRED returns with sort_order=desc. Nulls ('.') are skipped."""
    valued = [r for r in records if r.value is not None and r.observed_at is not None]
    latest = valued[0] if valued else None
    previous = valued[1] if len(valued) > 1 else None
    yoy = None
    if series_id == "CPIAUCSL" and latest and len(valued) >= 13 and valued[12].value:
        yoy = (latest.value / valued[12].value - 1) * 100
    return MacroIndicatorView(
        series_id=series_id,
        label=LABELS.get(series_id, series_id),
        unit=(latest.unit if latest else None) or UNITS.get(series_id),
        latest=latest.value if latest else None,
        latest_date=latest.observed_at.date().isoformat() if latest else None,
        previous=previous.value if previous else None,
        previous_date=previous.observed_at.date().isoformat() if previous else None,
        change=(latest.value - previous.value) if latest and previous else None,
        yoy_pct=yoy,
        source_url=f"https://fred.stlouisfed.org/series/{series_id}",
    )


def macro_flags(indicators: list[MacroIndicatorView]) -> list[str]:
    by_id = {i.series_id: i for i in indicators}
    flags: list[str] = []
    spread = by_id.get("T10Y2Y")
    if spread and spread.latest is not None and spread.latest < 0:
        flags.append("yield_curve_inverted")
    cpi = by_id.get("CPIAUCSL")
    if cpi and cpi.yoy_pct is not None and cpi.yoy_pct >= 4:
        flags.append("inflation_above_4pct")
    oil = by_id.get("DCOILWTICO")
    if (
        oil
        and oil.latest is not None
        and oil.previous
        and abs(oil.latest / oil.previous - 1) >= 0.05
    ):
        flags.append("oil_move_over_5pct")
    return flags


class MacroClient:
    def __init__(self, settings: TerminalSettings) -> None:
        self.settings = settings
        self.api_key = secret_value(settings.fred_api_key)
        self._cache = Cached(settings.macro_cache_seconds)

    async def snapshot(self) -> MacroSnapshot:
        if not self.api_key:
            raise ConnectorError("fred_key_missing")
        if (hit := self._cache.get("snapshot")) is not None:
            return hit
        series = self.settings.terminal_macro_series
        results = await asyncio.gather(
            *(self._series(sid) for sid in series), return_exceptions=True
        )
        indicators = [
            summarize_series(sid, records)
            for sid, records in zip(series, results, strict=True)
            if not isinstance(records, BaseException)
        ]
        if not indicators:
            raise ConnectorError("macro_unavailable")
        snapshot = MacroSnapshot(indicators=indicators, flags=macro_flags(indicators))
        self._cache.put("snapshot", snapshot)
        return snapshot

    async def _series(self, series_id: str) -> list[MacroIndicator]:
        connector = FredMacroConnector(self.api_key or "", [series_id], limit=13)
        connector.setup_http(self.settings)
        try:
            raw = await connector.fetch()
            records = await connector.normalize(raw)
        finally:
            await connector.close()
        return [r for r in records if isinstance(r, MacroIndicator)]
