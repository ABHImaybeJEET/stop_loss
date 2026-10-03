"""Transparent 0-100 risk and trust scores from observed inputs (ADR-T06 in docs/DECISIONS.md).

Every component maps one real input onto 0-100 with a fixed, documented scale. Missing
inputs drop out and the weights renormalize; nothing is filled in.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from fin_terminal.schemas import Theme
from stop_loss.analytics.models import (
    ChartSeries,
    Frozen,
    MacroSnapshot,
    NewsItem,
    QuantMetrics,
    WeatherOutlook,
)

RiskBand = Literal["Low", "Moderate", "High", "Severe"]
TrustBand = Literal["Low", "Medium", "High"]
EVENT_THEMES = {Theme.WAR_CRISIS, Theme.TARIFF, Theme.BANK_TAX, Theme.WEATHER_EXTREME}


class ScoreComponent(Frozen):
    key: str
    label: str
    value: float = Field(ge=0, le=100)
    weight: float = Field(ge=0)
    detail: str


class RiskAssessment(Frozen):
    score: float | None
    band: RiskBand | None
    components: list[ScoreComponent]


class TrustAssessment(Frozen):
    score: float | None
    band: TrustBand | None
    components: list[ScoreComponent]
    reasons: list[str]


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def risk_band(score: float) -> RiskBand:
    if score < 25:
        return "Low"
    if score < 50:
        return "Moderate"
    if score < 75:
        return "High"
    return "Severe"


def trust_band(score: float) -> TrustBand:
    return "High" if score >= 70 else "Medium" if score >= 45 else "Low"


def sentiment_counts(news: list[NewsItem]) -> dict[str, int]:
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for item in news:
        if item.sentiment:
            counts[item.sentiment] += 1
    return counts


def net_sentiment(news: list[NewsItem]) -> float | None:
    """(negative - positive) / scored, in [-1, 1]; None with fewer than 3 scored headlines."""
    counts = sentiment_counts(news)
    scored = sum(counts.values())
    if scored < 3:
        return None
    return (counts["negative"] - counts["positive"]) / scored


def _weighted(components: list[ScoreComponent]) -> float | None:
    total = sum(c.weight for c in components)
    if not total:
        return None
    return round(sum(c.value * c.weight for c in components) / total, 1)


def assess_risk(
    quant: QuantMetrics | None,
    news: list[NewsItem],
    macro: MacroSnapshot | None,
    weather: list[WeatherOutlook],
) -> RiskAssessment:
    parts: list[ScoreComponent] = []
    if quant and quant.vol_1y is not None:
        parts.append(
            ScoreComponent(
                key="volatility",
                label="Volatility",
                weight=0.25,
                value=clamp(quant.vol_1y / 0.60 * 100),
                detail=f"1Y annualized volatility {quant.vol_1y:.1%} (60% maps to 100)",
            )
        )
    if quant and quant.max_drawdown_1y is not None:
        parts.append(
            ScoreComponent(
                key="drawdown",
                label="Drawdown",
                weight=0.20,
                value=clamp(abs(quant.max_drawdown_1y) / 0.50 * 100),
                detail=f"1Y max drawdown {quant.max_drawdown_1y:.1%} (-50% maps to 100)",
            )
        )
    if quant and quant.var_95_1d is not None:
        parts.append(
            ScoreComponent(
                key="tail",
                label="Tail loss (VaR)",
                weight=0.20,
                value=clamp(quant.var_95_1d / 0.05 * 100),
                detail=f"1-day 95% historical VaR {quant.var_95_1d:.2%} (5% maps to 100)",
            )
        )
    if not parts:
        return RiskAssessment(score=None, band=None, components=[])
    if quant and quant.beta_1y is not None:
        parts.append(
            ScoreComponent(
                key="beta",
                label="Market sensitivity",
                weight=0.10,
                value=clamp(abs(quant.beta_1y) / 2 * 100),
                detail=(
                    f"1Y beta {quant.beta_1y:.2f} vs {quant.benchmark_symbol} (|2.0| maps to 100)"
                ),
            )
        )
    net = net_sentiment(news)
    if net is not None:
        counts = sentiment_counts(news)
        parts.append(
            ScoreComponent(
                key="sentiment",
                label="News sentiment",
                weight=0.15,
                value=clamp(50 + 50 * net),
                detail=(
                    f"{counts['negative']} negative / {counts['positive']} positive of "
                    f"{sum(counts.values())} scored headlines"
                ),
            )
        )
    events = _event_count(news, macro, weather)
    if events is not None:
        parts.append(
            ScoreComponent(
                key="events",
                label="Event exposure",
                weight=0.10,
                value=clamp(events[0] * 20),
                detail=events[1],
            )
        )
    score = _weighted(parts)
    return RiskAssessment(
        score=score, band=risk_band(score) if score is not None else None, components=parts
    )


def _event_count(
    news: list[NewsItem], macro: MacroSnapshot | None, weather: list[WeatherOutlook]
) -> tuple[int, str] | None:
    if not news and macro is None and not weather:
        return None
    themes = sorted({t.value for item in news for t in item.themes if t in EVENT_THEMES})
    extremes = sum(len(w.extremes) for w in weather)
    flags = macro.flags if macro else []
    count = len(themes) + min(extremes, 2) + len(flags)
    bits = []
    if themes:
        bits.append("themes " + ", ".join(themes))
    if extremes:
        bits.append(f"{extremes} weather extreme(s)")
    if flags:
        bits.append("macro " + ", ".join(flags))
    return count, ("; ".join(bits) or "no theme, weather or macro flags") + " (each signal = 20)"


def assess_trust(
    *,
    agents_ok: int,
    agents_total: int,
    market: ChartSeries | None,
    news: list[NewsItem],
    quant: QuantMetrics | None,
    unverified_numbers: int | None,
    now: datetime | None = None,
) -> TrustAssessment:
    now = now or datetime.now(UTC)
    parts: list[ScoreComponent] = []
    reasons: list[str] = []
    if agents_total:
        coverage = agents_ok / agents_total * 100
        parts.append(
            ScoreComponent(
                key="coverage",
                label="Data coverage",
                weight=1,
                value=clamp(coverage),
                detail=f"{agents_ok}/{agents_total} data agents returned usable data",
            )
        )
        reasons.append(f"{agents_ok} of {agents_total} data agents returned usable data.")
    if market is not None and market.market_time is not None:
        age_min = (now - market.market_time).total_seconds() / 60
        if market.market_state == "open":
            fresh = clamp(100 - max(0.0, age_min - 20))
            detail = f"live quote {age_min:.0f} min old"
        else:
            fresh = 90.0 if age_min <= 4 * 24 * 60 else 50.0
            detail = f"market {market.market_state}; last trade {age_min / 60:.0f} h ago"
        parts.append(
            ScoreComponent(
                key="freshness", label="Data freshness", weight=1, value=fresh, detail=detail
            )
        )
        reasons.append(f"Price data: {detail}.")
    publishers = {item.publisher for item in news}
    if news:
        parts.append(
            ScoreComponent(
                key="sources",
                label="Source depth",
                weight=1,
                value=clamp(len(publishers) * 20),
                detail=f"{len(news)} headlines from {len(publishers)} distinct publishers",
            )
        )
        reasons.append(f"{len(news)} headlines from {len(publishers)} distinct publishers.")
        sources = {item.sentiment_source for item in news if item.sentiment_source}
        if sources == {"llm"}:
            reasons.append("Headline sentiment is model-classified (no provider scores available).")
    net = net_sentiment(news)
    if net is not None and quant and quant.return_1m is not None:
        momentum = quant.return_1m
        if abs(net) < 0.1 or abs(momentum) < 0.01:
            agree, word = 70.0, "mixed"
        elif (net < 0) == (momentum > 0):
            agree, word = 100.0, "agree"
        else:
            agree, word = 40.0, "disagree"
        parts.append(
            ScoreComponent(
                key="agreement",
                label="Signal agreement",
                weight=1,
                value=agree,
                detail=f"news sentiment and 1M price momentum {word}",
            )
        )
        reasons.append(f"News sentiment and 1-month price momentum {word}.")
    if unverified_numbers is not None:
        parts.append(
            ScoreComponent(
                key="audit",
                label="Evidence audit",
                weight=1,
                value=clamp(100 - 25 * unverified_numbers),
                detail=f"{unverified_numbers} figure(s) in the narrative not found in evidence",
            )
        )
        reasons.append(
            "Every figure in the narrative matched recorded evidence."
            if unverified_numbers == 0
            else f"{unverified_numbers} narrative figure(s) could not be matched to evidence."
        )
    score = _weighted(parts)
    return TrustAssessment(
        score=score,
        band=trust_band(score) if score is not None else None,
        components=parts,
        reasons=reasons,
    )
