"""Deterministic routing and narrative used when no LLM is configured (or it fails).

Text is assembled only from catalog entries, so every figure carries an evidence id.
"""

import calendar
import re
from typing import Any

from stop_loss.agents.evidence import Catalog
from stop_loss.agents.llm import NarrativeDraft, QueryPlan, SuggestionDraft
from stop_loss.analytics.models import NewsItem, QuantMetrics, WeatherOutlook
from stop_loss.analytics.scoring import RiskAssessment, sentiment_counts

HORIZON = re.compile(r"\b(\d{1,2})\s*(day|week|month|year)s?\b", re.I)


def heuristic_plan(prompt: str) -> QueryPlan:
    horizon = None
    if match := HORIZON.search(prompt):
        horizon = f"{match.group(1)} {match.group(2).lower()}s"
    elif re.search(r"short[- ]term", prompt, re.I):
        horizon = "short term"
    elif re.search(r"long[- ]term", prompt, re.I):
        horizon = "long term"
    position = "unknown"
    if re.search(r"\b(short(ed|ing)?\s+(position|the stock)|i am short)\b", prompt, re.I):
        position = "short"
    elif re.search(r"\b(hold|holding|own|bought|long|my position|portfolio)\b", prompt, re.I):
        position = "long"
    return QueryPlan(mode="analysis", intent=prompt[:80], horizon=horizon, position=position)


class Refs:
    def __init__(self, catalog: Catalog) -> None:
        self.by_label = {item.label: item for item in catalog.items}

    def __call__(self, label: str) -> str | None:
        item = self.by_label.get(label)
        return f"{item.display} [{item.id}]" if item else None

    def id(self, label: str) -> str | None:
        item = self.by_label.get(label)
        return item.id if item else None


def _join(parts: list[str | None]) -> str:
    return " ".join(p for p in parts if p)


def rules_narrative(
    *,
    asset: dict[str, Any],
    plan: dict[str, Any],
    catalog: Catalog,
    quant: QuantMetrics | None,
    risk: RiskAssessment | None,
    news: list[NewsItem],
    weather: list[WeatherOutlook],
) -> NarrativeDraft:
    ref = Refs(catalog)
    name = f"{asset['name']} ({asset['symbol']})"
    price, change = ref("Last price"), ref("Change today")
    low, high, sector = ref("52-week low"), ref("52-week high"), ref("Sector")
    snapshot = _join(
        [
            f"{name} last traded at {price}" + (f", {change} on the session." if change else ".")
            if price
            else f"No live quote is available for {name}.",
            f"52-week range: {low} to {high}." if low and high else None,
            f"Sector: {sector}." if sector else None,
        ]
    )

    counts = sentiment_counts(news)
    scored = sum(counts.values())
    publishers = len({n.publisher for n in news})
    themes = sorted({t.value for n in news for t in n.themes})
    extremes = sum(len(w.extremes) for w in weather)
    macro_bits = [
        f"{label} {value}"
        for label in ("USD/INR", "Brent crude", "India VIX")
        if (value := ref(label))
    ]
    sources = _join(
        [
            f"{len(news)} recent headlines from {publishers} publishers"
            + (
                f": {counts['positive']} positive, {counts['negative']} negative, "
                f"{counts['neutral']} neutral."
                if scored
                else " (no sentiment scores available)."
            )
            if news
            else "No recent headlines were found for this asset.",
            f"Themes flagged: {', '.join(themes)}." if themes else None,
            "Macro backdrop: " + "; ".join(macro_bits) + "." if macro_bits else None,
            f"{extremes} weather extreme(s) forecast near tracked facilities."
            if extremes
            else ("No weather extremes in the 7-day forecast." if weather else None),
        ]
    )

    best_month = None
    if quant and quant.seasonality:
        best = max(quant.seasonality, key=lambda s: s.avg_return)
        best_month = calendar.month_name[best.month]
    trend = ref("Trend (price vs 50/200-day averages)")
    historical = (
        _join(
            [
                f"Trend: {trend}." if trend else None,
                f"1-year return {ref('1-year return')}"
                + (
                    f" with a 1Y max drawdown of {ref('1Y max drawdown')}."
                    if ref("1Y max drawdown")
                    else "."
                )
                if ref("1-year return")
                else None,
                f"Annualized volatility {ref('1Y annualized volatility')}; 1-day 95% VaR "
                f"{ref('1-day 95% VaR (historical)')}."
                if ref("1Y annualized volatility") and ref("1-day 95% VaR (historical)")
                else None,
                f"Historically strongest calendar month: {best_month}." if best_month else None,
            ]
        )
        or "Not enough price history to compute historical risk metrics."
    )

    suggestions = _rules_suggestions(ref, plan, quant, risk, news, weather)
    return NarrativeDraft(
        executive_answer="Info not known. (Language model disabled; answering deterministically.)",
        snapshot_summary=snapshot,
        sources_summary=sources,
        historical_summary=historical,
        suggestions=suggestions,
    )


def _rules_suggestions(
    ref: Refs,
    plan: dict[str, Any],
    quant: QuantMetrics | None,
    risk: RiskAssessment | None,
    news: list[NewsItem],
    weather: list[WeatherOutlook],
) -> list[SuggestionDraft]:
    horizon = plan.get("horizon")
    out: list[SuggestionDraft] = []

    def add(action: str, rationale: str, labels: list[str], confidence: float) -> None:
        ids = [i for label in labels if (i := ref.id(label))]
        out.append(
            SuggestionDraft(
                action=action,
                rationale=rationale,
                horizon=horizon,
                confidence=confidence,
                evidence_ids=ids,
            )
        )

    band = risk.band if risk else None
    if band in ("High", "Severe") or (quant and quant.trend == "downtrend"):
        add(
            "Protect downside with a protective put or collar",
            f"Risk is {band or 'elevated'} with trend {quant.trend if quant else 'unknown'}; "
            f"1Y max drawdown {ref('1Y max drawdown') or 'n/a'} and 1-day 95% VaR "
            f"{ref('1-day 95% VaR (historical)') or 'n/a'}.",
            ["1Y max drawdown", "1-day 95% VaR (historical)", "Risk score (0-100)"],
            0.6,
        )
    if ref("1-day 95% VaR (historical)"):
        add(
            "Size positions and stops to the VaR band",
            f"A typical bad day (95% VaR) costs {ref('1-day 95% VaR (historical)')}; "
            f"tail days average {ref('1-day 95% CVaR (historical)') or 'n/a'}.",
            ["1-day 95% VaR (historical)", "1-day 95% CVaR (historical)"],
            0.55,
        )
    if quant and quant.beta_1y is not None and quant.beta_1y >= 1.2:
        label = f"1Y beta vs {quant.benchmark_symbol}"
        add(
            f"Consider an index hedge on {quant.benchmark_symbol}",
            f"High market sensitivity: beta {ref(label)}.",
            [label],
            0.5,
        )
    counts = sentiment_counts(news)
    if counts["negative"] > counts["positive"] and counts["negative"] >= 2:
        add(
            "Wait for news flow to stabilize before adding",
            f"{counts['negative']} of {sum(counts.values())} scored headlines are negative.",
            [],
            0.45,
        )
    if any(w.extremes for w in weather):
        locations = ", ".join(w.location for w in weather if w.extremes)
        add(
            f"Monitor weather disruption risk near {locations}",
            "The 7-day forecast crosses extreme-weather thresholds near tracked facilities.",
            [],
            0.45,
        )
    if not out or (band in ("Low", "Moderate") and quant and quant.trend == "uptrend"):
        add(
            "Hold and review on a fixed schedule",
            f"Trend {ref('Trend (price vs 50/200-day averages)') or 'n/a'} with risk band "
            f"{band or 'n/a'}.",
            ["Trend (price vs 50/200-day averages)"],
            0.5,
        )
    return out[:4]
