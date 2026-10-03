from typing import Any

from stop_loss.domain.enums import DataType
from stop_loss.domain.models import NormalizedRecord
from stop_loss.ingestion.base import DataProvider


class FREDProvider(DataProvider):
    """Macroeconomic data provider querying Federal Reserve Economic Data (FRED).

    Responsible for ingesting interest rates, oil benchmarks (e.g. WTI), CPI,
    and macroeconomic volatility gauges. Implementation scheduled for Checkpoint 1.
    """

    @property
    def name(self) -> str:
        return "fred"

    @property
    def data_type(self) -> DataType:
        return DataType.MACRO

    def fetch(self, **kwargs: Any) -> Any:
        """Fetch raw FRED observations for configured series.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("FREDProvider.fetch() will be implemented in Checkpoint 1.")

    def normalize(self, raw_data: Any) -> list[NormalizedRecord]:
        """Normalize FRED observations into NormalizedRecord instances.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("FREDProvider.normalize() will be implemented in Checkpoint 1.")
