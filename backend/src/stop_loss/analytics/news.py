"""Live news aggregation from Google RSS, GDELT, and yfinance with source isolation."""

import asyncio
import hashlib
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from fin_terminal.config import Settings, secret_value
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.resilience import RateLimitedError
from stop_loss.analytics.http import Cached, GuardedHTTP
from stop_loss.analytics.models import NewsItem, Sentiment
from stop_loss.analytics.themes import tag_themes
from stop_loss.analytics.yahoo import YahooFinanceClient, num, text

GOOGLE_NEWS = "https://news.google.com/rss/search"
ALPHA_VANTAGE = "https://www.alphavantage.co/query"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"


def parse_gdelt(payload: dict[str, Any]) -> list[NewsItem]:
    rows = payload.get("articles")
    if not isinstance(rows, list):
        raise ConnectorError("gdelt_invalid_envelope")
    items = []
    for row in rows:
        title, url = text(row.get("title")), text(row.get("url"))
        if not title or not url or not url.startswith(("https://", "http://")):
            continue
        seen = None
        try:
            seen = datetime.strptime(row.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except (ValueError, TypeError):
            pass
        items.append(
            NewsItem(
                id=hashlib.sha256(url.encode()).hexdigest()[:16],
                publisher=text(row.get("domain")) or "GDELT",
                title=title,
                url=url,
                observed_at=seen,
                published_at=None,
                provider="gdelt",
                image_url=text(row.get("socialimage")),
                themes=tag_themes(title),
            )
        )
    return items


def dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen_urls, seen_titles = set(), set()
    result = []
    for item in items:
        url = urlsplit(item.url)
        canonical = urlunsplit(
            (url.scheme, url.netloc.lower(), url.path.rstrip("/"), url.query, "")
        )
        title = " ".join(item.title.casefold().split())
        if canonical in seen_urls or title in seen_titles:
            continue
        seen_urls.add(canonical)
        seen_titles.add(title)
        result.append(item)
    return sorted(
        result,
        key=lambda i: i.published_at or i.observed_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


def sentiment_label(score: float) -> Sentiment:
    """Alpha Vantage's own bands: |x| < 0.15 is Neutral."""
    if score <= -0.15:
        return "negative"
    if score >= 0.15:
        return "positive"
    return "neutral"


def parse_google_news_rss(xml_text: str, limit: int = 12) -> list[NewsItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise ConnectorError("invalid_rss") from None
    items: list[NewsItem] = []
    for node in root.iterfind("./channel/item"):
        title = text(node.findtext("title"))
        link = text(node.findtext("link"))
        if not title or not link:
            continue
        source = node.find("source")
        publisher = text(source.text if source is not None else None)
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3]
        published = None
        if stamp := text(node.findtext("pubDate")):
            try:
                published = parsedate_to_datetime(stamp).astimezone(UTC)
            except (TypeError, ValueError):
                published = None
        items.append(
            NewsItem(
                id=hashlib.sha1(link.encode()).hexdigest()[:16],
                publisher=publisher or "Google News",
                title=title,
                url=link,
                published_at=published,
                provider="google_news_rss",
                themes=tag_themes(title),
            )
        )
        if len(items) >= limit:
            break
    return items


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_alpha_vantage_sentiment(
    payload: dict[str, Any], ticker: str, limit: int = 12
) -> list[NewsItem]:
    feed = payload.get("feed")
    if not isinstance(feed, list):
        note = str(payload.get("Information") or payload.get("Note") or "")
        if "rate" in note.lower() or "requests per day" in note.lower():
            raise RateLimitedError("provider_rate_limited")
        raise ConnectorError("unavailable_feed")
    items: list[NewsItem] = []
    for entry in feed:
        if not isinstance(entry, dict):
            continue
        title, url = text(entry.get("title")), text(entry.get("url"))
        if not title or not url:
            continue
        score = None
        for row in _as_list(entry.get("ticker_sentiment")):
            if isinstance(row, dict) and str(row.get("ticker", "")).upper() == ticker.upper():
                score = _float(row.get("ticker_sentiment_score"))
        if score is None:
            score = _float(entry.get("overall_sentiment_score"))
        published = None
        if stamp := text(entry.get("time_published")):
            try:
                published = datetime.strptime(stamp, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
            except ValueError:
                published = None
        summary = text(entry.get("summary"))
        items.append(
            NewsItem(
                id=hashlib.sha1(url.encode()).hexdigest()[:16],
                publisher=text(entry.get("source")) or "Alpha Vantage",
                title=title,
                url=url,
                published_at=published,
                summary=summary,
                image_url=text(entry.get("banner_image")),
                provider="alpha_vantage_news",
                sentiment=sentiment_label(score) if score is not None else None,
                sentiment_score=score,
                sentiment_source="alpha_vantage" if score is not None else None,
                themes=tag_themes(title, summary),
            )
        )
        if len(items) >= limit:
            break
    return items


def _float(value: object) -> float | None:
    if isinstance(value, str):
        try:
            return num(float(value))
        except ValueError:
            return None
    return num(value)


class NewsClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.google = GuardedHTTP(settings, rate_per_second=2, burst=4, client=client)
        self.alpha = GuardedHTTP(settings, rate_per_second=1, burst=1, client=client)
        self.alpha_key = secret_value(settings.alpha_vantage_api_key)
        self.gdelt = GuardedHTTP(settings, rate_per_second=0.2, burst=1, client=client)
        self.gdelt_enabled = settings.news_gdelt_enabled
        self.source_timeout = min(8.0, settings.http_timeout_seconds * 0.6)
        self._gdelt_cache = Cached(settings.news_cache_seconds)
        self._google_cache = Cached(settings.news_cache_seconds)
        self._sentiment_cache = Cached(settings.sentiment_cache_seconds)

    async def google_news(self, query: str, *, region: str = "IN") -> list[NewsItem]:
        key = f"{query}|{region}"
        if (hit := self._google_cache.get(key)) is not None:
            return hit
        locale = {"IN": ("en-IN", "IN", "IN:en")}.get(region, ("en-US", "US", "US:en"))
        response = await self.google.get(
            GOOGLE_NEWS,
            {"q": f"{query} when:7d", "hl": locale[0], "gl": locale[1], "ceid": locale[2]},
        )
        if response.status_code != 200:
            raise ConnectorError(f"http_{response.status_code}")
        items = parse_google_news_rss(response.text)
        self._google_cache.put(key, items)
        return items

    async def alpha_vantage_ticker_news(self, ticker: str) -> list[NewsItem]:
        """Scored headlines for US-listed tickers. Free tier: ~25 calls/day, so cache hard."""
        if not self.alpha_key:
            raise ConnectorError("alpha_vantage_key_missing")
        if (hit := self._sentiment_cache.get(ticker)) is not None:
            return hit
        payload = await self.alpha.get_json(
            ALPHA_VANTAGE,
            {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "limit": 50,
                "apikey": self.alpha_key,
            },
        )
        items = parse_alpha_vantage_sentiment(payload, ticker)
        self._sentiment_cache.put(ticker, items)
        return items

    async def gdelt_news(self, query: str) -> list[NewsItem]:
        if (hit := self._gdelt_cache.get(query)) is not None:
            return hit
        payload = await self.gdelt.get_json(
            GDELT,
            {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": 25,
                "timespan": "7d",
                "sort": "datedesc",
            },
        )
        items = parse_gdelt(payload)
        self._gdelt_cache.put(query, items)
        return items

    async def collect(
        self,
        query: str,
        *,
        yahoo: YahooFinanceClient | None = None,
        symbol: str | None = None,
    ) -> tuple[list[NewsItem], dict[str, str]]:
        jobs = {"google_news_rss": self.google_news(query, region="IN")}
        if self.gdelt_enabled:
            jobs["gdelt"] = self.gdelt_news(query)
        if yahoo is not None:

            async def yahoo_news() -> list[NewsItem]:
                if symbol:
                    return await yahoo.ticker_news(symbol)
                return (await yahoo.search(query, quotes=0, news=8))[1]

            jobs["yfinance"] = yahoo_news()
        values = await asyncio.gather(
            *(asyncio.wait_for(job, self.source_timeout) for job in jobs.values()),
            return_exceptions=True,
        )
        items, failures = [], {}
        for source, value in zip(jobs, values, strict=True):
            if isinstance(value, Exception):
                failures[source] = type(value).__name__
            elif isinstance(value, BaseException):
                raise value
            else:
                items.extend(value)
        if len(failures) == len(jobs):
            raise ConnectorError("all_news_sources_unavailable")
        return dedupe_news(items), failures

    async def aclose(self) -> None:
        await self.google.aclose()
        await self.alpha.aclose()
        await self.gdelt.aclose()
