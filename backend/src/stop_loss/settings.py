"""Settings for the analysis terminal (API + agents), layered on the ingestion settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator

from fin_terminal.config import Settings
from stop_loss.symbols import nse_symbol


class TerminalSettings(Settings):
    llm_provider: Literal["groq", "openai"] = "groq"
    groq_chat_model: str = "openai/gpt-oss-20b"
    groq_coordinator_api_key: SecretStr | None = None
    groq_market_api_key: SecretStr | None = None
    groq_news_api_key: SecretStr | None = None
    groq_macro_api_key: SecretStr | None = None
    groq_weather_api_key: SecretStr | None = None
    groq_impact_api_key: SecretStr | None = None
    groq_analogs_api_key: SecretStr | None = None
    groq_quant_api_key: SecretStr | None = None
    groq_hedging_api_key: SecretStr | None = None
    groq_audit_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = Field(default=60, gt=0)
    api_internal_token: SecretStr | None = None
    conversation_db_path: Path = Path("data/conversations.sqlite")
    feedback_db_path: Path = Path("data/feedback.sqlite")
    runs_db_path: Path = Path("data/runs.sqlite")
    # Live ingestion (stop-loss-vectors live): per-source poll intervals and health.
    pinecone_live_namespace: str = "live"
    live_news_seconds: float = Field(default=120, gt=0)
    live_gdacs_seconds: float = Field(default=300, gt=0)
    live_usgs_seconds: float = Field(default=300, gt=0)
    live_weather_seconds: float = Field(default=1800, gt=0)
    live_backoff_max_seconds: float = Field(default=900, gt=0)
    live_down_after_failures: int = Field(default=3, ge=1)
    # Items per embed+upsert call. 1 = per-item latency (the streaming invariant); larger
    # batches raise throughput but every item then waits for its whole batch.
    live_microbatch: int = Field(default=1, ge=1, le=100)
    live_news_queries: list[str] = Field(
        default_factory=lambda: [
            "India tariff OR export controls OR trade war",
            "RBI OR bank levy OR windfall tax India banks",
            "war OR sanctions OR Strait of Hormuz oil supply",
            "cyclone OR flood OR heatwave India",
        ]
    )
    source_health_db_path: Path = Path("data/source_health.sqlite")
    latency_report_path: Path = Path("../docs/latency_report.md")
    # Bulk datasets (repo-level data/processed) and the backfill checkpoint file.
    datasets_dir: Path = Path("../data/processed")
    backfill_progress_path: Path = Path("data/backfill_progress.sqlite")
    india_news_min_year: int = Field(default=2015, ge=1990)
    india_news_categories: list[str] = Field(default_factory=lambda: ["business"])
    run_timeout_seconds: float = Field(default=150, gt=0)
    run_retention_seconds: float = Field(default=900, gt=0)
    quote_cache_seconds: float = Field(default=5, gt=0)
    history_cache_seconds: float = Field(default=300, gt=0)
    profile_cache_seconds: float = Field(default=1800, gt=0)
    news_cache_seconds: float = Field(default=600, gt=0)
    sentiment_cache_seconds: float = Field(default=1800, gt=0)
    macro_cache_seconds: float = Field(default=21600, gt=0)
    weather_cache_seconds: float = Field(default=1800, gt=0)
    yahoo_rate_per_second: float = Field(default=2, gt=0)
    # FRED: India CPI (monthly, published with a lag) and the US 10Y as the global rate.
    terminal_macro_series: list[str] = Field(default_factory=lambda: ["INDCPIALLMINMEI", "DGS10"])
    # yfinance market series for India: USD/INR, Brent crude, India VIX, NIFTY Bank.
    terminal_market_macro: list[str] = Field(
        default_factory=lambda: ["INR=X", "BZ=F", "^INDIAVIX", "^NSEBANK", "CL=F", "NG=F"]
    )
    feed_indian_tickers: list[str] = Field(
        default_factory=lambda: [
            "RELIANCE.NS",
            "TCS.NS",
            "HDFCBANK.NS",
            "INFY.NS",
            "ICICIBANK.NS",
            "SBIN.NS",
            "BHARTIARTL.NS",
            "ITC.NS",
            "LT.NS",
            "HINDUNILVR.NS",
        ]
    )

    @field_validator("feed_indian_tickers")
    @classmethod
    def only_nse_feed(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(nse_symbol(value) for value in values))


@lru_cache
def get_terminal_settings() -> TerminalSettings:
    return TerminalSettings()


# Reloaded model config
