"""Wire models for the analysis run: requests, stream events, and the final result."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from stop_loss.analytics.models import MarketState, Sentiment

AgentStatus = Literal["queued", "running", "done", "error"]
AgentId = Literal["coordinator", "market", "news", "macro", "weather", "quant", "hedging", "audit"]

AGENTS: list[tuple[AgentId, str, str]] = [
    ("coordinator", "Query Coordinator", "Parses the request and plans the run"),
    ("market", "Market Data Agent", "Live quote, profile and price history"),
    ("news", "News Sentiment Agent", "Headlines, sentiment and theme tags"),
    ("macro", "Macro Analysis Agent", "Rates, inflation, oil and the yield curve"),
    ("weather", "Weather Impact Agent", "Facility weather extremes"),
    ("quant", "Quantitative Risk Agent", "Volatility, VaR, drawdown, beta, scores"),
    ("hedging", "Hedging Strategy Agent", "Evidence-grounded narrative and actions"),
    ("audit", "Evidence & Audit Agent", "Verifies figures and scores trust"),
]
DATA_AGENTS: tuple[AgentId, ...] = ("market", "news", "macro", "weather", "quant")


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetRef(Wire):
    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9.\-^=]+$")
    name: str = Field(min_length=1, max_length=200)
    exchange: str | None = Field(default=None, max_length=80)


class HistoryTurn(Wire):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(Wire):
    thread_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    prompt: str = Field(min_length=1, max_length=4000)
    asset: AssetRef


class EvidenceItem(Wire):
    id: str
    agent: AgentId
    label: str
    value: float | str | None
    unit: str | None = None
    display: str
    source: str
    url: str | None = None
    observed_at: str | None = None


class Fact(Wire):
    label: str
    value: float | str
    kind: Literal["currency", "percent", "number", "compact", "text"]
    unit: str | None = None


class Snapshot(Wire):
    summary: str | None = None
    price: float | None = None
    change_pct: float | None = None
    previous_close: float | None = None
    currency: str | None = None
    market_state: MarketState | None = None
    as_of: str | None = None
    facts: list[Fact] = Field(default_factory=list)


class SourceOut(Wire):
    publisher: str
    title: str
    url: str
    published_at: str | None = None
    sentiment: Sentiment | None = None
    sentiment_source: Literal["alpha_vantage", "llm"] | None = None
    themes: list[str] = Field(default_factory=list)


class Sources(Wire):
    summary: str | None = None
    items: list[SourceOut] = Field(default_factory=list)


class Metric(Wire):
    key: str
    label: str
    value: float | str
    kind: Literal["currency", "percent", "number", "text"]


class Historical(Wire):
    summary: str | None = None
    metrics: list[Metric] = Field(default_factory=list)
    seasonality: list[dict[str, float | int]] = Field(default_factory=list)


class SuggestionItem(Wire):
    action: str
    rationale: str
    horizon: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class Suggestions(Wire):
    items: list[SuggestionItem] = Field(default_factory=list)
    disclaimer: str = "Informational analysis generated from public data. Not investment advice."


class Breakdown(Wire):
    label: str
    value: float
    detail: str


class Risk(Wire):
    risk_score: float | None = None
    risk_band: str | None = None
    trust_score: float | None = None
    trust_band: str | None = None
    trust_reasons: list[str] = Field(default_factory=list)
    breakdown: list[Breakdown] = Field(default_factory=list)
    trust_breakdown: list[Breakdown] = Field(default_factory=list)
    var_sensitivity: list[dict[str, float | None]] = Field(default_factory=list)
    drawdown: list[dict[str, str | float]] = Field(default_factory=list)
    sentiment_distribution: dict[str, int] | None = None
    macro: list[dict[str, str | float | None]] = Field(default_factory=list)
    weather: list[dict[str, str | float]] = Field(default_factory=list)


class Audit(Wire):
    checked_numbers: int = 0
    unverified_numbers: list[str] = Field(default_factory=list)


class AnalysisResult(Wire):
    message_id: str
    run_id: str
    thread_id: str
    generated_at: str
    narrative_source: Literal["llm", "rules"]
    partial: bool = False
    failed_agents: list[str] = Field(default_factory=list)
    langsmith_run_id: str | None = None
    asset: AssetRef
    snapshot: Snapshot
    sources: Sources
    historical: Historical
    suggestions: Suggestions
    risk: Risk
    evidence: list[EvidenceItem] = Field(default_factory=list)
    audit: Audit = Field(default_factory=Audit)


class TextReply(Wire):
    message_id: str
    run_id: str
    thread_id: str
    generated_at: str
    narrative_source: Literal["llm", "rules"]
    content: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    audit: Audit = Field(default_factory=Audit)
    langsmith_run_id: str | None = None
