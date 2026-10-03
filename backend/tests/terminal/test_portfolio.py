import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import fin_terminal.connectors  # noqa: F401  (import before resilience: package import cycle)
from fin_terminal.connectors.errors import ConnectorError
from stop_loss.analytics.models import AssetProfile, Bar, ChartSeries
from stop_loss.api.portfolio import PortfolioData, parse_holdings, parse_symbols
from stop_loss.universe import NseUniverse


@pytest.fixture
def universe(tmp_path: Path) -> NseUniverse:
    (tmp_path / "nse_historical").mkdir()
    for symbol in ("RELIANCE.NS", "TCS.NS", "RPOWER.NS", "NOINFO.NS"):
        (tmp_path / "nse_historical" / f"{symbol}.csv").write_text("Date,Close\n")
    metadata = {
        "TCS.NS": {
            "longName": "Tata Consultancy Services Limited",
            "sector": "Technology",
            "city": "Mumbai",
            "country": "India",
            "marketCap": 1.5e13,
        },
        "RPOWER.NS": {
            "longName": "Reliance Power Limited",
            "sector": "Utilities",
            "city": "Mumbai",
            "country": "India",
            "marketCap": 1e11,
        },
    }
    (tmp_path / "company_metadata_cleaned.json").write_text(json.dumps(metadata))
    return NseUniverse(tmp_path)


def series(symbol: str, closes: dict[str, float]) -> ChartSeries:
    bars = [
        Bar(t=datetime.fromisoformat(f"{d}T04:00:00+00:00"), close=c) for d, c in closes.items()
    ]
    return ChartSeries(
        symbol=symbol,
        range="6mo",
        interval="1d",
        bars=bars,
        source_url="u",
        price=list(closes.values())[-1],
        change_pct=1.0,
        market_state="closed",
    )


class FakeYahoo:
    def __init__(self, charts: dict[str, ChartSeries], failing: set[str] = frozenset()) -> None:
        self.charts, self.failing, self.profiles = charts, failing, 0

    async def quote(self, symbol: str) -> ChartSeries:
        if symbol in self.failing:
            raise ConnectorError("yfinance_down")
        return self.charts[symbol]

    async def chart(self, symbol: str, range_: str, interval: str) -> ChartSeries:
        return await self.quote(symbol)

    async def profile(self, symbol: str) -> AssetProfile:
        self.profiles += 1
        return AssetProfile(
            symbol=symbol,
            long_name="Reliance Industries Limited",
            sector="Energy",
            city="Mumbai",
            country="India",
            source_url="u",
        )


def portfolio(universe: NseUniverse, yahoo: FakeYahoo) -> PortfolioData:
    kit = SimpleNamespace(yahoo=yahoo, model_for=lambda _: None)
    return PortfolioData(SimpleNamespace(kit=kit), universe)


def test_parsers_enforce_nse_and_merge_duplicates() -> None:
    assert parse_symbols("reliance.ns, TCS.NS,RELIANCE.NS") == ["RELIANCE.NS", "TCS.NS"]
    with pytest.raises(HTTPException):
        parse_symbols("AAPL")
    with pytest.raises(HTTPException):
        parse_symbols("^NSEI")  # indices are benchmarks, not holdings
    assert parse_holdings("tcs.ns:2,TCS.NS:3") == {"TCS.NS": 5.0}
    with pytest.raises(HTTPException):
        parse_holdings("TCS.NS:-1")


def test_universe_search_ranks_and_enriches(universe: NseUniverse, tmp_path: Path) -> None:
    assert [c.symbol for c in universe.search("tcs")] == ["TCS.NS"]
    assert [c.symbol for c in universe.search("reliance")] == ["RELIANCE.NS", "RPOWER.NS"]
    assert [c.symbol for c in universe.search("utilities")] == ["RPOWER.NS"]
    assert universe.get("RELIANCE.NS").sector is None and universe.needs_profile("RELIANCE.NS")
    merged = universe.record_profile(
        AssetProfile(
            symbol="RELIANCE.NS",
            sector="Energy",
            long_name="Reliance Industries Limited",
            city="Mumbai",
            source_url="u",
        )
    )
    assert merged.sector == "Energy" and merged.name == "Reliance Industries Limited"
    assert NseUniverse(tmp_path).get("RELIANCE.NS").city == "Mumbai"  # persisted


@pytest.mark.asyncio
async def test_quotes_isolate_failures_and_fetch_profiles_once(universe: NseUniverse) -> None:
    yahoo = FakeYahoo({"TCS.NS": series("TCS.NS", {"2026-10-01": 2075.0})}, {"RELIANCE.NS"})
    data = portfolio(universe, yahoo)
    rows = {r["symbol"]: r for r in (await data.quotes(["TCS.NS", "RELIANCE.NS"]))["quotes"]}
    assert rows["TCS.NS"]["status"] == "ok" and rows["TCS.NS"]["price"] == 2075.0
    assert rows["RELIANCE.NS"]["status"] == "unavailable"
    assert rows["RELIANCE.NS"]["sector"] == "Energy"  # profile still enriched the row
    await data.quotes(["RELIANCE.NS"])
    assert yahoo.profiles == 1


@pytest.mark.asyncio
async def test_performance_uses_common_dates_and_leaves_benchmark_gaps(universe) -> None:
    day = datetime(2026, 9, 1, tzinfo=UTC)
    dates = [(day + timedelta(days=i)).date().isoformat() for i in range(4)]
    yahoo = FakeYahoo(
        {
            "TCS.NS": series("TCS.NS", dict(zip(dates, [100, 110, 120, 130], strict=True))),
            "RPOWER.NS": series("RPOWER.NS", dict(zip(dates[1:], [10, 10, 20], strict=True))),
            "^NSEI": series("^NSEI", {dates[1]: 200, dates[3]: 220}),
        },
        {"NOINFO.NS"},
    )
    data = portfolio(universe, yahoo)
    out = await data.performance({"TCS.NS": 1, "RPOWER.NS": 2, "NOINFO.NS": 5}, "1mo")
    assert out["dates"] == dates[1:]  # first date missing for RPOWER: not filled
    assert out["value"] == [130, 140, 170]
    assert out["portfolio"][0] == 100
    assert out["nifty"][1] is None
    assert [out["nifty"][0], out["nifty"][2]] == pytest.approx([100, 110])
    assert out["excluded"] == ["NOINFO.NS"]
    with pytest.raises(HTTPException):
        await data.performance({"TCS.NS": 1}, "10y")
