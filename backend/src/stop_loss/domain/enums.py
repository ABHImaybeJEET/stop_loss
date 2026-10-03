from enum import StrEnum


class DataType(StrEnum):
    """Categorization of data collected across market, macro, and alternative sources."""

    WEATHER = "weather"
    NEWS = "news"
    MARKET_PRICE = "market_price"
    MACRO = "macro"


class RunStatus(StrEnum):
    """Execution status of an ingestion run."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class ProviderErrorType(StrEnum):
    """Categorized provider operational error types."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    INVALID_RESPONSE = "invalid_response"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
