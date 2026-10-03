from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from stop_loss.domain.enums import DataType, ProviderErrorType, RunStatus


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
    data_type: DataType = Field(
        ...,
        description="Type of domain data (weather, news, market_price, macro).",
    )
    provider: str = Field(
        ...,
        description="Identifier of the data provider origin (e.g. open_meteo, gdelt).",
    )
    observed_at: datetime = Field(
        ...,
        description="Timestamp when the event occurred or was reported in the world.",
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
        description="Financial ticker or asset identifier (e.g., XOM, XLE).",
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
        description="Numeric representation of the observation.",
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
        description="Direct link to source origin or documentation.",
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

    @field_validator("observed_at", mode="after")
    @classmethod
    def validate_observed_at_tz(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "observed_at")

    @field_validator("fetched_at", mode="after")
    @classmethod
    def validate_fetched_at_tz(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "fetched_at")

    @model_validator(mode="after")
    def validate_value_present(self) -> Self:
        if self.numeric_value is None and self.text_value is None:
            raise ValueError("At least one of numeric_value or text_value must be provided.")
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
