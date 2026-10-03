"""Factory to instantiate live or stub connectors based on settings."""

from fin_terminal.config import Settings, secret_value
from fin_terminal.connectors.alphavantage import (
    AlphaVantageMarketConnector,
    AlphaVantageNewsConnector,
)
from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.connectors.fred import FredMacroConnector
from fin_terminal.connectors.openmeteo import OpenMeteoWeatherConnector
from fin_terminal.connectors.stub import StubConnector

SOURCES = ("prices", "macro", "weather", "news_tariff", "news_banktax", "news_war")


def create_connectors(settings: Settings, *, live: bool = False) -> dict[str, AsyncConnector]:
    """Create connectors for all six streams.

    If live is True and API keys/configurations are present, live connectors are used.
    Otherwise, safe StubConnectors are used for offline and test execution.
    """
    connectors: dict[str, AsyncConnector] = {}
    av_key = secret_value(settings.alpha_vantage_api_key)
    fred_key = secret_value(settings.fred_api_key)

    # 1. Market prices
    if live and av_key:
        tickers = (
            [settings.market_tickers]
            if isinstance(settings.market_tickers, str)
            else list(settings.market_tickers)
        )
        connectors["prices"] = AlphaVantageMarketConnector(
            api_key=av_key,
            tickers=tickers,
            timeout=settings.http_timeout_seconds,
        )
    else:
        connectors["prices"] = StubConnector(
            "prices",
            settings.stub_failure_mode if settings.stub_fail_source == "prices" else None,
        )

    # 2. Macroeconomic indicators
    if live and fred_key:
        series = (
            [settings.macro_series]
            if isinstance(settings.macro_series, str)
            else list(settings.macro_series)
        )
        connectors["macro"] = FredMacroConnector(
            api_key=fred_key,
            series=series,
            timeout=settings.http_timeout_seconds,
        )
    else:
        connectors["macro"] = StubConnector(
            "macro",
            settings.stub_failure_mode if settings.stub_fail_source == "macro" else None,
        )

    # 3. Weather telemetry
    if live:
        connectors["weather"] = OpenMeteoWeatherConnector(
            latitude=settings.weather_latitude,
            longitude=settings.weather_longitude,
            location_name=settings.weather_location_name,
            timeout=settings.http_timeout_seconds,
        )
    else:
        connectors["weather"] = StubConnector(
            "weather",
            settings.stub_failure_mode if settings.stub_fail_source == "weather" else None,
        )

    # 4, 5, 6. News themes (Tariff, Bank Tax, War Crisis)
    for news_source in ("news_tariff", "news_banktax", "news_war"):
        if live and av_key:
            connectors[news_source] = AlphaVantageNewsConnector(
                source=news_source,
                api_key=av_key,
                timeout=settings.http_timeout_seconds,
            )
        else:
            connectors[news_source] = StubConnector(
                news_source,
                settings.stub_failure_mode if settings.stub_fail_source == news_source else None,
            )

    return connectors
