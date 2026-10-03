"""Environment-only configuration; retain the existing provider settings."""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, SecretStr

from stop_loss.config import Settings as LegacySettings


class ConnectorPolicy(BaseModel):
    timeout_seconds: float = Field(default=15, gt=0)
    rate_per_second: float = Field(default=1, gt=0)
    burst: int = Field(default=1, ge=1)
    concurrency: int = Field(default=2, ge=1, le=32)
    retries: int = Field(default=3, ge=1, le=10)


class Settings(LegacySettings):
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
    embedding_backend: Literal["local", "openai"] = "local"
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
