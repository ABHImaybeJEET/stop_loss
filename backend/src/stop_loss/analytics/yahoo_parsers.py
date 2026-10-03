"""Yahoo Finance public JSON endpoints (the same ones yfinance wraps), without pandas.

Parsers are pure functions over recorded payloads so they are testable offline.
"""

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from fin_terminal.connectors.errors import ConnectorError
from stop_loss.analytics.models import (
    AssetMatch,
    AssetProfile,
    Bar,
    ChartSeries,
    MarketState,
    NewsItem,
)

QUERY1 = "https://query1.finance.yahoo.com"
QUERY2 = "https://query2.finance.yahoo.com"
VALID_RANGES = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo"}
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}


class SymbolNotFoundError(ConnectorError):
    def __init__(self, symbol: str, detail: str = "symbol_not_found") -> None:
        super().__init__(detail, retryable=False)
        self.symbol = symbol


def num(value: object) -> float | None:
    """Accept raw numbers or Yahoo's {"raw": ..., "fmt": ...} wrappers; never coerce junk."""
    if isinstance(value, dict):
        value = value.get("raw")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    return None


def text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _epoch(value: object) -> datetime | None:
    stamp = num(value)
    return datetime.fromtimestamp(stamp, UTC) if stamp is not None else None


def market_state_from_meta(meta: dict[str, Any], now: datetime | None = None) -> MarketState:
    now_ts = (now or datetime.now(UTC)).timestamp()
    periods = meta.get("currentTradingPeriod") or {}

    def within(name: str) -> bool:
        period = periods.get(name) or {}
        start, end = num(period.get("start")), num(period.get("end"))
        return start is not None and end is not None and start <= now_ts < end

    if within("regular"):
        return "open"
    if within("pre"):
        return "pre"
    if within("post"):
        return "post"
    return "closed"


def chart_url(symbol: str, range_: str, interval: str) -> str:
    return f"{QUERY1}/v8/finance/chart/{quote(symbol, safe='')}?range={range_}&interval={interval}"


def parse_chart(
    payload: dict[str, Any], symbol: str, range_: str, interval: str, now: datetime | None = None
) -> ChartSeries:
    chart = payload.get("chart") or {}
    results = chart.get("result")
    error = chart.get("error")
    if error or not results:
        detail = (error or {}).get("description") if isinstance(error, dict) else None
        raise SymbolNotFoundError(symbol, detail or "symbol_not_found")
    result = results[0]
    meta = result.get("meta") or {}
    stamps = result.get("timestamp") or []
    quote_block = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}

    def column(name: str) -> list[Any]:
        values = quote_block.get(name) or []
        return values if isinstance(values, list) else []

    opens, highs, lows = column("open"), column("high"), column("low")
    closes, volumes = column("close"), column("volume")
    bars: list[Bar] = []
    for i, stamp in enumerate(stamps):
        close = num(closes[i]) if i < len(closes) else None
        when = _epoch(stamp)
        if close is None or when is None:
            continue  # Yahoo emits null rows for halted/illiquid intervals; drop, never fill.
        bars.append(
            Bar(
                t=when,
                open=num(opens[i]) if i < len(opens) else None,
                high=num(highs[i]) if i < len(highs) else None,
                low=num(lows[i]) if i < len(lows) else None,
                close=close,
                volume=num(volumes[i]) if i < len(volumes) else None,
            )
        )

    price = num(meta.get("regularMarketPrice"))
    previous = num(meta.get("previousClose"))
    change_pct = num(meta.get("regularMarketChangePercent"))
    if change_pct is None and price is not None and previous:
        change_pct = (price - previous) / previous * 100
    quality = "good" if bars and price is not None else "missing_fields"
    return ChartSeries(
        symbol=text(meta.get("symbol")) or symbol,
        name=text(meta.get("longName")) or text(meta.get("shortName")),
        currency=text(meta.get("currency")),
        exchange=text(meta.get("fullExchangeName")) or text(meta.get("exchangeName")),
        exchange_timezone=text(meta.get("exchangeTimezoneName")),
        gmt_offset_seconds=int(num(meta.get("gmtoffset")) or 0),
        instrument_type=text(meta.get("instrumentType")),
        price=price,
        previous_close=previous,
        change_pct=change_pct,
        day_high=num(meta.get("regularMarketDayHigh")),
        day_low=num(meta.get("regularMarketDayLow")),
        volume=num(meta.get("regularMarketVolume")),
        fifty_two_week_high=num(meta.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=num(meta.get("fiftyTwoWeekLow")),
        market_time=_epoch(meta.get("regularMarketTime")),
        market_state=market_state_from_meta(meta, now),
        range=range_,
        interval=interval,
        bars=bars,
        source_url=chart_url(symbol, range_, interval),
        data_quality=quality,
    )


def last_session(series: ChartSeries) -> ChartSeries:
    """Keep only bars from the most recent exchange-local trading date."""
    if not series.bars:
        return series
    tz = timezone(timedelta(seconds=series.gmt_offset_seconds))
    last_day = series.bars[-1].t.astimezone(tz).date()
    bars = [bar for bar in series.bars if bar.t.astimezone(tz).date() == last_day]
    return series.model_copy(update={"bars": bars, "range": "1d"})


def parse_search(payload: dict[str, Any]) -> tuple[list[AssetMatch], list[NewsItem]]:
    matches: list[AssetMatch] = []
    for item in payload.get("quotes") or []:
        if not isinstance(item, dict):
            continue
        symbol = text(item.get("symbol"))
        name = text(item.get("longname")) or text(item.get("shortname"))
        if not symbol or not name:
            continue
        matches.append(
            AssetMatch(
                symbol=symbol,
                name=name,
                exchange=text(item.get("exchDisp")) or text(item.get("exchange")),
                quote_type=text(item.get("quoteType")),
                sector=text(item.get("sectorDisp")) or text(item.get("sector")),
            )
        )
    news: list[NewsItem] = []
    for item in payload.get("news") or []:
        if not isinstance(item, dict):
            continue
        title, link = text(item.get("title")), text(item.get("link"))
        if not title or not link:
            continue
        resolutions = ((item.get("thumbnail") or {}).get("resolutions")) or []
        image = next(
            (
                text(r.get("url"))
                for r in resolutions
                if isinstance(r, dict) and r.get("tag") == "original"
            ),
            None,
        )
        news.append(
            NewsItem(
                id=text(item.get("uuid")) or hashlib.sha1(link.encode()).hexdigest()[:16],
                publisher=text(item.get("publisher")) or "Yahoo Finance",
                title=title,
                url=link,
                published_at=_epoch(item.get("providerPublishTime")),
                image_url=image,
                related_tickers=[t for t in item.get("relatedTickers") or [] if isinstance(t, str)],
                provider="yahoo_finance",
            )
        )
    return matches, news


def parse_quote_summary(payload: dict[str, Any], symbol: str) -> AssetProfile:
    summary = payload.get("quoteSummary") or {}
    results = summary.get("result")
    if summary.get("error") or not results:
        raise SymbolNotFoundError(symbol, "profile_not_found")
    result = results[0]
    profile = result.get("assetProfile") or {}
    detail = result.get("summaryDetail") or {}
    price = result.get("price") or {}
    stats = result.get("defaultKeyStatistics") or {}
    return AssetProfile(
        symbol=symbol,
        long_name=text(price.get("longName")) or text(price.get("shortName")),
        sector=text(profile.get("sectorDisp")) or text(profile.get("sector")),
        industry=text(profile.get("industryDisp")) or text(profile.get("industry")),
        city=text(profile.get("city")),
        country=text(profile.get("country")),
        website=text(profile.get("website")),
        market_cap=num(detail.get("marketCap")) or num(price.get("marketCap")),
        trailing_pe=num(detail.get("trailingPE")),
        forward_pe=num(detail.get("forwardPE")) or num(stats.get("forwardPE")),
        beta=num(detail.get("beta")) or num(stats.get("beta")),
        dividend_yield=num(detail.get("dividendYield")),
        average_volume=num(detail.get("averageVolume")),
        currency=text(price.get("currency")) or text(detail.get("currency")),
        quote_type=text(price.get("quoteType")),
        source_url=f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/profile",
    )
