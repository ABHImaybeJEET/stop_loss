# PS5: Multi-Agent Financial Intelligence Terminal — Standing Contract

This document is the **standing architectural and operational contract** for the StopLoss Multi-Agent Financial Intelligence Terminal. All contributors and AI agents must review and adhere to these specifications across all tasks.

---

## 1. Project Goal
An AI financial intelligence terminal that continuously ingests global news, macroeconomic indicators, weather extremes, and market price series, indexes them in a vector database, and feeds a LangGraph multi-agent portfolio engine:
- **Sentiment Agent**: News & geopolitical event extraction and tone modeling.
- **Weather & Macro Impact Agent**: Facility disruption and macro shock propagation.
- **Quant Risk Agent**: Value-at-Risk (VaR), sensitivity matrices, and stress scenario drawdowns.
- **Hedging Strategy Agent**: Evidence-backed portfolio protection (collars, index puts, futures).

Operating behind a modern terminal UI (Streamlit / Next.js).
**Current Phase**: DATA INGESTION PIPELINE (modularly decoupled so later agents plug in with zero refactoring).

---

## 2. Chosen Macro Themes (First-Class Tags)
Every ingested record MUST be tagged with zero or more of these first-class macro themes:
1. `TARIFF`: Trade tariffs, duties, export controls, trade-war escalation, cross-border supply chain friction.
2. `BANK_TAX`: Bank levies, windfall taxes on financials, capital/reserve requirement changes, interest-rate policy shocks.
3. `WAR_CRISIS`: Armed conflict, sanctions, geopolitical crises, shipping/chokepoint disruptions, energy supply shocks.
4. `WEATHER_EXTREME`: Hurricane tracks, severe winter freezes, flood levels, coastal refinery threats.

---

## 3. Fixed Technology Stack

| Category | Technology |
|---|---|
| **Language & Base** | Python 3.11+, Pydantic v2, `httpx` (async), `tenacity`, `pytest`, `python-dotenv`, `ruff` |
| **Orchestration** | LangGraph for ALL orchestration (`StateGraph`, checkpointers) |
| **Agent Tooling** | LangChain (`langchain-core`, `langchain-community`, text splitters, embeddings wrappers) |
| **Observability** | LangSmith tracing on every graph run (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`) |
| **Vector DB** | Behind `VectorStoreAdapter` interface; supporting Weaviate (local Docker) AND Pinecone (`VECTOR_BACKEND`) |
| **Market Data** | Alpha Vantage (primary market provider in repo); Polygon.io optional behind feature flag |
| **Embeddings** | Local `sentence-transformers` (e.g. `BAAI/bge-small-en-v1.5`) default for <1s latency; OpenAI embeddings via env switch |
| **Persistence** | SQLite with WAL mode for local relational storage; Vector DB for dense semantic search |

---

## 4. Non-Negotiable Ingestion Requirements

1. **Multi-Modal Data Streams**:
   - News intelligence (GDELT, RSS, Alpha Vantage News).
   - Macro indicators (FRED: Oil WTI, CPI, Fed Funds, yield curves).
   - Weather telemetry (Open-Meteo marine & atmospheric forecasts).
   - Market price series (Alpha Vantage / Yahoo Finance / optional Polygon).

2. **Latency Invariant**:
   - Per-item process + embed + index must complete in **under 1.0 second** in streaming mode.
   - Separate telemetry: Measure and log `fetch_latency_ms` and `process_latency_ms` individually on every record.

3. **Robustness & Fault Tolerance**:
   - Rate limiting: Token-bucket algorithm combined with exponential backoff with jitter (`tenacity`).
   - Missing/failing streams: Graceful degradation, record stream health status, NEVER crash the ingestion engine.
   - Zero fabrication rule: **NEVER fabricate or impute financial metrics**. Missing values = `null` (`None`) accompanied by an explicit `data_quality` flag (`good`, `missing_fields`, `degraded`, `suspect`).

4. **Auditability & Provenance**:
   - Every stored record must record complete lineage:
     - `source` & `provider`
     - `source_url`
     - `published_at` & `observed_at`
     - `fetched_at`
     - `ingest_run_id`
     - `content_hash` (deterministic SHA-256 for deduplication)
     - `theme_tags` (`TARIFF`, `BANK_TAX`, `WAR_CRISIS`, etc.)
     - `langsmith_run_id` (when available)
   - Every graph node and pipeline stage writes to an append-only evidence log.

5. **Idempotency**:
   - Deduplication enforced by `content_hash`. Repeated ingestion cycles must never duplicate stored records.

6. **Offline Testability**:
   - Every external source must have recorded JSON fixtures under `backend/tests/fixtures/` so the full test suite runs reliably offline.

---

## 5. Code & Architectural Rules
- Strict typing throughout with Pydantic v2.
- Small, focused, single-responsibility modules.
- Zero secrets committed to version control; maintain `.env.example`.
- Each task deliverable must include unit tests and documentation updates.
- If a requirement is ambiguous: pick the simplest viable option, document it in `docs/DECISIONS.md`, and continue.
