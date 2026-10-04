"""Portfolio-mode reasoning steps (per-agent Groq models). Each returns None on any failure
so the caller falls back to deterministic logic instead of inventing content."""

import json
import logging
import re
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from fin_terminal.grounding import GROUNDING_PROMPT
from stop_loss.agents.llm import RULES
from stop_loss.agents.models import EvidenceItem

logger = logging.getLogger("stop_loss.agents")

EventKind = Literal[
    "cyclone",
    "flood",
    "earthquake",
    "heatwave",
    "drought",
    "wildfire",
    "monsoon",
    "war",
    "sanctions",
    "tariff",
    "rate_change",
    "oil_shock",
    "currency",
    "earnings",
    "regulation",
    "other",
    "none",
]


class PortfolioPlan(BaseModel):
    intent: str = Field(description="One short phrase describing what the user wants.")
    horizon: str | None = Field(default=None, description="Investment horizon if stated.")
    event_kind: EventKind = Field(default="none", description="Main event the question is about.")
    event_region: str | None = Field(default=None, description="Region of the event, if any.")
    event_severity: str | None = Field(default=None, description="e.g. 'Category 4', 'M7'.")
    event_description: str | None = Field(
        default=None, description="Short search phrase for live news about the event."
    )
    target_sectors: list[str] = Field(
        default_factory=list, description="Sectors the user asks about (e.g. Energy); empty = all."
    )
    target_symbols: list[str] = Field(
        default_factory=list, description="Holding tickers the user names; empty = none named."
    )
    analog_query: str = Field(
        description="Phrase to search a database of past events/news for historical parallels."
    )


class RecommendationDraft(BaseModel):
    action: str = Field(description="Imperative, specific action (<= 14 words).")
    kind: Literal["hedge", "reduce", "add", "rebalance", "monitor"]
    symbols: list[str] = Field(default_factory=list, description="Tickers without .NS")
    size: str | None = Field(
        default=None, description="Size copied from a sizing evidence item, or null."
    )
    rationale: str = Field(description="1-2 sentences citing evidence ids like [E3].")
    horizon: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]


class PortfolioNarrative(BaseModel):
    bottom_line: str
    event_summary: str
    exposure_summary: str
    analogs_summary: str
    sentiment_summary: str
    risk_summary: str
    recommendations: list[RecommendationDraft] = Field(min_length=1, max_length=5)


KIND_WORDS: list[tuple[str, str]] = [
    (r"cyclone|hurricane|typhoon|storm", "cyclone"),
    (r"flood|deluge", "flood"),
    (r"earthquake|quake|tremor", "earthquake"),
    (r"heat ?wave", "heatwave"),
    (r"drought", "drought"),
    (r"monsoon", "monsoon"),
    (r"war|conflict|missile|attack", "war"),
    (r"sanction", "sanctions"),
    (r"tariff|duty|trade war", "tariff"),
    (r"repo|rate (hike|cut)|interest rate|rbi|fed", "rate_change"),
    (r"crude|oil (price|shock|spike)|opec", "oil_shock"),
    (r"rupee|usd/inr|currency", "currency"),
]
SECTOR_WORDS = {
    "energy": "Energy",
    "oil": "Energy",
    "refin": "Energy",
    "bank": "Financial Services",
    "financial": "Financial Services",
    "it ": "Technology",
    "tech": "Technology",
    "pharma": "Healthcare",
    "health": "Healthcare",
    "auto": "Consumer Cyclical",
    "metal": "Basic Materials",
    "steel": "Basic Materials",
    "cement": "Basic Materials",
    "fmcg": "Consumer Defensive",
    "consumer": "Consumer Defensive",
    "power": "Utilities",
    "utilit": "Utilities",
    "telecom": "Communication Services",
    "realty": "Real Estate",
    "real estate": "Real Estate",
    "industrial": "Industrials",
    "infra": "Industrials",
}


def compact_evidence(evidence: list[EvidenceItem], limit: int = 140) -> str:
    """Token-lean evidence for the free-tier context: id, label and display only."""
    rows = [
        {"id": e.id, "label": e.label[:90], "display": e.display[:160]} for e in evidence[:limit]
    ]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def heuristic_portfolio_plan(prompt: str, holdings: list[dict[str, Any]]) -> PortfolioPlan:
    low = f" {prompt.lower()} "
    kind = next((k for pattern, k in KIND_WORDS if re.search(pattern, low)), "none")
    severity = None
    if match := re.search(r"category\s*(\d)", low):
        severity = f"Category {match.group(1)}"
    region = None
    for name in (
        "gulf of mexico",
        "bay of bengal",
        "arabian sea",
        "south china sea",
        "caribbean",
        "gujarat",
        "odisha",
        "mumbai",
        "chennai",
        "kerala",
    ):
        if name in low:
            region = name.title()
            break
    sectors = sorted({s for w, s in SECTOR_WORDS.items() if w in low})
    bases = {h["symbol"].removesuffix(".NS"): h["symbol"] for h in holdings}
    named = [bases[t] for t in re.findall(r"[A-Z][A-Z0-9&-]{1,}", prompt) if t in bases]
    return PortfolioPlan(
        intent=prompt[:80],
        event_kind=kind,
        event_region=region,
        event_severity=severity,
        event_description=prompt[:120] if kind != "none" else None,
        target_sectors=sectors,
        target_symbols=named,
        analog_query=prompt[:200],
    )


async def plan_portfolio(
    model: BaseChatModel | None, prompt: str, holdings: list[dict[str, Any]], history: list[str]
) -> PortfolioPlan | None:
    if model is None:
        return None
    try:
        return await model.with_structured_output(PortfolioPlan).ainvoke(
            [
                SystemMessage(
                    "You are the Query Coordinator of a multi-agent portfolio terminal for NSE "
                    "(India) equities. Extract the event the user asks about (kind, region, "
                    "severity), which holdings or sectors they target, the horizon, a news search "
                    "phrase for the live event, and a search phrase for historical parallels. "
                    "Use tickers without the .NS suffix. Never invent holdings."
                ),
                HumanMessage(
                    json.dumps(
                        {
                            "question": prompt,
                            "holdings": [
                                {
                                    "ticker": h["symbol"].removesuffix(".NS"),
                                    "name": h.get("name"),
                                    "sector": h.get("sector"),
                                }
                                for h in holdings
                            ],
                            "recent_conversation": history[-6:],
                        },
                        ensure_ascii=False,
                    )
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("plan_portfolio failed: %s", type(exc).__name__)
        return None


async def write_portfolio_narrative(
    model: BaseChatModel | None,
    *,
    prompt: str,
    plan: dict[str, Any],
    history: list[str],
    evidence: list[EvidenceItem],
) -> PortfolioNarrative | None:
    if model is None:
        return None
    try:
        return await model.with_structured_output(PortfolioNarrative).ainvoke(
            [
                SystemMessage(
                    "You are the Hedging Strategy Agent of StopLoss, writing an evidence-backed "
                    "answer about the user's NSE portfolio.\n"
                    f"{GROUNDING_PROMPT}\n{RULES}\n"
                    "- Write tickers without the .NS suffix (RELIANCE, not RELIANCE.NS).\n"
                    "- bottom_line: 2-4 sentences answering the question directly: the event, "
                    "which holdings are exposed and through which channel (sector, crude/Brent, "
                    "USD/INR, sentiment), the historical analog evidence (median move, n), and the top "
                    "recommendation.\n"
                    "- The bottom_line MUST cite: the live-event status (a live alert, or that no "
                "live alert matches the region), the portfolio analog-based scenario with its "
                "range, the most exposed holding's median 5-day move with n, and the top action. "
                "Never a single generic sentence.\n"
                "- Recommendations must follow the evidence direction: hedge or reduce only "
                "where a holding's analog median is negative, it fell in >= 50% of parallels, "
                "or its risk band is High/Severe; where analogs are positive, prefer hold or "
                "monitor and say why. Use the Brent and USD/INR betas to explain channels.\n"
                "- Forecast-style statements must come from analog aggregates or scenario "
                    "items and must state n; if n < 3 say historical parallels are insufficient.\n"
                    "- Live event facts (alert level, severity) only from live alert items.\n"
                    "- event/exposure/analogs/sentiment/risk summaries: 2-3 sentences each.\n"
                    "- recommendations: 2-5 portfolio actions (hedge, reduce, add, rebalance, "
                    "monitor) naming the affected tickers; `size` must be copied from a sizing "
                    "evidence item (position value, protective put notional, NIFTY hedge notional) "
                    "or null. confidence reflects analog n, dispersion and data coverage."
                ),
                HumanMessage(
                    json.dumps(
                        {"question": prompt, "plan": plan, "recent_conversation": history[-6:]},
                        ensure_ascii=False,
                    )
                    + "\nEVIDENCE:\n"
                    + compact_evidence(evidence)
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("write_portfolio_narrative failed: %s", type(exc).__name__)
        return None
