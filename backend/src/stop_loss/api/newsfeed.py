"""Landing-page market intelligence feed, built from live provider data only."""

import asyncio
import hashlib
from typing import Any

from stop_loss.analytics.models import NewsItem
from stop_loss.analytics.news import NewsClient
from stop_loss.analytics.themes import tag_themes
from stop_loss.analytics.yahoo import YahooFinanceClient


def _article(item: NewsItem) -> dict[str, Any]:
    themes = item.themes or tag_themes(item.title, item.summary)
    return {
        "id": item.id,
        "category": themes[0].value if themes else "MACRO",
        "title": item.title,
        "summary": item.summary or "",
        "source": item.publisher,
        "publishedAt": item.published_at.isoformat() if item.published_at else "",
        "url": item.url,
        "imageUrl": item.image_url,
    }


async def _headlines(yahoo: YahooFinanceClient, news: NewsClient, query: str) -> list[NewsItem]:
    items, _ = await news.collect(query, yahoo=yahoo)
    return items


async def build_feed(
    yahoo: YahooFinanceClient, news: NewsClient, indian_tickers: list[str]
) -> dict[str, list[dict[str, Any]]]:
    top, commodities, *quotes = await asyncio.gather(
        _headlines(yahoo, news, "India NSE stock market"),
        _headlines(yahoo, news, "crude oil gold commodities"),
        *(yahoo.chart(symbol, "5d", "1d") for symbol in indian_tickers),
        return_exceptions=True,
    )
    
    if isinstance(top, BaseException):
        print(f"Error fetching top stories: {type(top).__name__}: {top}")
    if isinstance(commodities, BaseException):
        print(f"Error fetching commodities: {type(commodities).__name__}: {commodities}")

    stocks: list[dict[str, Any]] = []
    for symbol, series in zip(indian_tickers, quotes, strict=True):
        if isinstance(series, BaseException):
            print(f"Error fetching {symbol}: {type(series).__name__}: {series}")
            continue
        change = series.change_pct
        stocks.append(
            {
                "id": hashlib.sha1(symbol.encode()).hexdigest()[:12],
                "category": "MACRO",
                "title": series.name or symbol,
                "summary": "",
                "source": "Yahoo Finance",
                "publishedAt": series.market_time.isoformat() if series.market_time else "",
                "url": f"https://finance.yahoo.com/quote/{symbol}",
                "ticker": symbol.split(".")[0],
                "companyName": series.name,
                "priceInr": f"{series.price:,.2f}",
                "changePercent": f"{change:+.2f}%" if change is not None else "n/a",
                "isPositive": bool(change is not None and change >= 0),
            }
        )
    return {
        "topStories": [_article(i) for i in ([] if isinstance(top, BaseException) else top)][:9],
        "commodities": [
            _article(i) for i in ([] if isinstance(commodities, BaseException) else commodities)
        ][:9],
        "indianStocks": stocks,
    }
