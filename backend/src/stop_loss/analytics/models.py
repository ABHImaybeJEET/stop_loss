"""Typed market/analysis payloads. Absent provider values stay None; nothing is imputed."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from fin_terminal.schemas import Quality, Theme, utcnow

MarketState = Literal["open", "pre", "post", "closed"]
Sentiment = Literal["positive", "neutral", "negative"]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)


class AssetMatch(Frozen):
    symbol: str
    name: str
    exchange: str | None = None
    quote_type: str | None = None
    sector: str | None = None


class Bar(Frozen):
    t: AwareDatetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None


class ChartSeries(Frozen):
    symbol: str
    name: str | None = None
    currency: str | None = None
    exchange: str | None = None
    exchange_timezone: str | None = None
    gmt_offset_seconds: int = 0
    instrument_type: str | None = None
    price: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    market_time: AwareDatetime | None = None
    market_state: MarketState = "closed"
    range: str
    interval: str
    bars: list[Bar] = Field(default_factory=list)
    source_url: str
    fetched_at: AwareDatetime = Field(default_factory=utcnow)
    data_quality: Quality = "good"


class AssetProfile(Frozen):
    symbol: str
    long_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    city: str | None = None
    country: str | None = None
    website: str | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    average_volume: float | None = None
    currency: str | None = None
    quote_type: str | None = None
    source_url: str
    fetched_at: AwareDatetime = Field(default_factory=utcnow)


class NewsItem(Frozen):
    id: str
    publisher: str
    title: str
    url: str
    published_at: AwareDatetime | None = None
    observed_at: AwareDatetime | None = None
    summary: str | None = None
    image_url: str | None = None
    related_tickers: list[str] = Field(default_factory=list)
    provider: str
    sentiment: Sentiment | None = None
    sentiment_score: float | None = None
    sentiment_source: Literal["alpha_vantage", "llm"] | None = None
    themes: list[Theme] = Field(default_factory=list)


class SeasonalityPoint(Frozen):
    month: int = Field(ge=1, le=12)
    avg_return: float
    observations: int


class SeriesPoint(Frozen):
    date: datetime
    value: float


class VarPoint(Frozen):
    confidence: float
    var: float
    cvar: float | None = None


class QuantMetrics(Frozen):
    as_of: AwareDatetime | None = None
    observations: int
    periods_per_year: int
    return_1m: float | None = None
    return_3m: float | None = None
    return_6m: float | None = None
    return_1y: float | None = None
    return_5y: float | None = None
    vol_30d: float | None = None
    vol_1y: float | None = None
    var_95_1d: float | None = None
    cvar_95_1d: float | None = None
    var_sensitivity: list[VarPoint] = Field(default_factory=list)
    max_drawdown_1y: float | None = None
    max_drawdown_5y: float | None = None
    current_drawdown: float | None = None
    beta_1y: float | None = None
    benchmark_symbol: str | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    trend: Literal["uptrend", "downtrend", "sideways"] | None = None
    best_day: float | None = None
    worst_day: float | None = None
    seasonality: list[SeasonalityPoint] = Field(default_factory=list)
    drawdown_series: list[SeriesPoint] = Field(default_factory=list)
    correlations: list["CrossAssetCorrelation"] = Field(default_factory=list)


class CrossAssetCorrelation(Frozen):
    asset_name: str
    symbol: str
    correlation: float | None = None
    observations: int = 0


class MacroIndicatorView(Frozen):
    series_id: str
    label: str
    unit: str | None = None
    latest: float | None = None
    latest_date: str | None = None
    previous: float | None = None
    previous_date: str | None = None
    change: float | None = None
    change_pct: float | None = None
    yoy_pct: float | None = None
    source: str = "FRED"
    source_url: str


class MacroSnapshot(Frozen):
    indicators: list[MacroIndicatorView] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class WeatherDay(Frozen):
    date: str
    weather_code: int | None = None
    temp_max: float | None = None
    temp_min: float | None = None
    precipitation_sum: float | None = None
    wind_speed_max: float | None = None
    wind_gust_max: float | None = None


class WeatherExtreme(Frozen):
    date: str
    metric: str
    value: float
    threshold: float
    unit: str
    description: str


class WeatherOutlook(Frozen):
    location: str
    latitude: float
    longitude: float
    reason: str
    days: list[WeatherDay] = Field(default_factory=list)
    extremes: list[WeatherExtreme] = Field(default_factory=list)
    source_url: str
