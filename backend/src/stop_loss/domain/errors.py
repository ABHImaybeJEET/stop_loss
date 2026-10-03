from stop_loss.domain.enums import ProviderErrorType


class StopLossError(Exception):
    """Base exception class for all StopLoss errors."""


class ProviderError(StopLossError):
    """Base exception for external data provider failures."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        error_type: ProviderErrorType = ProviderErrorType.UNKNOWN,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.error_type = error_type

    def __str__(self) -> str:
        prov_prefix = f"[{self.provider}] " if self.provider else ""
        return f"{prov_prefix}({self.error_type.value}): {self.message}"


class ProviderTimeoutError(ProviderError):
    """Raised when an external data provider request times out."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message, provider=provider, error_type=ProviderErrorType.TIMEOUT)


class ProviderRateLimitError(ProviderError):
    """Raised when an external data provider rejects requests due to rate limits."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message, provider=provider, error_type=ProviderErrorType.RATE_LIMIT)


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication or API key validation fails for a provider."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message, provider=provider, error_type=ProviderErrorType.AUTHENTICATION)


class ProviderInvalidResponseError(ProviderError):
    """Raised when an external data provider returns a malformed or unexpected payload."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message, provider=provider, error_type=ProviderErrorType.INVALID_RESPONSE)


class ProviderUnavailableError(ProviderError):
    """Raised when external data provider service is unavailable (e.g. 503, connection dropped)."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message, provider=provider, error_type=ProviderErrorType.UNAVAILABLE)


class StorageError(StopLossError):
    """Base exception for storage and repository operations."""


class RecordNotFoundError(StorageError):
    """Raised when a specific record is not found in the repository."""
