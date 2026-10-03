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
- **Context**: External financial APIs (e.g. Alpha Vantage, FRED) impose plan-specific rate limits. Verify the account's current quota when implementing each connector.
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
- **Decision**: Default to a lightweight local embedding model (`BAAI/bge-small-en-v1.5`, 384 dimensions) running on CPU. Provide an environment switch (`EMBEDDING_BACKEND=openai`) for OpenAI embeddings.
- **Consequences**: Eliminates per-item external latency and API cost during streaming ingestion.

---

## ADR 008: Alpha Vantage as Primary Market Provider
- **Context**: Alpha Vantage is designated as the primary market provider in the contract; Polygon is optional.
- **Decision**: Implement `AlphaVantageProvider` for equity quotes, time series, and market news sentiment. Provide `PolygonProvider` as an optional plugin controlled by `ENABLE_POLYGON=false`.
- **Consequences**: Maximizes availability and free-tier compatibility while preserving extensibility for enterprise polygon feeds.

---

## ADR 009: Repository Inventory and Compatibility (2026-10-03)
- **Observed**: The repository already contains a uv/Hatch Python project under `backend`, the `stop_loss` package, Pydantic configuration/domain models and errors, synchronous `DataProvider` and repository interfaces, a sequential ingestion runner, provider skeletons, a CLI, 22 unit tests, documentation, a Makefile, and `.env.example`. SQLite methods and source implementations remain `NotImplementedError` stubs. Frontend, agent, analytics, API, and retrieval directories are placeholders.
- **Alpha Vantage inspection**: Searches of tracked code and docs found `ALPHA_VANTAGE_API_KEY`, provider-name examples in tests/models, and ADR 008. There is no implemented Alpha Vantage client, HTTP integration, or recorded provider fixture in this checkout. `ingestion/providers/market.py` contains a Yahoo Finance stub. ADR 008 describes an intended implementation, not an existing one. No integration was removed or replaced.
- **Decision**: Preserve the `stop_loss` package and CLI. Add `backend/src/fin_terminal` alongside it and package both using Hatch. Extend existing settings to preserve provider environment keys. Real Alpha Vantage integration remains a future `AsyncConnector` implementation; if supplied separately, wrap that client instead of rewriting it. Do not treat an externally connected Alpha Vantage app as repository source code.
- **Consequences**: Existing tests/API imports continue to work. Legacy orchestration stays available for compatibility; all new pipeline orchestration uses LangGraph. New schemas use uppercase theme values without changing the legacy lowercase enum contract.

## ADR 010: Empty Sources and Explicit Failure Injection
- **Decision**: All six fetch branches return empty lists by default. A successful stub is `ok` with an explicit stub health message. Inject failure by source and mode through env/CLI. Do not invent market observations to populate smoke output. Normalization/indexing are exercised with clearly labelled offline test fixtures and injected test adapters.
- **Consequences**: End-to-end smoke needs neither data-provider credentials nor vector services/model downloads. Live source fixtures must be recorded and sanitized during connector implementation.

## ADR 011: SQLite Graph Execution, Dedupe, and Audit Boundary
- **Decision**: Use a typed LangGraph state with reducer-based fan-out merges and a list-valued join edge. Support `SqliteSaver`/`graph.invoke` and `AsyncSqliteSaver`/`graph.ainvoke`; the CLI uses the async form because connectors are async. Each cycle gets its own thread/run identity. Keep checkpoint state JSON-compatible. Use SQLite WAL for checkpoints and canonical records, plus an append-only JSONL evidence log.
- **Decision**: Dedupe against committed content hashes, but commit only after successful vector upsert. Derive vector IDs from the same hash, making retries safe after a partial write. Vector stores contain projections referencing canonical SQLite records. Support one local ingestion writer; a distributed transaction or concurrent-process coordination is outside this skeleton.
- **Consequences**: Source errors degrade individual streams; cancellation remains effective. Local persistence/evidence failures are fatal and visible because continuing would break auditability. The CLI does not automatically resume an old cycle; checkpoints remain inspectable by ingest ID.

## ADR 012: Honest Latency and Observability Validation
- **Decision**: Measure fetch and processing separately, include normalization and queueing in processing time, and apply the remaining subsecond deadline to embed/index work. Record overruns as degraded; never claim the real-provider latency invariant has been benchmarked using empty stubs. Keep model packages optional/lazy. TTL cache is a reusable connector primitive, not a fabricated-data fallback.
- **Decision**: Every invocation receives a trace name, source/theme tags and ingest ID metadata. Enable tracing through configured LangSmith environment values. Smoke flushes traces and reads back completed root runs when enabled; missing key/disabled tracing produces an explicit skip. Unit tests are offline with mock trace verification.
- **Consequences**: Smoke establishes graph execution and failure isolation. Production throughput, real cloud adapters, model warm-up, and remote trace delivery require separate live integration validation. See [ingestion operations](ingestion.md) for commands, limitations, and API references.
