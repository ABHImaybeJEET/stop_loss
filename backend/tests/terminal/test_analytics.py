import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from terminal_fixtures import FIXTURES, load_json, load_text

import fin_terminal.connectors  # noqa: F401  (import before resilience: package import cycle)
from fin_terminal.resilience import RateLimitedError
from fin_terminal.schemas import MacroIndicator, Theme
from stop_loss.analytics.macro import macro_flags, summarize_series
from stop_loss.analytics.models import Bar, ChartSeries, NewsItem
from stop_loss.analytics.news import (
    parse_alpha_vantage_sentiment,
    parse_google_news_rss,
    sentiment_label,
)
from stop_loss.analytics.risk import (
    benchmark_for,
    compute_quant_metrics,
    historical_var,
    max_drawdown,
    trend_label,
)
from stop_loss.analytics.scoring import assess_risk, assess_trust, risk_band
from stop_loss.analytics.themes import tag_themes
from stop_loss.analytics.weather import parse_forecast, parse_geocode
from stop_loss.analytics.yahoo import (
    SymbolNotFoundError,
    YahooFinanceClient,
    last_session,
    market_state_from_meta,
    parse_chart,
    parse_quote_summary,
    parse_search,
)


def reliance() -> ChartSeries:
    return parse_chart(load_json("yahoo_chart_reliance_5y_1d.json"), "RELIANCE.NS", "5y", "1d")


def nifty() -> ChartSeries:
    return parse_chart(load_json("yahoo_chart_nsei_5y_1d.json"), "^NSEI", "5y", "1d")


def test_parse_chart_keeps_provider_values_and_drops_null_rows() -> None:
    series = reliance()
    assert series.name == "Reliance Industries Limited"
    assert series.currency == "INR" and series.exchange == "NSE"
    assert series.price == 1167.7 and series.change_pct == pytest.approx(-1.626)
    assert series.previous_close is None  # not in multi-year meta; never derived
    assert all(bar.close is not None for bar in series.bars)
    assert series.bars == sorted(series.bars, key=lambda b: b.t)


def test_unknown_symbol_raises() -> None:
    with pytest.raises(SymbolNotFoundError):
        parse_chart(load_json("yahoo_chart_unknown.json"), "NOTAREALTICKERXYZ", "1d", "5m")


def test_closed_market_intraday_payload_is_empty_and_flagged() -> None:
    series = parse_chart(load_json("yahoo_chart_reliance_1d_5m.json"), "RELIANCE.NS", "1d", "5m")
    assert series.bars == [] and series.data_quality == "missing_fields"


def test_market_state_windows() -> None:
    meta = {
        "currentTradingPeriod": {
            "regular": {"start": 100, "end": 200},
            "pre": {"start": 50, "end": 100},
        }
    }
    at = lambda s: datetime.fromtimestamp(s, UTC)  # noqa: E731
    assert market_state_from_meta(meta, at(150)) == "open"
    assert market_state_from_meta(meta, at(60)) == "pre"
    assert market_state_from_meta(meta, at(250)) == "closed"


def test_last_session_keeps_latest_local_day() -> None:
    base = datetime(2026, 10, 1, 4, 0, tzinfo=UTC)
    bars = [
        Bar(t=base - timedelta(days=1), close=1),
        Bar(t=base, close=2),
        Bar(t=base + timedelta(hours=3), close=3),
    ]
    series = ChartSeries(
        symbol="X", range="5d", interval="5m", bars=bars, source_url="u", gmt_offset_seconds=19800
    )
    assert [b.close for b in last_session(series).bars] == [2, 3]


def test_parse_search_and_profile() -> None:
    matches, news = parse_search(load_json("yahoo_search_reliance.json"))
    assert matches[0].symbol == "RELIANCE.NS" and matches[0].exchange == "NSE"
    assert any(m.symbol == "RELIANCE.BO" for m in matches)
    assert news and all(n.url.startswith("http") for n in news)
    profile = parse_quote_summary(load_json("yahoo_quote_summary_reliance.json"), "RELIANCE.NS")
    assert profile.sector == "Energy" and profile.city == "Mumbai"
    assert profile.market_cap and profile.market_cap > 1e12


def test_quant_metrics_on_real_history() -> None:
    metrics = compute_quant_metrics(reliance(), nifty())
    assert metrics.observations > 1000
    assert 0 < metrics.vol_1y < 1
    assert metrics.max_drawdown_1y is not None and metrics.max_drawdown_1y < 0
    assert metrics.var_95_1d is not None and metrics.cvar_95_1d >= metrics.var_95_1d
    levels = [p.var for p in metrics.var_sensitivity]
    assert levels == sorted(levels)  # higher confidence never lowers VaR
    assert metrics.beta_1y is not None and metrics.benchmark_symbol == "^NSEI"
    assert len(metrics.seasonality) == 12
    assert len(metrics.drawdown_series) <= 261


def test_metrics_refuse_thin_history() -> None:
    assert historical_var([0.01] * 10, 0.95) is None
    assert max_drawdown([100.0]) is None
    assert trend_label(10, None, 9) is None
    short = ChartSeries(
        symbol="X",
        range="5d",
        interval="1d",
        source_url="u",
        bars=[Bar(t=datetime(2026, 1, d, tzinfo=UTC), close=100 + d) for d in range(1, 6)],
    )
    metrics = compute_quant_metrics(short)
    assert metrics.vol_1y is None and metrics.var_95_1d is None and metrics.return_1y is None


def test_benchmark_selection() -> None:
    assert benchmark_for("RELIANCE.NS", "EQUITY") == "^NSEI"
    assert benchmark_for("AAPL", "EQUITY") is None
    assert benchmark_for("BTC-USD", "CRYPTOCURRENCY") is None


def test_google_news_rss_strips_publisher_suffix() -> None:
    items = parse_google_news_rss(load_text("google_news_reliance.xml"))
    assert 0 < len(items) <= 12
    assert all(not i.title.endswith(f" - {i.publisher}") for i in items)
    assert all(i.sentiment is None for i in items)  # RSS carries no scores; none invented


def test_alpha_vantage_sentiment_and_rate_limit() -> None:
    payload = json.loads((FIXTURES / "alphavantage_news.json").read_text(encoding="utf-8"))
    items = parse_alpha_vantage_sentiment(payload, "SCHW")
    assert items[0].sentiment_source == "alpha_vantage" and items[0].sentiment == "positive"
    with pytest.raises(RateLimitedError):
        parse_alpha_vantage_sentiment(
            {"Information": "standard API rate limit is 25 requests per day"}, "AAPL"
        )
    assert sentiment_label(-0.2) == "negative" and sentiment_label(0.05) == "neutral"


def test_theme_tagging() -> None:
    assert tag_themes("US slaps new tariff on steel") == [Theme.TARIFF]
    assert Theme.WEATHER_EXTREME in tag_themes("Cyclone nears Gujarat refinery")
    assert tag_themes("Quarterly results in line") == []


def test_weather_forecast_and_thresholds() -> None:
    lat, lon, label = parse_geocode(load_json("openmeteo_geocode_mumbai.json"))
    assert label == "Mumbai, India"
    outlook = parse_forecast(
        load_json("openmeteo_forecast_mumbai.json"),
        location=label,
        latitude=lat,
        longitude=lon,
        reason="HQ",
    )
    assert len(outlook.days) == 7
    storm = {
        "daily": {
            "time": ["2026-10-04"],
            "wind_gusts_10m_max": [120.0],
            "precipitation_sum": [None],
            "weather_code": [95],
        }
    }
    extremes = parse_forecast(storm, location="X", latitude=0, longitude=0, reason="r").extremes
    assert {e.metric for e in extremes} == {"wind_gust_max", "weather_code"}


def test_macro_summary_skips_missing_values() -> None:
    def rec(day: int, value: float | None) -> MacroIndicator:
        return MacroIndicator(
            source="macro",
            provider="fred",
            series_id="T10Y2Y",
            value=value,
            observed_at=datetime(2026, 9, day, tzinfo=UTC),
            source_url="u",
            fetched_at=datetime.now(UTC),
            ingest_run_id="t",
        )

    view = summarize_series("T10Y2Y", [rec(30, None), rec(29, -0.1), rec(28, 0.2)])
    assert view.latest == -0.1 and view.previous == 0.2
    assert macro_flags([view]) == ["yield_curve_inverted"]


def test_scores_are_bounded_and_drop_missing_inputs() -> None:
    metrics = compute_quant_metrics(reliance(), nifty())
    risk = assess_risk(metrics, [], None, [])
    assert risk.score is not None and 0 <= risk.score <= 100
    assert risk.band == risk_band(risk.score)
    assert {c.key for c in risk.components} == {"volatility", "drawdown", "tail", "beta"}
    assert assess_risk(None, [], None, []).score is None
    news = [
        NewsItem(
            id=str(i),
            publisher=f"P{i}",
            title="t",
            url="u",
            provider="x",
            sentiment="negative",
            sentiment_source="llm",
        )
        for i in range(4)
    ]
    trust = assess_trust(
        agents_ok=5,
        agents_total=5,
        market=reliance(),
        news=news,
        quant=metrics,
        unverified_numbers=1,
    )
    assert trust.score is not None and 0 <= trust.score <= 100
    assert any("model-classified" in r for r in trust.reasons)


@pytest.mark.asyncio
async def test_yahoo_client_falls_back_to_last_session_when_closed(settings) -> None:
    # Simulate an empty 1d chart (e.g. weekend) and a valid fallback 5d chart.
    intraday = load_json("yahoo_chart_reliance_1d_5m.json")
    intraday["chart"]["result"][0]["timestamp"] = []
    intraday["chart"]["result"][0]["indicators"] = {"quote": [{}]}
    week = load_json("yahoo_chart_reliance_5y_1d.json")

    client = YahooFinanceClient(settings)
    
    def mock_payload(symbol: str, range_: str, interval: str) -> dict:
        return intraday if range_ == "1d" else week

    client._history_payload = mock_payload
    series = await client.chart("RELIANCE.NS", "1d", "5m")
    assert series.bars and series.range == "1d"
    assert len({b.t.date() for b in series.bars}) == 1
