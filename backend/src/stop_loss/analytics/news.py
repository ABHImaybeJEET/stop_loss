"""Asset news from Google News RSS and Alpha Vantage NEWS_SENTIMENT (scores kept verbatim)."""

import hashlib
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from fin_terminal.config import secret_value
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.resilience import RateLimitedError
from stop_loss.analytics.http import Cached, GuardedHTTP
from stop_loss.analytics.models import NewsItem, Sentiment
from stop_loss.analytics.themes import tag_themes
from stop_loss.analytics.yahoo import num, text
from stop_loss.settings import TerminalSettings

GOOGLE_NEWS = "https://news.google.com/rss/search"
ALPHA_VANTAGE = "https://www.alphavantage.co/query"


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
    def __init__(self, settings: TerminalSettings, client: httpx.AsyncClient | None = None) -> None:
        self.google = GuardedHTTP(settings, rate_per_second=2, burst=4, client=client)
        self.alpha = GuardedHTTP(settings, rate_per_second=1, burst=1, client=client)
        self.alpha_key = secret_value(settings.alpha_vantage_api_key)
        self._google_cache = Cached(settings.news_cache_seconds)
        self._sentiment_cache = Cached(settings.sentiment_cache_seconds)

    async def google_news(self, query: str, *, region: str = "US") -> list[NewsItem]:
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

    async def aclose(self) -> None:
        await self.google.aclose()
        await self.alpha.aclose()
