from abc import ABC, abstractmethod
from typing import Any

from stop_loss.domain.enums import DataType
from stop_loss.domain.models import NormalizedRecord


class DataProvider(ABC):
    """Abstract base class establishing the contract for all external data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique machine-readable name of the provider."""

    @property
    @abstractmethod
    def data_type(self) -> DataType:
        """The primary domain data type produced by this provider."""

    @abstractmethod
    def fetch(self, **kwargs: Any) -> Any:
        """Retrieve raw observations or payloads from the external data source.

        Args:
            **kwargs: Source-specific query parameters (e.g. tickers, coordinates, date range).

        Returns:
            Raw provider response data (JSON dict, list of records, XML, etc.).

        Raises:
            ProviderTimeoutError: If the external request times out.
            ProviderRateLimitError: If provider rate limits are exceeded.
            ProviderAuthenticationError: If credentials or API tokens fail.
            ProviderInvalidResponseError: If the response is unparseable or unexpected.
            ProviderUnavailableError: If the external provider is offline or unreachable.
        """

    @abstractmethod
    def normalize(self, raw_data: Any) -> list[NormalizedRecord]:
        """Transform raw provider data into standardized NormalizedRecord models.

        Args:
            raw_data: Raw data returned by the fetch method.

        Returns:
            A list of validated NormalizedRecord instances.
        """
