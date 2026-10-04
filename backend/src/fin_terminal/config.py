"""Environment-only configuration; retain the existing provider settings."""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, SecretStr, field_validator

from stop_loss.config import Settings as LegacySettings
from stop_loss.symbols import nse_symbol


class ConnectorPolicy(BaseModel):
    timeout_seconds: float = Field(default=15, gt=0)
    rate_per_second: float = Field(default=1, gt=0)
    burst: int = Field(default=1, ge=1)
    concurrency: int = Field(default=2, ge=1, le=32)
    retries: int = Field(default=3, ge=1, le=10)


class Settings(LegacySettings):
    market_tickers: list[str] | str = Field(
        default_factory=lambda: ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"]
    )
    yahoo_rate_per_second: float = Field(default=2, gt=0)
    quote_cache_seconds: float = Field(default=5, gt=0)
    history_cache_seconds: float = Field(default=300, gt=0)
    profile_cache_seconds: float = Field(default=1800, gt=0)
    news_cache_seconds: float = Field(default=300, gt=0)
    sentiment_cache_seconds: float = Field(default=1800, gt=0)
    news_gdelt_enabled: bool = True

    @field_validator("market_tickers", mode="after")
    @classmethod
    def only_nse_tickers(cls, value: list[str] | str) -> list[str]:
        values = value.split(",") if isinstance(value, str) else value
        return list(dict.fromkeys(nse_symbol(v) for v in values if v.strip()))

    checkpoint_path: Path = Path("data/checkpoints.sqlite")
    evidence_path: Path = Path("data/evidence.jsonl")
    database_path: Path = Path("data/fin_terminal.sqlite")
    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = True
    langsmith_workspace_id: str | None = None
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    alpha_vantage_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("alpha_vantage_api_key", "alphavantage_api_key"),
    )
    fred_api_key: SecretStr | None = None
    polygon_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    weaviate_api_key: SecretStr | None = None
    pinecone_api_key: SecretStr | None = None
    vector_backend: Literal["weaviate", "pinecone"] = "weaviate"
    weaviate_collection: str = Field(default="FinancialDocument", pattern=r"^[A-Z][a-zA-Z0-9_]*$")
    pinecone_host: str = ""
    pinecone_namespace: str = "fin-terminal"
    # Bulk-loaded datasets (data/processed) live in their own namespace.
    pinecone_history_namespace: str = "history"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    embedding_backend: Literal["local", "onnx", "openai"] = "local"
    # Local sentence-transformers runtime: "auto" picks CUDA (fp16) when available.
    embedding_device: Literal["auto", "cuda", "cpu"] = "auto"
    embedding_batch_size: int = Field(default=128, ge=1, le=2048)
    embedding_dimensions: int = Field(default=768, ge=8, le=4096)
    # ONNX (CPU) intra-op threads; None = min(8, cpu count). All cores is slower after idle
    # gaps (thread-pool wake-up): measured 129 ms vs 34 ms per item at 8 threads (ADR T17).
    embedding_threads: int | None = Field(default=None, ge=1, le=256)
    # BGE retrieval models expect this prefix on queries only (never on documents).
    embedding_query_instruction: str = "Represent this sentence for searching relevant passages: "
    openai_embedding_model: str = "text-embedding-3-small"
    stub_fail_source: str = ""
    stub_failure_mode: Literal["failed", "degraded", "rate_limited"] = "failed"
    source_rate_per_second: float = Field(default=1.0, gt=0)
    source_burst: int = Field(default=1, ge=1)
    retry_attempts: int = Field(default=3, ge=1)
    retry_max_wait_seconds: float = Field(default=10, gt=0)
    circuit_failure_threshold: int = Field(default=3, ge=1)
    circuit_reset_seconds: float = Field(default=60, gt=0)
    cache_ttl_seconds: float = Field(default=60, gt=0)
    process_budget_ms: float = Field(default=1000, gt=0, le=1000)
    processing_concurrency: int = Field(default=8, ge=1, le=64)
    connector_policies: dict[str, ConnectorPolicy] = Field(default_factory=dict)
    fast_poll_seconds: float = Field(default=1, gt=0)
    media_refresh_seconds: float = Field(default=10800, gt=0)
    scheduler_jitter_seconds: float = Field(default=30, ge=0)
    freshness_seconds: float = Field(default=60, gt=0)
    stream_queue_size: int = Field(default=2, ge=1, le=1000)
    ingestion_batch_size: int = Field(default=32, ge=1, le=1000)
    fast_queue_policy: Literal["latest", "block"] = "latest"
    slow_processing_concurrency: int = Field(default=2, ge=1, le=16)
    dead_letter_path: Path = Path("data/dead_letters.jsonl")
    parser_max_bytes: int = Field(default=8_000_000, ge=1024)
    language_hint: str | None = None

    def connector_policy(self, provider: str) -> ConnectorPolicy:
        return self.connector_policies.get(provider) or ConnectorPolicy(
            timeout_seconds=self.http_timeout_seconds,
            rate_per_second=self.source_rate_per_second,
            burst=self.source_burst,
            concurrency=2,
            retries=self.retry_attempts,
        )


def secret_value(value: SecretStr | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        return value.get_secret_value() if value.get_secret_value() else None
    return str(value) if str(value) else None
