from pydantic import JsonValue

from fin_terminal.connectors.base import AsyncConnector
from fin_terminal.schemas import Document, NewsArticle, StreamStatus, utcnow
from stop_loss.analytics.models import NewsItem
from stop_loss.analytics.news import NewsClient

THEME_QUERIES = {
    "news_tariff": "(India OR global) (tariff OR trade war OR export restrictions)",
    "news_banktax": "(India OR RBI) "
    "(bank tax OR bank levy OR interest rates OR reserve requirements)",
    "news_war": "(war OR sanctions OR shipping disruption OR oil supply) (India OR global)",
}


class LiveNewsConnector(AsyncConnector):
    provider = "live_news"

    def __init__(self, source: str, client: NewsClient, *, owns_client: bool = False) -> None:
        self._source = source
        self.client = client
        self.owns_client = owns_client
        self._status = StreamStatus(source=source, status="degraded", message="not_fetched")

    @property
    def source(self) -> str:
        return self._source

    async def fetch(self) -> list[JsonValue]:
        try:
            items, failures = await self.client.collect(THEME_QUERIES[self.source])
        except Exception:
            self._status = StreamStatus(source=self.source, status="failed")
            raise
        self._status = StreamStatus(
            source=self.source,
            status="degraded" if failures else "ok",
            records_fetched=len(items),
            message=",".join(sorted(failures)) or None,
        )
        return [item.model_dump(mode="json") for item in items]

    async def normalize(self, raw: list[JsonValue]) -> list[Document]:
        records: list[Document] = []
        for row in raw:
            item = NewsItem.model_validate(row)
            records.append(
                NewsArticle(
                    source=self.source,
                    provider=item.provider,
                    source_url=item.url,
                    published_at=item.published_at,
                    observed_at=item.observed_at,
                    fetched_at=utcnow(),
                    ingest_run_id="pending",
                    title=item.title,
                    text=item.summary or item.title,
                    theme_tags=item.themes,
                )
            )
        return records

    async def health(self) -> StreamStatus:
        return self._status

    async def close(self) -> None:
        if self.owns_client:
            await self.client.aclose()
