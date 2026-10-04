"""Wire models for portfolio-mode answers (one result per question about the holdings)."""

from typing import Any, Literal

from pydantic import Field

from stop_loss.agents.models import Audit, EvidenceItem, SourceOut, Wire


class HoldingRow(Wire):
    symbol: str
    name: str
    sector: str | None = None
    quantity: float
    avg_price: float | None = None
    price: float | None = None
    change_pct: float | None = None
    value: float | None = None
    weight: float | None = None  # percent of priced portfolio value
    target: bool = True
    status: Literal["ok", "unavailable"] = "ok"


class SectorWeight(Wire):
    sector: str
    weight: float


class PortfolioSnapshot(Wire):
    total_value: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    priced: int = 0
    holdings: list[HoldingRow] = Field(default_factory=list)
    sectors: list[SectorWeight] = Field(default_factory=list)


class EventAlert(Wire):
    source: str
    event_type: str
    name: str
    alert_level: str | None = None
    country: str | None = None
    started_at: str | None = None
    severity: str | None = None
    current: bool | None = None
    url: str | None = None


class EventSection(Wire):
    summary: str | None = None
    kind: str | None = None
    region: str | None = None
    severity: str | None = None
    description: str | None = None
    alerts: list[EventAlert] = Field(default_factory=list)
    macro: list[dict[str, Any]] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    weather: list[dict[str, Any]] = Field(default_factory=list)


class ExposureRow(Wire):
    symbol: str
    name: str
    sector: str | None = None
    value: float | None = None
    weight: float | None = None
    beta_nifty: float | None = None
    beta_brent: float | None = None
    beta_inr: float | None = None
    corr_brent: float | None = None
    sentiment_score: float | None = None
    analog_n: int = 0
    analog_median_5d: float | None = None  # percent
    scenario_impact: float | None = None  # INR, analog median x value
    scenario_low: float | None = None
    scenario_high: float | None = None
    channel_impact: float | None = None  # INR, beta to Brent x analog Brent move x value


class ExposureSection(Wire):
    summary: str | None = None
    rows: list[ExposureRow] = Field(default_factory=list)
    total_impact: float | None = None
    total_low: float | None = None
    total_high: float | None = None
    method: str = (
        "Scenario = median 5-day move of each holding after the matched historical events x "
        "its current value; range from the smallest/largest analog move. Totals are a simple "
        "sum of per-holding estimates (no diversification). Shown only with >= 3 analogs."
    )


class AnalogEvent(Wire):
    id: str
    title: str
    date: str | None = None
    doc_type: str | None = None
    score: float
    returns: dict[str, dict[str, float | None]] = Field(default_factory=dict)  # percent
    brent_5d: float | None = None
    nifty_5d: float | None = None


class AnalogAggregate(Wire):
    symbol: str
    n: int = 0
    median_5d: float | None = None
    min_5d: float | None = None
    max_5d: float | None = None
    share_negative_5d: float | None = None
    median_20d: float | None = None


class AnalogsSection(Wire):
    summary: str | None = None
    query: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    events: list[AnalogEvent] = Field(default_factory=list)
    aggregates: list[AnalogAggregate] = Field(default_factory=list)
    brent: AnalogAggregate | None = None
    nifty: AnalogAggregate | None = None


class HoldingSentiment(Wire):
    symbol: str
    score: float | None = None  # (positive - negative) / scored, in [-1, 1]
    positive: int = 0
    negative: int = 0
    neutral: int = 0


class PortfolioSource(SourceOut):
    symbols: list[str] = Field(default_factory=list)


class SentimentSection(Wire):
    summary: str | None = None
    portfolio_score: float | None = None  # value-weighted over holdings with scores
    per_holding: list[HoldingSentiment] = Field(default_factory=list)
    items: list[PortfolioSource] = Field(default_factory=list)


class HoldingRisk(Wire):
    symbol: str
    risk_score: float | None = None
    band: str | None = None
    vol_1y: float | None = None  # percent
    var_95_1d: float | None = None  # percent
    max_drawdown_1y: float | None = None  # percent
    beta: float | None = None


class PortfolioRisk(Wire):
    summary: str | None = None
    risk_score: float | None = None  # value-weighted mean of per-holding scores
    risk_band: str | None = None
    per_holding: list[HoldingRisk] = Field(default_factory=list)
    trust_score: float | None = None
    trust_band: str | None = None
    trust_reasons: list[str] = Field(default_factory=list)
    nifty_hedge_notional: float | None = None  # sum(beta x value) over target holdings


class Recommendation(Wire):
    action: str
    kind: Literal["hedge", "reduce", "add", "rebalance", "monitor"] = "monitor"
    symbols: list[str] = Field(default_factory=list)
    size: str | None = None
    rationale: str
    horizon: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class AuditStep(Wire):
    agent: str
    name: str
    status: str
    summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class PortfolioResult(Wire):
    kind: Literal["portfolio"] = "portfolio"
    message_id: str
    run_id: str
    thread_id: str
    generated_at: str
    narrative_source: Literal["llm", "rules"]
    partial: bool = False
    failed_agents: list[str] = Field(default_factory=list)
    langsmith_run_id: str | None = None
    bottom_line: str
    portfolio: PortfolioSnapshot
    event: EventSection
    exposure: ExposureSection
    analogs: AnalogsSection
    sentiment: SentimentSection
    risk: PortfolioRisk
    recommendations: list[Recommendation] = Field(default_factory=list)
    disclaimer: str = "Informational analysis generated from public data. Not investment advice."
    evidence: list[EvidenceItem] = Field(default_factory=list)
    audit: Audit = Field(default_factory=Audit)
    steps: list[AuditStep] = Field(default_factory=list)
