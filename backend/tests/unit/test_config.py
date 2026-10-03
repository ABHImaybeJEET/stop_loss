import os
from pathlib import Path
from unittest import mock

from stop_loss.config import Settings


class TestConfig:
    """Unit tests for configuration management."""

    def test_default_settings(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.app_env == "development"
            assert settings.log_level == "INFO"
            assert settings.database_path == Path("data/stop_loss.db")
            assert settings.http_timeout_seconds == 15.0
            assert settings.ingestion_poll_seconds == 300
            assert settings.weather_latitude == 27.8006
            assert settings.weather_longitude == -97.3964
            assert settings.weather_location_name == "Corpus Christi, Texas"
            assert "XLE" in settings.market_tickers
            assert "DCOILWTICO" in settings.macro_series
            assert settings.fred_api_key is None
            assert settings.vector_backend == "weaviate"
            assert settings.embedding_backend == "local"
            assert settings.langsmith_tracing is False
            assert settings.alpha_vantage_api_key is None
            assert settings.enable_polygon is False

    def test_env_var_overrides(self) -> None:
        custom_env = {
            "APP_ENV": "production",
            "LOG_LEVEL": "WARNING",
            "DATABASE_PATH": "/custom/path.db",
            "HTTP_TIMEOUT_SECONDS": "30.5",
            "INGESTION_POLL_SECONDS": "600",
            "WEATHER_LATITUDE": "29.7604",
            "WEATHER_LONGITUDE": "-95.3698",
            "WEATHER_LOCATION_NAME": "Houston, Texas",
            "NEWS_QUERY": "oil spill OR pipeline leak",
            "MARKET_TICKERS": "SPY,QQQ,AAPL",
            "MACRO_SERIES": "GDP,UNRATE",
            "FRED_API_KEY": "test-fred-key-12345",
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_API_KEY": "lsv2_test_key",
            "LANGSMITH_PROJECT": "custom-ps5-project",
            "VECTOR_BACKEND": "pinecone",
            "PINECONE_API_KEY": "pc-key-123",
            "EMBEDDING_BACKEND": "openai",
            "OPENAI_API_KEY": "sk-openai-key",
            "ALPHA_VANTAGE_API_KEY": "av-test-key",
            "ENABLE_POLYGON": "true",
            "POLYGON_API_KEY": "poly-key-123",
        }
        with mock.patch.dict(os.environ, custom_env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.app_env == "production"
            assert settings.log_level == "WARNING"
            assert settings.database_path == Path("/custom/path.db")
            assert settings.http_timeout_seconds == 30.5
            assert settings.ingestion_poll_seconds == 600
            assert settings.weather_latitude == 29.7604
            assert settings.weather_longitude == -95.3698
            assert settings.weather_location_name == "Houston, Texas"
            assert settings.news_query == "oil spill OR pipeline leak"
            assert settings.market_tickers == ["SPY", "QQQ", "AAPL"]
            assert settings.macro_series == ["GDP", "UNRATE"]
            assert settings.fred_api_key == "test-fred-key-12345"
            assert settings.langsmith_tracing is True
            assert settings.langsmith_api_key == "lsv2_test_key"
            assert settings.langsmith_project == "custom-ps5-project"
            assert settings.vector_backend == "pinecone"
            assert settings.pinecone_api_key == "pc-key-123"
            assert settings.embedding_backend == "openai"
            assert settings.openai_api_key == "sk-openai-key"
            assert settings.alpha_vantage_api_key == "av-test-key"
            assert settings.enable_polygon is True
            assert settings.polygon_api_key == "poly-key-123"

    def test_comma_separated_parsing_empty_string(self) -> None:
        custom_env = {
            "MARKET_TICKERS": "",
            "MACRO_SERIES": "   ",
        }
        with mock.patch.dict(os.environ, custom_env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.market_tickers == []
            assert settings.macro_series == []
