"""India-focused macro context: market series via yfinance (USD/INR, Brent, India VIX,
NIFTY Bank) and official statistics via FRED (India CPI, US 10Y). Values are never imputed;
each indicator carries its own observation date so stale series read as historical."""

import asyncio
from typing import Any

from fin_terminal.config import secret_value
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.connectors.fred import FredMacroConnector
from fin_terminal.schemas import MacroIndicator
from stop_loss.analytics.http import Cached
from stop_loss.analytics.models import MacroIndicatorView, MacroSnapshot
from stop_loss.settings import TerminalSettings

LABELS = {
    "INDCPIALLMINMEI": "India CPI (all items)",
    "DGS10": "US 10Y Treasury yield",
    "DCOILWTICO": "WTI crude oil",
    "CPIAUCSL": "US CPI (all items)",
    "FEDFUNDS": "Fed funds rate",
    "T10Y2Y": "US 10Y-2Y Treasury spread",
    "INR=X": "USD/INR",
    "BZ=F": "Brent crude",
    "^INDIAVIX": "India VIX",
    "^NSEBANK": "NIFTY Bank index",
}
UNITS = {
    "DGS10": "Percent",
    "INDCPIALLMINMEI": "Index 2015=100",
    "INR=X": "INR per USD",
    "BZ=F": "USD/bbl",
    "^INDIAVIX": "index",
    "^NSEBANK": "index points",
}
CPI_SERIES = {"CPIAUCSL", "INDCPIALLMINMEI"}
WEEK_SESSIONS = 5


def summarize_series(series_id: str, records: list[MacroIndicator]) -> MacroIndicatorView:
    """FRED records, newest first (sort_order=desc). Nulls ('.') are skipped."""
    valued = [r for r in records if r.value is not None and r.observed_at is not None]
    latest = valued[0] if valued else None
    previous = valued[1] if len(valued) > 1 else None
    yoy = None
    if series_id in CPI_SERIES and latest and len(valued) >= 13 and valued[12].value:
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
        change_pct=((latest.value / previous.value - 1) * 100)
        if latest and previous and previous.value
        else None,
        yoy_pct=yoy,
        source="FRED",
        source_url=f"https://fred.stlouisfed.org/series/{series_id}",
    )


def summarize_market(symbol: str, series: Any) -> MacroIndicatorView:
    """Latest daily close vs the close WEEK_SESSIONS sessions earlier."""
    bars = [b for b in series.bars if b.close is not None]
    latest = bars[-1] if bars else None
    previous = bars[-1 - WEEK_SESSIONS] if len(bars) > WEEK_SESSIONS else None
    return MacroIndicatorView(
        series_id=symbol,
        label=LABELS.get(symbol, symbol),
        unit=UNITS.get(symbol),
        latest=latest.close if latest else None,
        latest_date=latest.t.date().isoformat() if latest else None,
        previous=previous.close if previous else None,
        previous_date=previous.t.date().isoformat() if previous else None,
        change=(latest.close - previous.close) if latest and previous else None,
        change_pct=((latest.close / previous.close - 1) * 100)
        if latest and previous and previous.close
        else None,
        source="Yahoo Finance (yfinance)",
        source_url=f"https://finance.yahoo.com/quote/{symbol}",
    )


def macro_flags(indicators: list[MacroIndicatorView]) -> list[str]:
    """Documented thresholds (ADR T13): RBI's 6% CPI tolerance ceiling, India VIX > 20,
    a >1% weekly rupee move, and a >5% weekly crude move."""
    by_id = {i.series_id: i for i in indicators}
    flags: list[str] = []
    cpi = by_id.get("INDCPIALLMINMEI")
    if cpi and cpi.yoy_pct is not None and cpi.yoy_pct > 6:
        flags.append("india_cpi_above_rbi_band")
    us_cpi = by_id.get("CPIAUCSL")
    if us_cpi and us_cpi.yoy_pct is not None and us_cpi.yoy_pct >= 4:
        flags.append("us_inflation_above_4pct")
    spread = by_id.get("T10Y2Y")
    if spread and spread.latest is not None and spread.latest < 0:
        flags.append("us_yield_curve_inverted")
    vix = by_id.get("^INDIAVIX")
    if vix and vix.latest is not None and vix.latest > 20:
        flags.append("india_vix_elevated")
    inr = by_id.get("INR=X")
    if inr and inr.change_pct is not None and abs(inr.change_pct) > 1:
        flags.append("rupee_weakened_1w" if inr.change_pct > 0 else "rupee_strengthened_1w")
    for oil_id in ("BZ=F", "DCOILWTICO"):
        oil = by_id.get(oil_id)
        if oil and oil.change_pct is not None and abs(oil.change_pct) >= 5:
            flags.append("crude_move_over_5pct")
            break
    return flags


class MacroClient:
    def __init__(self, settings: TerminalSettings, yahoo: Any = None) -> None:
        self.settings = settings
        self.yahoo = yahoo
        self.api_key = secret_value(settings.fred_api_key)
        self._cache = Cached(settings.macro_cache_seconds)
        self._market_cache = Cached(900)

    async def snapshot(self) -> MacroSnapshot:
        fred_ids = self.settings.terminal_macro_series if self.api_key else []
        market_ids = self.settings.terminal_market_macro if self.yahoo is not None else []
        if not fred_ids and not market_ids:
            raise ConnectorError("macro_sources_unconfigured")
        fred = self._cache.get("fred")
        market = self._market_cache.get("market")
        jobs = []
        if fred is None:
            jobs.append(
                (
                    "fred",
                    asyncio.gather(*(self._series(s) for s in fred_ids), return_exceptions=True),
                )
            )
        if market is None:
            jobs.append(
                (
                    "market",
                    asyncio.gather(
                        *(self.yahoo.chart(s, "1mo", "1d") for s in market_ids),
                        return_exceptions=True,
                    ),
                )
            )
        results = dict(
            zip([n for n, _ in jobs], await asyncio.gather(*(j for _, j in jobs)), strict=True)
        )
        if fred is None:
            fred = [
                summarize_series(sid, r)
                for sid, r in zip(fred_ids, results["fred"], strict=True)
                if not isinstance(r, BaseException)
            ]
            if fred:
                self._cache.put("fred", fred)
        if market is None:
            market = [
                summarize_market(sid, r)
                for sid, r in zip(market_ids, results["market"], strict=True)
                if not isinstance(r, BaseException)
            ]
            if market:
                self._market_cache.put("market", market)
        indicators = [*market, *fred]
        if not indicators:
            raise ConnectorError("macro_unavailable")
        return MacroSnapshot(indicators=indicators, flags=macro_flags(indicators))

    async def _series(self, series_id: str) -> list[MacroIndicator]:
        connector = FredMacroConnector(self.api_key or "", [series_id], limit=13)
        connector.setup_http(self.settings)
        try:
            raw = await connector.fetch()
            records = await connector.normalize(raw)
        finally:
            await connector.close()
        return [r for r in records if isinstance(r, MacroIndicator)]
