"""Numbered evidence catalog: every figure an agent may cite, with its provenance."""

from typing import Any

from stop_loss.agents.models import AgentId, EvidenceItem
from stop_loss.analytics.models import (
    AssetProfile,
    ChartSeries,
    MacroSnapshot,
    NewsItem,
    QuantMetrics,
    WeatherOutlook,
)
from stop_loss.analytics.scoring import RiskAssessment

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}


def money(value: float, currency: str | None) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency or "", "")
    suffix = "" if symbol or not currency else f" {currency}"
    return f"{symbol}{value:,.2f}{suffix}"


def compact(value: float, currency: str | None = None) -> str:
    for size, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            text = f"{value / size:,.2f}{unit}"
            break
    else:
        text = f"{value:,.0f}"
    return f"{text} {currency}" if currency else text


def pct(fraction: float) -> float:
    return round(fraction * 100, 2)


class Catalog:
    def __init__(self) -> None:
        self.items: list[EvidenceItem] = []

    def add(
        self,
        agent: AgentId,
        label: str,
        value: float | str | None,
        display: str,
        *,
        source: str,
        unit: str | None = None,
        url: str | None = None,
        observed_at: str | None = None,
    ) -> str:
        item_id = f"E{len(self.items) + 1}"
        self.items.append(
            EvidenceItem(
                id=item_id,
                agent=agent,
                label=label,
                value=value,
                unit=unit,
                display=display,
                source=source,
                url=url,
                observed_at=observed_at,
            )
        )
        return item_id

    def percent(self, agent: AgentId, label: str, fraction: float | None, **kw: Any) -> None:
        if fraction is not None:
            self.add(
                agent,
                label,
                pct(fraction),
                f"{pct(fraction):+.2f}%" if kw.pop("signed", False) else f"{pct(fraction):.2f}%",
                unit="%",
                **kw,
            )

    def ids(self) -> set[str]:
        return {item.id for item in self.items}


def build_catalog(
    *,
    market: ChartSeries | None,
    profile: AssetProfile | None,
    quant: QuantMetrics | None,
    risk: RiskAssessment | None,
    news: list[NewsItem],
    macro: MacroSnapshot | None,
    weather: list[WeatherOutlook],
) -> Catalog:
    cat = Catalog()
    if market is not None:
        cur = market.currency
        src, url = "Yahoo Finance", market.source_url
        when = market.market_time.isoformat() if market.market_time else None
        if market.price is not None:
            cat.add(
                "market",
                "Last price",
                market.price,
                money(market.price, cur),
                unit=cur,
                source=src,
                url=url,
                observed_at=when,
            )
        if market.change_pct is not None:
            cat.add(
                "market",
                "Change today",
                round(market.change_pct, 2),
                f"{market.change_pct:+.2f}%",
                unit="%",
                source=src,
                url=url,
                observed_at=when,
            )
        for label, value in (
            ("52-week high", market.fifty_two_week_high),
            ("52-week low", market.fifty_two_week_low),
            ("Day high", market.day_high),
            ("Day low", market.day_low),
        ):
            if value is not None:
                cat.add(
                    "market",
                    label,
                    value,
                    money(value, cur),
                    unit=cur,
                    source=src,
                    url=url,
                    observed_at=when,
                )
        cat.add(
            "market",
            "Market state",
            market.market_state,
            market.market_state,
            source=src,
            url=url,
            observed_at=when,
        )
    if profile is not None:
        src, url = "Yahoo Finance profile", profile.source_url
        if profile.market_cap is not None:
            cat.add(
                "market",
                "Market cap",
                profile.market_cap,
                compact(profile.market_cap, profile.currency),
                unit=profile.currency,
                source=src,
                url=url,
            )
        if profile.trailing_pe is not None:
            cat.add(
                "market",
                "Trailing P/E",
                round(profile.trailing_pe, 2),
                f"{profile.trailing_pe:.2f}",
                source=src,
                url=url,
            )
        for label, value in (("Sector", profile.sector), ("Industry", profile.industry)):
            if value:
                cat.add("market", label, value, value, source=src, url=url)
    if quant is not None:
        src = "Computed from Yahoo Finance daily closes"
        when = quant.as_of.isoformat() if quant.as_of else None
        kw = {"source": src, "observed_at": when}
        for label, value in (
            ("1-month return", quant.return_1m),
            ("3-month return", quant.return_3m),
            ("6-month return", quant.return_6m),
            ("1-year return", quant.return_1y),
            ("5-year return", quant.return_5y),
            ("Best day (1Y)", quant.best_day),
            ("Worst day (1Y)", quant.worst_day),
            ("1Y max drawdown", quant.max_drawdown_1y),
            ("5Y max drawdown", quant.max_drawdown_5y),
            ("Current drawdown from peak", quant.current_drawdown),
        ):
            cat.percent("quant", label, value, signed=True, **kw)
        for label, value in (
            ("30-day annualized volatility", quant.vol_30d),
            ("1Y annualized volatility", quant.vol_1y),
            ("1-day 95% VaR (historical)", quant.var_95_1d),
            ("1-day 95% CVaR (historical)", quant.cvar_95_1d),
        ):
            cat.percent("quant", label, value, **kw)
        for point in quant.var_sensitivity:
            if point.confidence != 0.95:
                cat.percent("quant", f"1-day {point.confidence:.1%} VaR", point.var, **kw)
        if quant.beta_1y is not None:
            cat.add(
                "quant",
                f"1Y beta vs {quant.benchmark_symbol}",
                round(quant.beta_1y, 2),
                f"{quant.beta_1y:.2f}",
                **kw,
            )
        for c in quant.correlations:
            if c.correlation is not None:
                cat.add(
                    "quant",
                    f"1Y correlation vs {c.asset_name} ({c.symbol})",
                    round(c.correlation, 2),
                    f"{c.correlation:+.2f}",
                    **kw,
                )
        cur = market.currency if market else None
        for label, value in (("50-day average", quant.sma_50), ("200-day average", quant.sma_200)):
            if value is not None:
                cat.add("quant", label, round(value, 2), money(value, cur), unit=cur, **kw)
        if quant.trend:
            cat.add("quant", "Trend (price vs 50/200-day averages)", quant.trend, quant.trend, **kw)
    if risk is not None and risk.score is not None:
        cat.add(
            "quant",
            "Risk score (0-100)",
            risk.score,
            f"{risk.score:.1f} ({risk.band})",
            source="StopLoss risk model (ADR-T06)",
        )
    for item in news:
        label = item.sentiment or "unscored"
        detail = (
            f" ({item.sentiment_source} score {item.sentiment_score:+.3f})"
            if (item.sentiment_score is not None)
            else ""
        )
        cat.add(
            "news",
            f"Headline: {item.title}",
            label,
            f"{item.publisher}: {item.title} — sentiment {label}{detail}",
            source=item.publisher,
            url=item.url,
            observed_at=item.published_at.isoformat() if item.published_at else None,
        )
    if macro is not None:
        for ind in macro.indicators:
            if ind.latest is None:
                continue
            cat.add(
                "macro",
                ind.label,
                ind.latest,
                f"{ind.latest:,.2f} {ind.unit or ''}".strip(),
                unit=ind.unit,
                source=ind.source,
                url=ind.source_url,
                observed_at=ind.latest_date,
            )
            if ind.change_pct is not None and ind.previous_date:
                cat.add(
                    "macro",
                    f"{ind.label} change since {ind.previous_date}",
                    round(ind.change_pct, 2),
                    f"{ind.change_pct:+.2f}%",
                    unit="%",
                    source=ind.source,
                    url=ind.source_url,
                    observed_at=ind.latest_date,
                )
            if ind.yoy_pct is not None:
                cat.add(
                    "macro",
                    f"{ind.label} year-over-year",
                    round(ind.yoy_pct, 2),
                    f"{ind.yoy_pct:.2f}%",
                    unit="%",
                    source=ind.source,
                    url=ind.source_url,
                    observed_at=ind.latest_date,
                )
        for flag in macro.flags:
            cat.add(
                "macro",
                "Macro flag",
                flag,
                flag.replace("_", " "),
                source="StopLoss macro thresholds (ADR T13)",
            )
    for outlook in weather:
        gusts = [d.wind_gust_max for d in outlook.days if d.wind_gust_max is not None]
        rain = [d.precipitation_sum for d in outlook.days if d.precipitation_sum is not None]
        kw = {"source": "Open-Meteo", "url": outlook.source_url}
        if gusts:
            cat.add(
                "weather",
                f"Max 7-day wind gust, {outlook.location}",
                max(gusts),
                f"{max(gusts):g} km/h",
                unit="km/h",
                **kw,
            )
        if rain:
            cat.add(
                "weather",
                f"Max daily rainfall (7d), {outlook.location}",
                max(rain),
                f"{max(rain):g} mm",
                unit="mm",
                **kw,
            )
        for extreme in outlook.extremes:
            cat.add(
                "weather",
                f"{outlook.location} {extreme.date}",
                extreme.value,
                extreme.description,
                unit=extreme.unit,
                observed_at=extreme.date,
                **kw,
            )
    return cat
