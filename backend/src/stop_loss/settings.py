"""Settings for the analysis terminal (API + agents), layered on the ingestion settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr

from fin_terminal.config import Settings


class TerminalSettings(Settings):
    openai_chat_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = Field(default=60, gt=0)
    api_internal_token: SecretStr | None = None
    conversation_db_path: Path = Path("data/conversations.sqlite")
    feedback_db_path: Path = Path("data/feedback.sqlite")
    run_timeout_seconds: float = Field(default=150, gt=0)
    run_retention_seconds: float = Field(default=900, gt=0)
    quote_cache_seconds: float = Field(default=5, gt=0)
    history_cache_seconds: float = Field(default=300, gt=0)
    profile_cache_seconds: float = Field(default=1800, gt=0)
    news_cache_seconds: float = Field(default=600, gt=0)
    sentiment_cache_seconds: float = Field(default=1800, gt=0)
    macro_cache_seconds: float = Field(default=21600, gt=0)
    weather_cache_seconds: float = Field(default=1800, gt=0)
    yahoo_rate_per_second: float = Field(default=6, gt=0)
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


@lru_cache
def get_terminal_settings() -> TerminalSettings:
    return TerminalSettings()
