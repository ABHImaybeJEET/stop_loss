"""Immutable records with explicit provenance and no metric imputation."""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    field_validator,
    model_validator,
)


class Theme(StrEnum):
    TARIFF = "TARIFF"
    BANK_TAX = "BANK_TAX"
    WAR_CRISIS = "WAR_CRISIS"
    WEATHER_EXTREME = "WEATHER_EXTREME"


Quality = Literal["good", "missing_fields", "degraded", "suspect"]
StreamHealth = Literal["ok", "degraded", "failed", "rate_limited"]


def utcnow() -> datetime:
    return datetime.now(UTC)


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    kind: Literal["document"] = "document"
    source: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    source_url: str | None = None
    published_at: AwareDatetime | None = None
    observed_at: AwareDatetime | None = None
    fetched_at: AwareDatetime
    ingest_run_id: str = Field(min_length=1)
    content_hash: str = ""
    theme_tags: list[Theme] = Field(default_factory=list)
    langsmith_run_id: str | None = None
    data_quality: Quality = "good"
    text: str | None = None
    fetch_latency_ms: float = Field(default=0, ge=0)
    process_latency_ms: float = Field(default=0, ge=0)
    schema_version: Literal["1"] = "1"
    raw_reference: str | None = None
    transformations: list[str] = Field(default_factory=list)
    language: str | None = None

    @field_validator("published_at", "observed_at", "fetched_at")
    @classmethod
    def canonical_timezone(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def validate_quality_and_hash(self) -> Self:
        missing = (
            self.source_url is None
            or (self.published_at is None and self.observed_at is None)
            or (isinstance(self, PricePoint) and self.price is None)
            or (isinstance(self, MacroIndicator) and self.value is None)
            or (isinstance(self, WeatherEvent) and self.value is None)
            or (isinstance(self, NewsArticle) and not self.title)
            or (self.kind == "document" and not self.text)
        )
        if missing and self.data_quality == "good":
            object.__setattr__(self, "data_quality", "missing_fields")
        payload = self.model_dump(
            mode="json",
            exclude={
                "content_hash",
                "fetched_at",
                "ingest_run_id",
                "langsmith_run_id",
                "theme_tags",
                "data_quality",
                "fetch_latency_ms",
                "process_latency_ms",
                "schema_version",
                "raw_reference",
                "transformations",
                "language",
            },
        )
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        if self.content_hash and self.content_hash != digest:
            raise ValueError("content_hash does not match canonical content")
        object.__setattr__(self, "content_hash", digest)
        return self


class PricePoint(Document):
    kind: Literal["price"] = "price"
    symbol: str
    price: float | None = None
    currency: str | None = None
    volume: float | None = Field(default=None, ge=0)


class MacroIndicator(Document):
    kind: Literal["macro"] = "macro"
    series_id: str
    value: float | None = None
    unit: str | None = None


class WeatherEvent(Document):
    kind: Literal["weather"] = "weather"
    location: str
    metric: str
    value: float | None = None
    unit: str | None = None


class NewsArticle(Document):
    kind: Literal["news"] = "news"
    title: str | None = None


Record = Annotated[
    Document | PricePoint | MacroIndicator | WeatherEvent | NewsArticle,
    Field(discriminator="kind"),
]
RECORD_ADAPTER: TypeAdapter[Record] = TypeAdapter(Record)


class StreamStatus(BaseModel):
    source: str
    status: StreamHealth = "ok"
    records_fetched: int = Field(default=0, ge=0)
    records_normalized: int = Field(default=0, ge=0)
    records_rejected: int = Field(default=0, ge=0)
    records_dropped: int = Field(default=0, ge=0)
    availability: Literal["available", "stale", "unavailable"] = "unavailable"
    last_successful_update: AwareDatetime | None = None
    fetch_latency_ms: float = Field(default=0, ge=0)
    message: str | None = None
    checked_at: AwareDatetime = Field(default_factory=utcnow)


class EvidenceLogEntry(BaseModel):
    timestamp: AwareDatetime = Field(default_factory=utcnow)
    ingest_run_id: str
    stage: str
    event: str
    source: str | None = None
    langsmith_run_id: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)
