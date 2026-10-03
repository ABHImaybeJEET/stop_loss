from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core environment & logging
    app_env: str = Field(
        default="development",
        description="Application environment (development, test, production).",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level threshold (DEBUG, INFO, WARNING, ERROR).",
    )

    # Storage
    database_path: Path = Field(
        default=Path("data/stop_loss.db"),
        description="Path to SQLite database file for local persistence.",
    )

    # Operational timeouts & intervals
    http_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        description="HTTP client request timeout in seconds.",
    )
    ingestion_poll_seconds: int = Field(
        default=300,
        gt=0,
        description="Polling interval in seconds for continuous ingestion cycles.",
    )

    # Weather provider settings (Gulf of Mexico demonstration scenario)
    weather_latitude: float = Field(
        default=27.8006,
        description="Latitude for weather observations.",
    )
    weather_longitude: float = Field(
        default=-97.3964,
        description="Longitude for weather observations.",
    )
    weather_location_name: str = Field(
        default="Corpus Christi, Texas",
        description="Human-readable location label for weather observations.",
    )

    # News provider settings
    news_query: str = Field(
        default="hurricane OR refinery OR Gulf of Mexico",
        description="Default search query for news ingestion.",
    )

    # Market provider settings
    market_tickers: list[str] | str = Field(
        default_factory=lambda: ["XLE", "XOM", "CVX", "NG=F"],
        description="List of financial ticker symbols to track.",
    )

    # Macroeconomic provider settings
    macro_series: list[str] | str = Field(
        default_factory=lambda: ["DCOILWTICO", "CPIAUCSL", "FEDFUNDS"],
        description="FRED or macroeconomic series IDs to track.",
    )
    fred_api_key: str | None = Field(
        default=None,
        description="Optional API key for Federal Reserve Economic Data (FRED).",
    )

    @field_validator("market_tickers", "macro_series", mode="after")
    @classmethod
    def parse_comma_separated_list(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
