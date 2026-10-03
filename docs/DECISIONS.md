# Architectural Decision Records (ADRs)

This document records key design choices, resolutions to ambiguous requirements, and standing architectural decisions for StopLoss Intelligence.

---

## ADR 001: First-Class Macro Theme Tagging
- **Context**: Ingested records must be contextualized for downstream financial risk and hedging agents.
- **Decision**: Define a canonical `MacroTheme` enum (`TARIFF`, `BANK_TAX`, `WAR_CRISIS`, `WEATHER_EXTREME`). Every `NormalizedRecord` includes `theme_tags: list[MacroTheme]`. Keyword and rule-based heuristics tag records at ingestion time without requiring expensive LLM calls during streaming.
- **Consequences**: Fast, deterministic filtering for downstream retrieval and multi-agent routing.

---

## ADR 002: Deterministic Content Hashing for Idempotency
- **Context**: Repeated polling or streaming cycles must never create duplicate records or skew analytical models.
- **Decision**: Calculate a deterministic SHA-256 `content_hash` across canonical normalized attributes (`provider`, `data_type`, `observed_at`, `indicator`, `ticker`/`entity`, `numeric_value`/`text_value`). The storage repository enforces unique constraints on `content_hash`.
- **Consequences**: Guarantees zero duplicate entries across multiple ingestion runs.

---

## ADR 003: Strict Zero-Imputation & Data Quality Auditing
- **Context**: LLMs and automated risk engines fail silently when financial metrics are synthetic or imputed without notice.
- **Decision**: Implement a strict "Never Fabricate" invariant. Missing data remains `None` (`null`), accompanied by a required `data_quality` status (`good`, `missing_fields`, `degraded`, `suspect`).
- **Consequences**: Downstream risk agents can verify data fidelity and exclude degraded metrics from mathematical calculations (e.g. VaR).

---

## ADR 004: Dual-Stage Latency Telemetry
- **Context**: The streaming ingestion SLA requires per-item process, embed, and index under 1.0 second.
- **Decision**: Instrument and record two distinct timing metrics on every record:
  1. `fetch_latency_ms`: Duration of the external HTTP request.
  2. `process_latency_ms`: Duration to parse, normalize, tag themes, embed, and persist.
- **Consequences**: Direct visibility into network bottlenecks versus local processing bottlenecks.

---

## ADR 005: Token-Bucket Rate Limiter with Jitter
- **Context**: External financial APIs (e.g. Alpha Vantage, FRED) impose strict rate limits (e.g. 5 calls/min, 25 calls/day on free tiers).
- **Decision**: Combine a client-side in-memory token bucket rate limiter with `tenacity` retry decorators implementing exponential backoff and randomized jitter.
- **Consequences**: Prevents HTTP 429 penalties while gracefully recovering from temporary rate limit spikes.

---

## ADR 006: VectorStoreAdapter Pattern
- **Context**: The terminal requires vector indexing with flexible infrastructure support (local self-hosted Docker for development, Pinecone for managed cloud).
- **Decision**: Decouple the vector store behind a `VectorStoreAdapter` abstract base class. Provide implementations for:
  - `WeaviateVectorAdapter` (local Docker container)
  - `PineconeVectorAdapter` (cloud managed)
  Selected dynamically via the `VECTOR_BACKEND` environment variable.
- **Consequences**: Seamless switching between offline local development and cloud deployments with zero codebase changes.

---

## ADR 007: Local Sentence-Transformers Default Embeddings
- **Context**: Sub-second per-item latency SLA cannot rely on external network calls to embedding APIs for high-volume news streaming.
- **Decision**: Default to a lightweight local embedding model (`BAAI/bge-small-en-v1.5`, 384 dimensions) running on CPU. Provide an environment switch (`EMBEDDINGS_BACKEND=openai`) for high-fidelity offline batch processing.
- **Consequences**: Eliminates per-item external latency and API cost during streaming ingestion.

---

## ADR 008: Alpha Vantage as Primary Market Provider
- **Context**: Alpha Vantage is designated as the primary market provider in the contract; Polygon is optional.
- **Decision**: Implement `AlphaVantageProvider` for equity quotes, time series, and market news sentiment. Provide `PolygonProvider` as an optional plugin controlled by `ENABLE_POLYGON=false`.
- **Consequences**: Maximizes availability and free-tier compatibility while preserving extensibility for enterprise polygon feeds.
