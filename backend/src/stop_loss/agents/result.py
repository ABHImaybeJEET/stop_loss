"""Builders that turn agent outputs into the wire sections (used for progressive + final)."""

from stop_loss.agents.evidence import pct
from stop_loss.agents.models import (
    Breakdown,
    Fact,
    Historical,
    Metric,
    Risk,
    Snapshot,
    SourceOut,
    Sources,
)
from stop_loss.analytics.models import (
    AssetProfile,
    ChartSeries,
    MacroSnapshot,
    NewsItem,
    QuantMetrics,
    WeatherOutlook,
)
from stop_loss.analytics.scoring import RiskAssessment, TrustAssessment, sentiment_counts


def snapshot_section(
    market: ChartSeries, profile: AssetProfile | None, summary: str | None = None
) -> Snapshot:
    facts: list[Fact] = []

    def add(label: str, value: float | str | None, kind: str, unit: str | None = None) -> None:
        if value is not None and value != "":
            facts.append(Fact(label=label, value=value, kind=kind, unit=unit))

    cur = market.currency
    add("Exchange", market.exchange, "text")
    if profile:
        add("Sector", profile.sector, "text")
        add("Industry", profile.industry, "text")
        add("Market cap", profile.market_cap, "compact", cur)
        add("P/E (TTM)", round(profile.trailing_pe, 2) if profile.trailing_pe else None, "number")
    if market.fifty_two_week_low is not None and market.fifty_two_week_high is not None:
        add("52W low", market.fifty_two_week_low, "currency", cur)
        add("52W high", market.fifty_two_week_high, "currency", cur)
    add("Day low", market.day_low, "currency", cur)
    add("Day high", market.day_high, "currency", cur)
    add("Volume", market.volume, "compact")
    if profile:
        add("Avg volume", profile.average_volume, "compact")
        if profile.dividend_yield is not None:
            add("Dividend yield", pct(profile.dividend_yield), "percent")
    return Snapshot(
        summary=summary,
        price=market.price,
        change_pct=market.change_pct,
        previous_close=market.previous_close,
        currency=cur,
        market_state=market.market_state,
        as_of=market.market_time.isoformat() if market.market_time else None,
        facts=facts,
    )


def sources_section(items: list[NewsItem], summary: str | None = None) -> Sources:
    return Sources(
        summary=summary,
        items=[
            SourceOut(
                publisher=i.publisher,
                title=i.title,
                url=i.url,
                published_at=i.published_at.isoformat() if i.published_at else None,
                sentiment=i.sentiment,
                sentiment_source=i.sentiment_source,
                themes=[t.value for t in i.themes],
            )
            for i in items
        ],
    )


def historical_section(quant: QuantMetrics | None, summary: str | None = None) -> Historical:
    if quant is None:
        return Historical(summary=summary)
    metrics: list[Metric] = []
    for key, label, value in (
        ("return_1m", "1M return", quant.return_1m),
        ("return_6m", "6M return", quant.return_6m),
        ("return_1y", "1Y return", quant.return_1y),
        ("vol_1y", "Volatility (1Y, ann.)", quant.vol_1y),
        ("max_drawdown_1y", "Max drawdown (1Y)", quant.max_drawdown_1y),
        ("current_drawdown", "Off peak", quant.current_drawdown),
        ("var_95_1d", "VaR 95% (1D)", quant.var_95_1d),
    ):
        if value is not None:
            metrics.append(Metric(key=key, label=label, value=pct(value), kind="percent"))
    if quant.beta_1y is not None:
        metrics.append(
            Metric(
                key="beta_1y",
                label=f"Beta vs {quant.benchmark_symbol}",
                value=round(quant.beta_1y, 2),
                kind="number",
            )
        )
    if quant.trend:
        metrics.append(Metric(key="trend", label="Trend", value=quant.trend, kind="text"))
    return Historical(
        summary=summary,
        metrics=metrics,
        seasonality=[
            {"month": s.month, "avg_return": pct(s.avg_return), "observations": s.observations}
            for s in quant.seasonality
        ],
    )


def risk_section(
    quant: QuantMetrics | None,
    risk: RiskAssessment | None,
    news: list[NewsItem],
    macro: MacroSnapshot | None,
    weather: list[WeatherOutlook],
    trust: TrustAssessment | None = None,
) -> Risk:
    counts = sentiment_counts(news)
    return Risk(
        risk_score=risk.score if risk else None,
        risk_band=risk.band if risk else None,
        trust_score=trust.score if trust else None,
        trust_band=trust.band if trust else None,
        trust_reasons=trust.reasons if trust else [],
        breakdown=[
            Breakdown(label=c.label, value=round(c.value, 1), detail=c.detail)
            for c in (risk.components if risk else [])
        ],
        trust_breakdown=[
            Breakdown(label=c.label, value=round(c.value, 1), detail=c.detail)
            for c in (trust.components if trust else [])
        ],
        var_sensitivity=[
            {
                "confidence": round(p.confidence * 100, 1),
                "var": pct(p.var),
                "cvar": pct(p.cvar) if p.cvar is not None else None,
            }
            for p in (quant.var_sensitivity if quant else [])
        ],
        drawdown=[
            {"date": p.date.date().isoformat(), "value": pct(p.value)}
            for p in (quant.drawdown_series if quant else [])
        ],
        sentiment_distribution=counts if sum(counts.values()) else None,
        macro=[
            {
                "label": i.label,
                "value": i.latest,
                "unit": i.unit,
                "date": i.latest_date,
                "change": i.change,
            }
            for i in (macro.indicators if macro else [])
        ],
        weather=[
            {
                "location": w.location,
                "date": e.date,
                "description": e.description,
                "value": e.value,
                "unit": e.unit,
            }
            for w in weather
            for e in w.extremes
        ],
    )
