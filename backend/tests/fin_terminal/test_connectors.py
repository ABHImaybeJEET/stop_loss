"""Offline unit tests for real async connectors using recorded fixtures."""

import json
from pathlib import Path

import pytest

from fin_terminal.config import Settings
from fin_terminal.connectors import create_connectors
from fin_terminal.connectors.alphavantage import (
    AlphaVantageMarketConnector,
    AlphaVantageNewsConnector,
)
from fin_terminal.connectors.fred import FredMacroConnector
from fin_terminal.connectors.news import LiveNewsConnector
from fin_terminal.connectors.openmeteo import OpenMeteoWeatherConnector
from fin_terminal.connectors.yfinance import YFinanceMarketConnector
from fin_terminal.schemas import MacroIndicator, NewsArticle, PricePoint, WeatherEvent

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def quote_fixture() -> dict:
    return json.loads((FIXTURES / "alphavantage_quote.json").read_text(encoding="utf-8"))


@pytest.fixture
def news_fixture() -> dict:
    return json.loads((FIXTURES / "alphavantage_news.json").read_text(encoding="utf-8"))


@pytest.fixture
def fred_fixture() -> dict:
    return json.loads((FIXTURES / "fred_observations.json").read_text(encoding="utf-8"))


@pytest.fixture
def weather_fixture() -> dict:
    return json.loads((FIXTURES / "openmeteo_weather.json").read_text(encoding="utf-8"))


@pytest.mark.anyio
async def test_alphavantage_market_connector_normalization(quote_fixture: dict):
    connector = AlphaVantageMarketConnector(api_key="mock_key", tickers=["XOM"])
    assert connector.source == "prices"

    raw = [quote_fixture["Global Quote"]]
    records = await connector.normalize(raw)

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, PricePoint)
    assert record.kind == "price"
    assert record.source == "prices"
    assert record.provider == "alpha_vantage"
    assert record.symbol == "XOM"
    assert record.price is not None and record.price > 0
    assert record.currency is None  # GLOBAL_QUOTE does not supply currency.
    assert record.observed_at is not None


@pytest.mark.anyio
async def test_alphavantage_news_connector_normalization(news_fixture: dict):
    connector = AlphaVantageNewsConnector("news_tariff", api_key="mock_key")
    assert connector.source == "news_tariff"

    raw = news_fixture.get("feed", [])
    assert len(raw) > 0
    records = await connector.normalize(raw)

    assert len(records) == len(raw)
    for record in records:
        assert isinstance(record, NewsArticle)
        assert record.kind == "news"
        assert record.source == "news_tariff"
        assert record.provider == "alpha_vantage_news"
        assert record.title
        assert record.published_at is not None


@pytest.mark.anyio
async def test_fred_macro_connector_normalization(fred_fixture: dict):
    connector = FredMacroConnector(api_key="mock_key", series=["DCOILWTICO"])
    assert connector.source == "macro"

    raw = [{"series_id": "DCOILWTICO", "observations": fred_fixture.get("observations", [])}]
    records = await connector.normalize(raw)

    assert len(records) == len(fred_fixture["observations"])
    for record in records:
        assert isinstance(record, MacroIndicator)
        assert record.kind == "macro"
        assert record.source == "macro"
        assert record.provider == "fred"
        assert record.series_id == "DCOILWTICO"
        assert record.unit == "USD/bbl"
        assert record.observed_at is not None


@pytest.mark.anyio
async def test_fred_zero_fabrication_on_missing_observation():
    connector = FredMacroConnector(api_key="mock_key", series=["DCOILWTICO"])
    # FRED returns "." on bank holidays
    raw = [{"series_id": "DCOILWTICO", "observations": [{"date": "2026-07-04", "value": "."}]}]
    records = await connector.normalize(raw)

    assert len(records) == 1
    assert records[0].value is None
    assert records[0].data_quality == "missing_fields"


@pytest.mark.anyio
async def test_openmeteo_weather_connector_normalization(weather_fixture: dict):
    connector = OpenMeteoWeatherConnector(location_name="Corpus Christi, Texas")
    assert connector.source == "weather"

    records = await connector.normalize([weather_fixture])
    assert len(records) == 3  # wind_speed_10m, temperature_2m, precipitation
    metrics = {r.metric for r in records}
    assert metrics == {"wind_speed_10m", "temperature_2m", "precipitation"}
    for record in records:
        assert isinstance(record, WeatherEvent)
        assert record.kind == "weather"
        assert record.source == "weather"
        assert record.provider == "open_meteo"
        assert record.location == "Corpus Christi, Texas"
        assert record.observed_at is not None


def test_create_connectors_factory(settings: Settings):
    # Default is offline stub mode
    stubs = create_connectors(settings, live=False)
    assert len(stubs) == 6
    assert all(c.__class__.__name__ == "StubConnector" for c in stubs.values())

    # Live mode with mock keys — yfinance is keyless, news uses LiveNewsConnector
    settings_with_keys = settings.model_copy(
        update={
            "fred_api_key": "mock_fred_key",
        }
    )
    live_connectors = create_connectors(settings_with_keys, live=True)
    assert isinstance(live_connectors["prices"], YFinanceMarketConnector)
    assert isinstance(live_connectors["macro"], FredMacroConnector)
    assert isinstance(live_connectors["weather"], OpenMeteoWeatherConnector)
    assert isinstance(live_connectors["news_tariff"], LiveNewsConnector)
    assert isinstance(live_connectors["news_banktax"], LiveNewsConnector)
    assert isinstance(live_connectors["news_war"], LiveNewsConnector)
