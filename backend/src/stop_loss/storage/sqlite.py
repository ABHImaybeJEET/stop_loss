from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from stop_loss.domain.enums import DataType
from stop_loss.domain.models import IngestionRun, NormalizedRecord
from stop_loss.storage.base import RecordRepository


class SQLiteRecordRepository(RecordRepository):
    """SQLite implementation of the RecordRepository contract.

    Provides embedded, zero-configuration local persistence with WAL mode,
    indexing on data_type, provider, ticker, and observed_at timestamps.
    Working implementation is scheduled for Checkpoint 1.
    """

    def __init__(self, database_path: Path | str = "data/stop_loss.db") -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        """Create tables and indexes. Scheduled for Checkpoint 1."""
        raise NotImplementedError("SQLite initialization will be implemented in Checkpoint 1.")

    def upsert_record(self, record: NormalizedRecord) -> None:
        """Insert or replace record. Scheduled for Checkpoint 1."""
        raise NotImplementedError("upsert_record will be implemented in Checkpoint 1.")

    def bulk_upsert_records(self, records: Sequence[NormalizedRecord]) -> int:
        """Bulk upsert transaction. Scheduled for Checkpoint 1."""
        raise NotImplementedError("bulk_upsert_records will be implemented in Checkpoint 1.")

    def get_record_by_id(self, record_id: str) -> NormalizedRecord | None:
        """Fetch record by ID. Scheduled for Checkpoint 1."""
        raise NotImplementedError("get_record_by_id will be implemented in Checkpoint 1.")

    def get_records_by_type(self, data_type: DataType, limit: int = 100) -> list[NormalizedRecord]:
        """Query by data type. Scheduled for Checkpoint 1."""
        raise NotImplementedError("get_records_by_type will be implemented in Checkpoint 1.")

    def get_records_by_provider(self, provider: str, limit: int = 100) -> list[NormalizedRecord]:
        """Query by provider. Scheduled for Checkpoint 1."""
        raise NotImplementedError("get_records_by_provider will be implemented in Checkpoint 1.")

    def get_records_by_entity_or_ticker(
        self, query: str, limit: int = 100
    ) -> list[NormalizedRecord]:
        """Query by entity or ticker. Scheduled for Checkpoint 1."""
        raise NotImplementedError(
            "get_records_by_entity_or_ticker will be implemented in Checkpoint 1."
        )

    def get_records_by_time_range(
        self, start: datetime, end: datetime, limit: int = 100
    ) -> list[NormalizedRecord]:
        """Query by time window. Scheduled for Checkpoint 1."""
        raise NotImplementedError("get_records_by_time_range will be implemented in Checkpoint 1.")

    def search_records(self, query: str, limit: int = 100) -> list[NormalizedRecord]:
        """Keyword search. Scheduled for Checkpoint 1."""
        raise NotImplementedError("search_records will be implemented in Checkpoint 1.")

    def save_ingestion_run(self, run: IngestionRun) -> None:
        """Persist ingestion audit record. Scheduled for Checkpoint 1."""
        raise NotImplementedError("save_ingestion_run will be implemented in Checkpoint 1.")

    def list_recent_ingestion_runs(self, limit: int = 20) -> list[IngestionRun]:
        """List past ingestion runs. Scheduled for Checkpoint 1."""
        raise NotImplementedError("list_recent_ingestion_runs will be implemented in Checkpoint 1.")
