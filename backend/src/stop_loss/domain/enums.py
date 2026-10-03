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


class MacroTheme(StrEnum):
    """First-class macro themes tagged on every record for downstream agents."""

    TARIFF = "tariff"
    BANK_TAX = "bank_tax"
    WAR_CRISIS = "war_crisis"
    WEATHER_EXTREME = "weather_extreme"


class DataQuality(StrEnum):
    """Data quality and integrity audit flag."""

    GOOD = "good"
    MISSING_FIELDS = "missing_fields"
    DEGRADED = "degraded"
    SUSPECT = "suspect"


class VectorBackend(StrEnum):
    """Supported vector database backends."""

    WEAVIATE = "weaviate"
    PINECONE = "pinecone"
    MEMORY = "memory"


class EmbeddingBackend(StrEnum):
    """Supported text embedding models."""

    LOCAL = "local"
    OPENAI = "openai"
