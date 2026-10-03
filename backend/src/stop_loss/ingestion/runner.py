import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from stop_loss.domain.enums import ProviderErrorType, RunStatus
from stop_loss.domain.errors import ProviderError
from stop_loss.domain.models import IngestionRun, NormalizedRecord
from stop_loss.ingestion.base import DataProvider
from stop_loss.storage.base import RecordRepository

logger = logging.getLogger(__name__)


class IngestionRunner:
    """Coordinates execution of data providers, normalization, and persistence."""

    def __init__(
        self,
        repository: RecordRepository | None = None,
        providers: Sequence[DataProvider] | None = None,
    ) -> None:
        self.repository = repository
        self.providers = list(providers) if providers else []

    def register_provider(self, provider: DataProvider) -> None:
        """Register a data provider instance."""
        self.providers.append(provider)

    def run_provider(self, provider: DataProvider) -> IngestionRun:
        """Execute a single provider cycle with error handling and metric tracking.

        In Checkpoint 0, this outlines the operational flow.
        Working execution and persistence is scheduled for Checkpoint 1.
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        run = IngestionRun(
            run_id=run_id,
            provider=provider.name,
            started_at=started_at,
            status=RunStatus.RUNNING,
        )

        try:
            raw_data = provider.fetch()
            records: list[NormalizedRecord] = provider.normalize(raw_data)
            run.records_fetched = len(records)

            if self.repository is not None:
                inserted = self.repository.bulk_upsert_records(records)
                run.records_inserted = inserted
                run.records_skipped = len(records) - inserted

            run.status = RunStatus.SUCCESS
        except NotImplementedError as exc:
            run.status = RunStatus.FAILED
            run.error_type = ProviderErrorType.UNKNOWN
            run.error_message = f"Provider not yet implemented: {exc}"
        except ProviderError as exc:
            run.status = RunStatus.FAILED
            run.error_type = exc.error_type
            run.error_message = exc.message
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error_type = ProviderErrorType.UNKNOWN
            run.error_message = str(exc)
        finally:
            run.finished_at = datetime.now(UTC)
            if self.repository is not None:
                try:
                    self.repository.save_ingestion_run(run)
                except Exception as save_err:
                    logger.error("Failed to persist ingestion run record: %s", save_err)

        return run
