from typing import Any

from stop_loss.domain.enums import DataType
from stop_loss.domain.models import NormalizedRecord
from stop_loss.ingestion.base import DataProvider


class OpenMeteoProvider(DataProvider):
    """Weather data provider using Open-Meteo API.

    Responsible for capturing marine forecasts, atmospheric pressure, wind speeds,
    and precipitation models relevant to offshore operations and coastal refineries.
    Implementation scheduled for Checkpoint 1.
    """

    @property
    def name(self) -> str:
        return "open_meteo"

    @property
    def data_type(self) -> DataType:
        return DataType.WEATHER

    def fetch(self, **kwargs: Any) -> Any:
        """Fetch raw weather forecast and telemetry.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("OpenMeteoProvider.fetch() will be implemented in Checkpoint 1.")

    def normalize(self, raw_data: Any) -> list[NormalizedRecord]:
        """Normalize Open-Meteo JSON into NormalizedRecord instances.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("OpenMeteoProvider.normalize() scheduled for Checkpoint 1.")
