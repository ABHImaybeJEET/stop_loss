from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from stop_loss.domain.enums import DataType, ProviderErrorType, RunStatus
from stop_loss.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RecordNotFoundError,
    StopLossError,
    StorageError,
)
from stop_loss.domain.models import IngestionRun, NormalizedRecord


class TestNormalizedRecord:
    """Unit tests for NormalizedRecord domain model validation."""

    def test_valid_record_with_numeric_value(self) -> None:
        now = datetime.now(UTC)
        record = NormalizedRecord(
            record_id="rec-001",
            data_type=DataType.MARKET_PRICE,
            provider="yahoo_finance",
            observed_at=now,
            fetched_at=now,
            ticker="XOM",
            numeric_value=115.50,
            unit="USD",
        )
        assert record.record_id == "rec-001"
        assert record.data_type == DataType.MARKET_PRICE
        assert record.provider == "yahoo_finance"
        assert record.ticker == "XOM"
        assert record.numeric_value == 115.50
        assert record.text_value is None
        assert record.is_demo is False
        assert record.metadata == {}
        assert record.raw_payload == {}

    def test_valid_record_with_text_value(self) -> None:
        now = datetime.now(UTC)
        record = NormalizedRecord(
            record_id="rec-002",
            data_type=DataType.NEWS,
            provider="gdelt",
            observed_at=now,
            fetched_at=now,
            text_value="Refinery shuts down ahead of hurricane landfall in Gulf.",
            source_url="https://example.com/news/123",
        )
        assert record.record_id == "rec-002"
        assert record.data_type == DataType.NEWS
        assert record.numeric_value is None
        assert record.text_value == "Refinery shuts down ahead of hurricane landfall in Gulf."
        assert record.source_url == "https://example.com/news/123"

    def test_valid_record_with_both_numeric_and_text(self) -> None:
        now = datetime.now(UTC)
        record = NormalizedRecord(
            record_id="rec-003",
            data_type=DataType.WEATHER,
            provider="open_meteo",
            observed_at=now,
            fetched_at=now,
            location="Corpus Christi, Texas",
            indicator="wind_speed_10m",
            numeric_value=75.2,
            text_value="Category 1 sustained winds detected",
            unit="knots",
        )
        assert record.numeric_value == 75.2
        assert record.text_value == "Category 1 sustained winds detected"

    def test_missing_both_numeric_and_text_raises_validation_error(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="At least one of numeric_value or text_value"):
            NormalizedRecord(
                record_id="rec-invalid",
                data_type=DataType.WEATHER,
                provider="open_meteo",
                observed_at=now,
                fetched_at=now,
            )

    def test_timezone_naive_observed_at_raises_error(self) -> None:
        naive_dt = datetime(2026, 10, 3, 12, 0, 0)
        aware_dt = datetime.now(UTC)
        with pytest.raises(ValidationError, match="observed_at must be timezone-aware"):
            NormalizedRecord(
                record_id="rec-naive-obs",
                data_type=DataType.MACRO,
                provider="fred",
                observed_at=naive_dt,
                fetched_at=aware_dt,
                numeric_value=3.4,
            )

    def test_timezone_naive_fetched_at_raises_error(self) -> None:
        aware_dt = datetime.now(UTC)
        naive_dt = datetime(2026, 10, 3, 12, 0, 0)
        with pytest.raises(ValidationError, match="fetched_at must be timezone-aware"):
            NormalizedRecord(
                record_id="rec-naive-fetch",
                data_type=DataType.MACRO,
                provider="fred",
                observed_at=aware_dt,
                fetched_at=naive_dt,
                numeric_value=3.4,
            )

    def test_mutable_default_isolation(self) -> None:
        now = datetime.now(UTC)
        rec1 = NormalizedRecord(
            record_id="rec-1",
            data_type=DataType.NEWS,
            provider="gdelt",
            observed_at=now,
            fetched_at=now,
            text_value="News 1",
        )
        rec2 = NormalizedRecord(
            record_id="rec-2",
            data_type=DataType.NEWS,
            provider="gdelt",
            observed_at=now,
            fetched_at=now,
            text_value="News 2",
        )
        rec1.metadata["key"] = "value"
        rec1.raw_payload["raw"] = 123
        assert "key" not in rec2.metadata
        assert "raw" not in rec2.raw_payload


class TestIngestionRun:
    """Unit tests for IngestionRun model."""

    def test_ingestion_run_defaults(self) -> None:
        now = datetime.now(UTC)
        run = IngestionRun(
            run_id="run-001",
            provider="open_meteo",
            started_at=now,
        )
        assert run.run_id == "run-001"
        assert run.provider == "open_meteo"
        assert run.status == RunStatus.RUNNING
        assert run.records_fetched == 0
        assert run.records_inserted == 0
        assert run.records_updated == 0
        assert run.records_skipped == 0
        assert run.finished_at is None
        assert run.error_type is None
        assert run.error_message is None

    def test_ingestion_run_timezone_validation(self) -> None:
        naive_dt = datetime(2026, 10, 3, 12, 0, 0)
        with pytest.raises(ValidationError, match="started_at must be timezone-aware"):
            IngestionRun(
                run_id="run-bad-tz",
                provider="open_meteo",
                started_at=naive_dt,
            )

    def test_ingestion_run_counter_validation(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            IngestionRun(
                run_id="run-negative-counter",
                provider="open_meteo",
                started_at=now,
                records_fetched=-1,
            )


class TestDomainEnumsAndErrors:
    """Unit tests for enums and error hierarchy."""

    def test_data_type_values(self) -> None:
        assert DataType.WEATHER.value == "weather"
        assert DataType.NEWS.value == "news"
        assert DataType.MARKET_PRICE.value == "market_price"
        assert DataType.MACRO.value == "macro"

    def test_run_status_values(self) -> None:
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.SUCCESS.value == "success"
        assert RunStatus.PARTIAL_SUCCESS.value == "partial_success"
        assert RunStatus.FAILED.value == "failed"

    def test_provider_error_type_values(self) -> None:
        assert ProviderErrorType.TIMEOUT.value == "timeout"
        assert ProviderErrorType.RATE_LIMIT.value == "rate_limit"
        assert ProviderErrorType.AUTHENTICATION.value == "authentication"
        assert ProviderErrorType.INVALID_RESPONSE.value == "invalid_response"
        assert ProviderErrorType.UNAVAILABLE.value == "unavailable"
        assert ProviderErrorType.UNKNOWN.value == "unknown"

    def test_error_hierarchy(self) -> None:
        assert issubclass(ProviderError, StopLossError)
        assert issubclass(StorageError, StopLossError)
        assert issubclass(RecordNotFoundError, StorageError)
        assert issubclass(ProviderTimeoutError, ProviderError)
        assert issubclass(ProviderRateLimitError, ProviderError)
        assert issubclass(ProviderAuthenticationError, ProviderError)
        assert issubclass(ProviderInvalidResponseError, ProviderError)
        assert issubclass(ProviderUnavailableError, ProviderError)

    def test_error_attributes(self) -> None:
        err = ProviderTimeoutError("Connection dropped after 15s", provider="open_meteo")
        assert err.provider == "open_meteo"
        assert err.error_type == ProviderErrorType.TIMEOUT
        assert "Connection dropped" in str(err)
