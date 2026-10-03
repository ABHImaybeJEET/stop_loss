

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

## ADR 013: Bounded Processing and Direct LangGraph Execution
- **Context**: Sequential normalization and indexing let one slow operation consume the deadline for otherwise healthy records. Unbounded parallel embedding would instead risk excessive CPU and memory use.
- **Decision**: Keep the existing LangGraph `StateGraph` and SQLite checkpoint topology. Normalize the six sources concurrently inside the normalization node. Embed/index using a bounded worker pool (`PROCESSING_CONCURRENCY=8`, range 1–64), preserving result order and accounting for queue delay. Expired records never start vector writes. Task groups cancel sibling workers on fatal failures; per-record operational failures remain isolated and retryable.
- **Decision**: Serialize first model initialization and Weaviate collection initialization to prevent races introduced by concurrent records. Default tracing to enabled when a key exists, support `LANGSMITH_WORKSPACE_ID`, and attach source metadata to fetch spans and execution mode to root traces. Store credentials only in ignored local environment files.
- **Validation boundary**: Concurrency, deadline isolation, dedupe, and setup races are covered by offline tests. Empty-stub smoke verifies graph execution and remote trace delivery when credentials/network are available. No live provider or real-model throughput SLA is claimed. Large batches need workload-specific tuning and model warm-up before production rollout.

---

## ADR 014: Unblocked Per-Stream Processing Lanes (Elimination of Join Barrier)
- **Context**: In ADR 013, all six data sources fanned into a central `normalize` node. In LangGraph's Pregel Bulk Synchronous Parallel execution model, supersteps act as barriers: a single slow external fetch (e.g. macro indicator HTTP delay) forced all other streams to wait before beginning normalization, deduping, theme tagging, embedding, and vectorstore indexing. This risked SLA breaches on healthy, low-latency streams (such as real-time market prices or breaking news).
- **Decision**: Restructure the ingestion graph into independent, unblocked stream processing lanes (`stream_{source}` for each of the six sources). Each stream lane immediately fetches, normalizes, dedupes, tags, embeds, and indexes its own records asynchronously without waiting for sibling streams to complete. State updates are merged across parallel lanes using LangGraph reducers (`merge_maps`, `merge_lists`, `merge_ints`).
- **Join Boundary**: Synchronization occurs only at the final `write_evidence` and `report` nodes once all stream lanes have concluded their lifecycle.
---

## ADR 015: Real Multi-Modal Async Connectors with Offline Fixtures
- **Context**: The terminal contract requires ingesting real-time market prices, macroeconomic indicators, weather extremes, and multi-theme news feeds through specialized financial APIs, while strictly maintaining offline testability, zero metric fabrication, and credential safety.
- **Decision**: Implement four production-grade `AsyncConnector` implementations under `backend/src/fin_terminal/connectors/`:
  1. `AlphaVantageMarketConnector`: Real equity/ETF quotes via `GLOBAL_QUOTE` (symbol, price, volume, trading day).
  2. `AlphaVantageNewsConnector`: Real news intelligence via `NEWS_SENTIMENT` mapped to the three macro themes (`TARIFF`, `BANK_TAX`, `WAR_CRISIS`).
  3. `FredMacroConnector`: Real Federal Reserve Economic Data via `series/observations` (`DCOILWTICO`, `CPIAUCSL`, `FEDFUNDS`, `T10Y2Y`). Missing holiday observations (`.`) map strictly to `None` with `data_quality="missing_fields"`.
  4. `OpenMeteoWeatherConnector`: High-resolution weather telemetry (`temperature_2m`, `wind_speed_10m`, `precipitation`) for facility risk demonstration without requiring API keys.
- **Offline Invariant**: Recorded JSON responses are stored under `backend/tests/fixtures/` and verified with unit tests (`test_connectors.py`), guaranteeing that tests and CI run 100% offline without live internet access or external credentials.
- **Execution Mode**: Live connectors are activated via `--live` or explicit configuration, with automatic fallback to safe `StubConnector` instances during smoke tests and offline test suites.



---

# Analysis Terminal (Checkpoints 3–5): ADR T01–T10

## ADR T01: Scope: Real Data End-to-End, Ingestion Untouched (2026-10-03)
- **Context**: The `/chat` terminal brief assumed a finished backend, but the repository only contained the ingestion pipeline (`stop_loss/agents`, `api`, `analytics` were README stubs). The owner directed that nothing be mocked and that the necessary backend pieces be added.
- **Decision**: Add `stop_loss/analytics` (providers + quant), `stop_loss/agents` (LangGraph engine) and `stop_loss/api` (FastAPI) on top of the existing `fin_terminal` modules, reusing its settings, `SourceGuard` resilience, FRED connector, schemas and evidence log. `fin_terminal` ingestion code is unchanged. The brief's `NEXT_PUBLIC_USE_MOCK` mock stream was intentionally **not** built.

## ADR T02: Yahoo Finance via httpx; Alpha Vantage for Sentiment Only
- **Context**: `yfinance` requires pandas, whose compiled DLLs are blocked by Windows Application Control on the dev machine. Alpha Vantage's free tier allows ~25 calls/day.
- **Decision**: Call the same public Yahoo endpoints yfinance wraps (`v8/finance/chart`, `v1/finance/search`, `v10/finance/quoteSummary` with cookie+crumb) through `GuardedHTTP` (token bucket, tenacity backoff, circuit breaker, TTL cache). Use Alpha Vantage `NEWS_SENTIMENT` only for US tickers (cached 30 min) and Google News RSS for broad headline coverage. When the market is closed, the 1D chart falls back to the last trading session.

## ADR T03: Agent Topology and Streaming Protocol
- **Decision**: `coordinator → {market, news, macro, weather} → quant → hedging → audit`. Nodes emit `agent_update` / `section` / `final` / `reply` / `error` events through LangGraph's custom stream (`get_stream_writer`). Each agent isolates its own failure; the run yields a partial result with `failed_agents`.
- **Transport**: SSE with a monotonically increasing `seq`. Runs execute detached from the HTTP connection and buffer events (`RunRegistry`), so clients resume with `?after=<seq>`, re-attach after reload, or cancel explicitly. One active run per thread (409 otherwise).
- **Gotcha**: `run_id` is reserved in LangGraph checkpoint metadata; putting it in `config.metadata` made follow-up runs on a thread silently no-op. We use `stoploss_run_id`.
- **Memory**: `AsyncSqliteSaver` keyed `"{uid}:{thread_id}"`; per-run keys are reset on every input.

## ADR T04: OpenAI for Reasoning, Deterministic Fallback
- **Decision**: `langchain-openai` `ChatOpenAI` (`OPENAI_CHAT_MODEL`, default `gpt-4.1-mini`) with structured outputs for routing (analysis vs follow-up reply), headline sentiment, and narrative/suggestions. Without `OPENAI_API_KEY`, or if a call fails, routing is heuristic and the narrative is assembled from evidence-catalog entries only (`narrative_source: "rules"`, shown in the UI).

## ADR T05: Weather Exposure and Extreme Thresholds
- **Decision**: Forecast the company HQ (Yahoo profile city → Open-Meteo geocoding) plus the configured Gulf Coast hub for Energy-sector assets. Assets with no known facility report `not_applicable`. Extremes: gusts ≥ 90 km/h, rain ≥ 64.5 mm/day (IMD "heavy"), Tmax ≥ 40 °C, Tmin ≤ −15 °C, WMO codes 95/96/99.

## ADR T06: Risk and Trust Scores
- **Risk (0–100)**: weighted mean of available components: 1Y volatility (60% ann. = 100, w .25), 1Y max drawdown (−50% = 100, w .20), 1-day 95% historical VaR (5% = 100, w .20), |beta| (2.0 = 100, w .10), net headline sentiment (w .15), event exposure (20 per theme/weather/macro flag, w .10). It requires at least one price-based component; otherwise it is `null`. Bands: <25 Low, <50 Moderate, <75 High, else Severe.
- **Trust (0–100)**: equal-weight mean of data coverage, freshness, source depth, sentiment/momentum agreement and the figure audit, with human-readable reasons.

## ADR T07: Evidence Catalog and Figure Audit
- **Decision**: Every citable figure gets an id (`E1…`) with source, URL and timestamp. Narratives must cite ids. The audit agent extracts every figure from generated text and matches it against evidence values (rounding tolerant). Unmatched figures are listed in the result, lower trust, and are flagged in the UI. The rules fallback passes the audit by construction (tested).

## ADR T08: Frontend Contract Extensions
- **Decision**: The normalized types in `frontend/lib/chat/types.ts` follow the brief, with these additions: `snapshot.facts` is an ordered list (stable display order); `riskScore`/`trustScore` are nullable (no fabricated numbers); `sources.items[].themes/sentimentSource`; `historical.metrics/seasonality`; `suggestions.items[].evidenceIds`; `evidence` and `audit` on the result; extra stream events `reply` (text follow-ups), `cancelled`, and `seq` on every event. `adapters/backendToUi.ts` is the only place that knows the snake_case wire format.

## ADR T09: Threads, Auth and Proxying
- **Decision**: The backend owns agent memory. The UI persists the message list in Firestore at `users/{uid}/threads/{threadId}/messages/{messageId}` with a localStorage cache, and `?thread=` restores it after refresh. Next.js route handlers verify the Firebase ID token (`jose`, Google securetoken JWKS) and forward `X-User-Id`, plus optional `X-Internal-Token`, to the backend, which must only listen on localhost or a private network.

## ADR T10: `frontend/lib` Was Silently Untracked
- **Context**: The root `.gitignore` rule `lib/` (Python build output) also matched `frontend/lib/`, so `firebase.ts`, `userProfile.ts` and `news.ts` were never committed and every page failed to build from a clean clone.
- **Decision**: Re-include `frontend/lib/` and recreate the modules from their call sites. The landing news feed now reads only from the backend's `/news/feed`; the static fallback dataset was removed.
