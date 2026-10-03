from datetime import datetime
import hashlib
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from stop_loss.domain.enums import DataQuality, DataType, MacroTheme, ProviderErrorType, RunStatus


def _validate_tz_aware(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"{field_name} must be timezone-aware (tzinfo cannot be None)")
    return dt


class NormalizedRecord(BaseModel):
    """Normalized schema for heterogeneous intelligence and market data observations."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(
        ...,
        description="Unique identifier for the record (e.g., UUID or deterministic hash).",
    )
    content_hash: str = Field(
        default="",
        description="Deterministic SHA-256 hash across canonical fields for idempotency.",
    )
    data_type: DataType = Field(
        ...,
        description="Type of domain data (weather, news, market_price, macro).",
    )
    provider: str = Field(
        ...,
        description="Identifier of data provider origin (e.g. open_meteo, gdelt, alpha_vantage).",
    )
    theme_tags: list[MacroTheme] = Field(
        default_factory=list,
        description="First-class macro themes (TARIFF, BANK_TAX, WAR_CRISIS, WEATHER_EXTREME).",
    )

    observed_at: datetime = Field(
        ...,
        description="Timestamp when the event occurred or was reported in the physical world.",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Timestamp when the article, report, or quote was officially published.",
    )
    fetched_at: datetime = Field(
        ...,
        description="Timestamp when the record was retrieved by the ingestion engine.",
    )

    entity: str | None = Field(
        default=None,
        description="Associated named entity, corporation, or organization.",
    )
    ticker: str | None = Field(
        default=None,
        description="Financial ticker or asset identifier (e.g., XOM, XLE, NG=F).",
    )
    location: str | None = Field(
        default=None,
        description="Geographic region or coordinates string.",
    )
    indicator: str | None = Field(
        default=None,
        description="Metric or series name (e.g., wind_speed_10m, headline, crude_oil_wti).",
    )

    numeric_value: float | None = Field(
        default=None,
        description="Numeric representation of the observation (null if missing; never fabricate).",
    )
    text_value: str | None = Field(
        default=None,
        description="Textual representation or article content of the observation.",
    )
    unit: str | None = Field(
        default=None,
        description="Unit of measurement (e.g., USD, knots, %, mm).",
    )
    source_url: str | None = Field(
        default=None,
        description="Direct link to source origin or documentation for audit provenance.",
    )

    raw_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Original unmodified raw JSON payload for lineage and audit.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible key-value metadata for downstream agents.",
    )
    is_demo: bool = Field(
        default=False,
        description="Flag indicating synthetic or demo playback data.",
    )

    # Ingestion audit & telemetry fields
    data_quality: DataQuality = Field(
        default=DataQuality.GOOD,
        description="Data quality audit status (good, missing_fields, degraded, suspect).",
    )
    ingest_run_id: str | None = Field(
        default=None,
        description="Ingestion run UUID associated with this record.",
    )
    langsmith_run_id: str | None = Field(
        default=None,
        description="LangSmith run ID for tracing downstream agent operations.",
    )
    fetch_latency_ms: float | None = Field(
        default=None,
        description="External network fetch latency in milliseconds.",
    )
    process_latency_ms: float | None = Field(
        default=None,
        description="Internal normalization, embedding, and indexing latency in milliseconds.",
    )

    @field_validator("observed_at", mode="after")
    @classmethod
    def validate_observed_at_tz(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "observed_at")

    @field_validator("fetched_at", mode="after")
    @classmethod
    def validate_fetched_at_tz(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "fetched_at")

    @field_validator("published_at", mode="after")
    @classmethod
    def validate_published_at_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return _validate_tz_aware(v, "published_at")
        return v

    def calculate_content_hash(self) -> str:
        """Compute deterministic SHA-256 hash across canonical fields."""
        components = [
            self.provider,
            str(self.data_type.value),
            self.observed_at.isoformat(),
            self.indicator or "",
            self.ticker or self.entity or self.location or "",
            str(self.numeric_value) if self.numeric_value is not None else "",
            self.text_value or "",
        ]
        return hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_and_compute_fields(self) -> Self:
        if self.numeric_value is None and self.text_value is None:
            raise ValueError("At least one of numeric_value or text_value must be provided.")
        if not self.content_hash:
            self.content_hash = self.calculate_content_hash()
        return self


class IngestionRun(BaseModel):
    """Record tracking an execution instance of a data provider ingestion cycle."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(
        ...,
        description="Unique identifier for the ingestion run.",
    )
    provider: str = Field(
        ...,
        description="Identifier of the provider being executed.",
    )
    started_at: datetime = Field(
        ...,
        description="Timestamp when the run was initiated.",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="Timestamp when the run completed or failed.",
    )
    status: RunStatus = Field(
        default=RunStatus.RUNNING,
        description="Current status of the ingestion run.",
    )

    records_fetched: int = Field(
        default=0,
        ge=0,
        description="Total records retrieved from the provider.",
    )
    records_inserted: int = Field(
        default=0,
        ge=0,
        description="Total new records persisted to storage.",
    )
    records_updated: int = Field(
        default=0,
        ge=0,
        description="Total existing records updated.",
    )
    records_skipped: int = Field(
        default=0,
        ge=0,
        description="Total duplicate or invalid records skipped.",
    )

    error_type: ProviderErrorType | None = Field(
        default=None,
        description="Categorized error type if the run failed.",
    )
    error_message: str | None = Field(
        default=None,
        description="Detailed error message if the run failed.",
    )

    @field_validator("started_at", mode="after")
    @classmethod
    def validate_started_at_tz(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "started_at")

    @field_validator("finished_at", mode="after")
    @classmethod
    def validate_finished_at_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return _validate_tz_aware(v, "finished_at")
        return v
