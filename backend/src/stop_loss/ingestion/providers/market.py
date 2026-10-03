from typing import Any

from stop_loss.domain.enums import DataType
from stop_loss.domain.models import NormalizedRecord
from stop_loss.ingestion.base import DataProvider


class YahooFinanceProvider(DataProvider):
    """Market price provider querying Yahoo Finance market feeds.

    Responsible for capturing equity, ETF (e.g. XLE), and futures prices (e.g. NG=F)
    for risk models and correlation tracking. Implementation scheduled for Checkpoint 1.
    """

    @property
    def name(self) -> str:
        return "yahoo_finance"

    @property
    def data_type(self) -> DataType:
        return DataType.MARKET_PRICE

    def fetch(self, **kwargs: Any) -> Any:
        """Fetch raw market price quotes and candles.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("YahooFinanceProvider.fetch() scheduled for Checkpoint 1.")

    def normalize(self, raw_data: Any) -> list[NormalizedRecord]:
        """Normalize market quotes into NormalizedRecord instances.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("YahooFinanceProvider.normalize() scheduled for Checkpoint 1.")
