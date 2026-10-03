# StopLoss Intelligence: Project Roadmap

This roadmap structures the delivery of StopLoss Intelligence into seven incremental, testable checkpoints designed for a four-developer hackathon sprint.

---

## Checkpoint 0: Foundation and Contracts (Current)
- **Goal**: Establish typed contracts, project layout, configuration, CLI foundation, and team conventions.
- **Deliverables**:
  - `pyproject.toml` with `uv` tooling, Ruff linting, and Pytest.
  - Typed domain models (`NormalizedRecord`, `IngestionRun`) and enums (`DataType`, `RunStatus`, `ProviderErrorType`).
  - Abstract contracts: `DataProvider`, `RecordRepository`.
  - Settings management using `pydantic-settings`.
  - Placeholder CLI: `stop-loss --help`, `ingest`, `status`, `records`.
  - Architecture, data contracts, and roadmap documentation.

---

## Checkpoint 1: Live Data Ingestion and SQLite Persistence
- **Goal**: Connect live data providers and persist normalized records into local SQLite database.
- **Deliverables**:
  - `OpenMeteoProvider`: Ingest hurricane coordinates, wind speeds, atmospheric pressure, and marine conditions.
  - `GDELTProvider`: Ingest real-time geopolitical, commodity disruption, and severe weather news.
  - `YahooFinanceProvider`: Ingest equity prices (`XLE`, `XOM`, `CVX`) and futures (`NG=F`).
  - `FREDProvider`: Ingest crude oil benchmark (`DCOILWTICO`), CPI (`CPIAUCSL`), and Federal Funds Rate (`FEDFUNDS`).
  - `SQLiteRecordRepository`: Implement SQLite schema, WAL mode, composite indexes, and bulk upsert operations.
  - Independent provider error handling and failure isolation.
  - One-shot CLI ingestion command (`python -m stop_loss ingest`).

---

## Checkpoint 2: Historical Retrieval and Optional Vector Index
- **Goal**: Provide fast relational querying and semantic event analog search.
- **Deliverables**:
  - Relational querying across time windows, tickers, and data types.
  - Hybrid search: BM25 text search + optional dense embeddings for news and market notes.
  - Historical event catalog: Curate Gulf hurricane scenarios (e.g. Katrina, Harvey, Ida) and energy freeze events.
  - Event analog matching engine finding past periods with similar composite risk vectors.

---

## Checkpoint 3: Portfolio and Quantitative Risk Engine
- **Goal**: Model asset correlations, portfolio exposures, and calculate quantitative risk metrics.
- **Deliverables**:
  - Portfolio definition model (holdings, weights, sector breakdown).
  - Value at Risk (VaR) and Conditional VaR (CVaR) parametric and historical simulation engine.
  - Macro and physical asset sensitivity matrix (beta to oil price spikes, refinery shut-in elasticity).
  - Tactical hedging calculator (options collars, index put hedges, futures spread ratios).

---

## Checkpoint 4: Multi-Agent Orchestration
- **Goal**: Build collaborative multi-agent decision workflow using LangGraph.
- **Deliverables**:
  - Agent state graph and routing logic via `Query Coordinator`.
  - Domain specialists: `News Sentiment Agent`, `Weather Impact Agent`, `Macro Analysis Agent`, `Quantitative Risk Agent`.
  - Synthesis agents: `Historical Event Retrieval Agent`, `Hedging Strategy Agent`.
  - Validation: `Evidence and Audit Agent` ensuring all claims cite concrete normalized records.

---

## Checkpoint 5: API and Interactive Terminal
- **Goal**: Expose backend services via FastAPI and launch interactive Next.js terminal.
- **Deliverables**:
  - FastAPI REST endpoints for portfolio submission, query execution, and historical data.
  - WebSocket / SSE streaming for agent reasoning traces and live market/weather telemetry.
  - Next.js dashboard with geospatial hurricane tracking map, financial charts, and hedging recommendation cards.

---

## Checkpoint 6: Evaluation, Resilience, and Final Demo
- **Goal**: End-to-end testing, resilience benchmarking, and hackathon presentation polish.
- **Deliverables**:
  - Benchmark evaluation suite testing agent accuracy against verified historical market outcomes.
  - Synthetic disaster playback / demo scenario (Gulf of Mexico Category 4 hurricane heading towards coastal refineries).
  - Comprehensive documentation, demo video, and production deployment packaging.
