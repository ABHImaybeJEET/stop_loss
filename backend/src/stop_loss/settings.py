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
    groq_quant_api_key: SecretStr | None = None
    groq_hedging_api_key: SecretStr | None = None
    groq_audit_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = Field(default=60, gt=0)
    api_internal_token: SecretStr | None = None
    conversation_db_path: Path = Path("data/conversations.sqlite")
    feedback_db_path: Path = Path("data/feedback.sqlite")
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
    terminal_macro_series: list[str] = Field(
        default_factory=lambda: ["DCOILWTICO", "CPIAUCSL", "FEDFUNDS", "T10Y2Y", "DGS10"]
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
