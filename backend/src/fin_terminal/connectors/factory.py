"""Factory to instantiate live or stub connectors based on settings."""

from fin_terminal.config import Settings, secret_value
from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.connectors.fred import FredMacroConnector
from fin_terminal.connectors.http import HTTPConnector
from fin_terminal.connectors.news import LiveNewsConnector
from fin_terminal.connectors.openmeteo import OpenMeteoWeatherConnector
from fin_terminal.connectors.stub import StubConnector
from fin_terminal.connectors.unavailable import UnavailableConnector
from fin_terminal.connectors.yfinance import YFinanceMarketConnector
from fin_terminal.resilience import TokenBucket
from stop_loss.analytics.news import NewsClient

SOURCES = ("prices", "macro", "weather", "news_tariff", "news_banktax", "news_war")


def create_connectors(settings: Settings, *, live: bool = False) -> dict[str, AsyncConnector]:
    """Create connectors for all six streams.

    If live is True and API keys/configurations are present, live connectors are used.
    Otherwise, safe StubConnectors are used for offline and test execution.
    """
    connectors: dict[str, AsyncConnector] = {}
    fred_key = secret_value(settings.fred_api_key)

    # yfinance is keyless. Preserve explicit offline stubs for smoke/tests.
    if live:
        connectors["prices"] = YFinanceMarketConnector(settings)
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

    # Share news caches and provider rate limits across all three theme queries.
    news_client = NewsClient(settings) if live else None
    for news_source in ("news_tariff", "news_banktax", "news_war"):
        if news_client is not None:
            connectors[news_source] = LiveNewsConnector(
                news_source,
                news_client,
                owns_client=news_source == "news_tariff",
            )
        else:
            connectors[news_source] = StubConnector(
                news_source,
                settings.stub_failure_mode if settings.stub_fail_source == news_source else None,
            )

    if live:
        buckets: dict[str, TokenBucket] = {}
        for source, connector in connectors.items():
            if isinstance(connector, StubConnector):
                connectors[source] = UnavailableConnector(source)
            elif isinstance(connector, HTTPConnector):
                policy = settings.connector_policy(connector.provider)
                bucket = buckets.setdefault(
                    connector.provider, TokenBucket(policy.rate_per_second, policy.burst)
                )
                connector.setup_http(settings, bucket)
    return connectors


class ConnectorRegistry:
    """Explicit ownership of connector resources and safe health reporting."""

    def __init__(self, connectors: dict[str, AsyncConnector]) -> None:
        self.connectors = connectors

    async def health(self) -> dict[str, dict]:
        import asyncio

        from fin_terminal.schemas import StreamStatus

        async def check(name: str, connector: AsyncConnector) -> tuple[str, dict]:
            try:
                async with asyncio.timeout(5):
                    status = await connector.health_check()
            except Exception as exc:
                status = StreamStatus(source=name, status="failed", message=type(exc).__name__)
            return name, status.model_dump(mode="json")

        return dict(await asyncio.gather(*(check(n, c) for n, c in self.connectors.items())))

    async def close(self) -> None:
        import asyncio

        results = await asyncio.gather(
            *(c.close() for c in self.connectors.values()), return_exceptions=True
        )
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            raise ExceptionGroup("connector shutdown failed", errors)
