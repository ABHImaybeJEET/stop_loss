# StopLoss Intelligence Terminal

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Checked with Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/managed%20by-uv-blueviolet)](https://github.com/astral-sh/uv)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-purple.svg)](https://github.com/langchain-ai/langgraph)

**StopLoss Intelligence** is a multi-agent financial intelligence terminal and automated risk analysis platform. It synthesizes real-time environmental threats (hurricanes, severe freezes), geopolitical and trade shock news, live market series, and macroeconomic indicators to generate evidence-backed hedging recommendations for equity assets and portfolios.

Every recommendation is grounded in primary ingested data and historical crisis analogs—validated by an automated audit agent with citation-level provenance to eliminate hallucination.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Ingestion ["Data Ingestion Engine (fin_terminal & stop_loss.retrieval)"]
        M[Market Data: Yahoo / NSE]
        N[News Feeds: GDELT / Google RSS / Yahoo]
        W[Weather Telemetry: Open-Meteo / GDACS / USGS]
        E[Macro Indicators: FRED]
        
        M & N & W & E --> Lane[Per-Source Ingestion Lanes & Resilience Guards]
        Lane --> Norm[Normalized Records & SHA-256 Content Hash]
        Lane --> Tag[Macro Theme Tagger: TARIFF, BANK_TAX, WAR_CRISIS, WEATHER_EXTREME]
        Lane --> VStore[Dense Vector Embedding & Indexing: Pinecone / Weaviate]
        Lane --> ELog[(Append-Only Evidence Log & SQLite WAL)]
    end

    subgraph Reasoning ["Multi-Agent Deliberative Graph (stop_loss.agents)"]
        Coord[Query Coordinator]
        
        subgraph ParallelAgents ["Parallel Intelligence Extraction"]
            MarketA[Market Intelligence Agent]
            NewsA[News Sentiment Agent]
            ImpactA[Weather & Macro Impact Agent]
            AnalogA[Historical Analogs Agent]
        end
        
        QuantA[Quantitative Risk Agent: VaR / CVaR / Beta / Correlations]
        HedgeA[Hedging Strategy Agent: Options, Collars & Index Puts]
        AuditA[Evidence & Audit Agent: Grounding & [E#] Citations]

        Coord --> ParallelAgents
        ParallelAgents --> QuantA
        QuantA --> HedgeA
        HedgeA --> AuditA
    end

    subgraph Interface ["FastAPI Service & Next.js Terminal Cockpit"]
        API[FastAPI Backend: Typed SSE Events & SQLite Replay]
        UI[Next.js 14 Terminal: Live Orchestration, Charts, Risk & Trust, Portfolio Cockpit]
        
        AuditA --> API
        API -->|Server-Sent Events| UI
    end
```

---

## Key Capabilities

### 1. Multi-Stream Ingestion & Resilient Lineage
- **Decoupled Ingestion Lanes**: Independent `stream_{source}` lanes running fetch, normalization, deduplication, theme tagging, embedding, and indexing without lockstep bottlenecks.
- **First-Class Macro Themes**: Every record is tagged with deterministic themes:
  - `TARIFF`: Tariffs, trade disputes, export curbs, cross-border supply chain friction.
  - `BANK_TAX`: Levies on financials, capital/reserve requirement changes, rate shocks.
  - `WAR_CRISIS`: Armed conflicts, sanctions, geopolitical crises, maritime chokepoints.
  - `WEATHER_EXTREME`: Hurricanes, freezes, floods, coastal facility and refinery threats.
- **Zero Fabrication Guarantee**: Strict data provenance; missing metrics are retained as `None` with explicit quality flags (`good`, `missing_fields`, `degraded`, `suspect`).
- **Telemetry & Low Latency**: Continuous per-item tracking for `fetch_latency_ms` and `process_latency_ms` with automated latency profiling (`make latency`).

### 2. Multi-Agent LangGraph Reasoning Engine
Orchestrated through LangGraph (`START → coordinator → {market, news, impact, analogs} → quant → hedging → audit → END`):
- **Query Coordinator**: Resolves user queries, detects single-asset or portfolio context, and directs the analysis flow.
- **Market Intelligence Agent**: Analyzes recent price momentum, 52-week ranges, volume dynamics, and key technical indicators.
- **News Sentiment Agent**: Evaluates press releases, news feeds, and geopolitical events for disruption alerts and supply bottlenecks.
- **Weather & Macro Impact Agent**: Evaluates operational risks from meteorological threats (marine storms, severe freezes) and macro indicators (CPI, interest rates, crude shocks).
- **Historical Analogs Agent**: Retrieves comparable past crises (e.g., deep winter freezes, geopolitical supply disruptions) from the crisis catalog and calculates empirical price-impact bounds (min, median, max returns).
- **Quantitative Risk Agent**: Computes historical Value-at-Risk (VaR 95/99), Expected Shortfall (CVaR), volatility, drawdowns, beta, and cross-asset correlations against Brent crude, USD/INR, NIFTY 50, and India VIX.
- **Hedging Strategy Agent**: Formulates asset-specific or portfolio-level hedging structures (protective puts, collars, futures/index hedges) with concrete rationale.
- **Evidence & Audit Agent**: Verifies every quantitative claim against primary evidence records, outputs clickable `[E#]` citation chips, and calculates transparent Risk & Trust scores.

### 3. Single-Asset & Portfolio-Wide Analysis
- **Single-Ticker Mode**: Deep-dive analysis for any supported equity (NSE securities `.NS` and global assets).
- **Portfolio Mode**: Analyzes an entire portfolio of holdings simultaneously, aggregating asset-specific impacts, sector exposures, and cross-asset risk concentrations.

### 4. Interactive Terminal UI (Next.js 14)
- **Live Orchestration Panel**: Real-time visualizer streaming agent execution states (`queued` → `running` → `done`/`error`), step details, and execution timers.
- **Progressive Results**: Progressive section rendering: Asset Snapshot, Real-Time Sources, Historical Analogs, Interactive Recharts Price Series, Suggestions & Hedging Tickets, and Risk & Trust Audit.
- **Full Traceability**: Interactive `[E#]` evidence drawer showing exact sources, timestamps, and primary content.
- **Session Persistence**: Thread history saved with Firebase Auth / local fallback; backend run replay via SQLite.

---

## Repository Layout

The repository is structured as a modular monorepo:

```text
stop_loss/
├── backend/
│   ├── pyproject.toml              # Build config, dependencies, CLI entrypoints
│   ├── src/
│   │   ├── fin_terminal/           # Canonical ingestion package
│   │   │   ├── ingestion/          # LangGraph ingestion graph & connectors
│   │   │   ├── resilience.py       # Rate limiting, circuit breakers & backoff
│   │   │   ├── schemas.py          # Strict Pydantic ingestion models
│   │   │   ├── vectorstore/        # Vector store adapters (Pinecone / Weaviate)
│   │   │   └── evidence.py         # Append-only evidence logger
│   │   │
│   │   └── stop_loss/              # Canonical product package
│   │       ├── agents/             # LangGraph multi-agent system & prompt nodes
│   │       │   ├── graph.py        # Single-asset and portfolio analysis graphs
│   │       │   ├── nodes.py        # Standard agent node implementations
│   │       │   ├── portfolio_nodes.py # Portfolio-mode agent nodes
│   │       │   ├── run_events.py   # Typed SSE lifecycle event models
│   │       │   └── service.py      # Execution service with SQLite WAL checkpointer
│   │       ├── analytics/          # Quant risk math, analogs, cross-asset correlations
│   │       ├── retrieval/          # Live ingestion loop, analog catalog & vector retriever
│   │       ├── storage/            # Relational SQLite repositories
│   │       └── api/                # FastAPI service (SSE runs, chat, market, portfolio)
│   │
│   └── tests/                      # Pytest suite with offline fixtures
│       ├── fin_terminal/           # Ingestion pipeline tests
│       ├── terminal/               # Agent, analytics, and API integration tests
│       └── fixtures/               # Recorded offline JSON payloads
│
├── frontend/                       # Next.js 14 App Router Terminal UI
│   ├── app/                        # App Router pages (/chat, /dashboard, /login, api proxies)
│   ├── components/                 # React components (chat, portfolio, orchestration, charts)
│   ├── lib/                        # SSE stream hooks, client state reducers, Firebase auth
│   └── package.json
│
├── data/                           # Ingestion raw datasets and processed reference catalogs
├── docs/                           # Architectural Decision Records (ADRs) and reports
│   ├── CODEMAP.md                  # Quick navigation map across the codebase
│   ├── DECISIONS.md                # Architectural Decision Records (ADR log)
│   ├── data-contract.md            # Normalized data schema specifications
│   ├── latency_report.md           # Live ingestion latency telemetry benchmarks
│   └── progress.md                 # Checkpoint delivery milestones
│
├── AGENTS.md                       # Standing architectural and operational contract
├── Makefile                        # Unified developer automation commands
└── status.txt                      # Current development task tracking
```

---

## Getting Started

### Prerequisites
- **Python 3.11+**
- **[`uv`](https://github.com/astral-sh/uv)** (fast Python package and project manager)
- **Node.js 18+** & **npm** (for the frontend terminal)
- *(Optional)* Pinecone API key or local Weaviate Docker container for dense semantic search.
- *(Optional)* Groq or OpenAI API key for LLM narrative generation. Without keys, agents operate in deterministic, rules-based mode using primary evidence.

---

### Backend Setup

1. **Install backend dependencies:**
   ```bash
   cd backend
   uv sync --extra onnx-embeddings
   ```

2. **Configure environment:**
   Copy the sample environment file from the repository root:
   ```bash
   cp ../.env.example ../.env
   ```
   Configure your keys in `.env` (e.g. `GROQ_API_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY`).

3. **Start the FastAPI backend service:**
   ```bash
   uv run stop-loss-api
   ```
   The backend API will be available at `http://127.0.0.1:8000`.

---

### Frontend Setup

1. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure frontend environment:**
   Create `frontend/.env.local` if using Firebase authentication or a custom backend URL:
   ```env
   BACKEND_URL=http://127.0.0.1:8000
   NEXT_PUBLIC_FIREBASE_API_KEY=your_firebase_key
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
   NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
   ```

3. **Launch the development server:**
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000/chat` to access the terminal cockpit.

---

## Developer Commands & Verification

A `Makefile` is provided at the repository root for common operational tasks:

| Command | Action | Description |
|---|---|---|
| `make check` | Lint + Format + Test | Executes `ruff check`, `ruff format --check`, and the full `pytest` suite. |
| `make test` | Test Suite | Runs all backend unit and integration tests offline using fixtures. |
| `make smoke` | Ingestion Smoke Test | Runs the ingestion graph with forced failures to test resilience. |
| `make live` | Live Ingestion Daemon | Starts continuous live ingestion into Pinecone/Weaviate. |
| `make latency` | Latency Benchmark | Measures end-to-end ingestion timing and updates `docs/latency_report.md`. |
| `make schema` | Sync Event Schemas | Exports agent run-event schemas to `frontend/types/run-events.schema.json`. |
| `make lint` | Code Linting | Runs `ruff check .` across backend packages. |
| `make format` | Formatting Check | Checks code style compliance with `ruff format --check .`. |

On Windows systems where `make` is not available, the equivalent `uv run` commands can be executed inside `backend/`:
```powershell
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

---

## Multi-Agent Execution Flow

When a query is dispatched in the terminal (e.g., *"Assess the impact of recent tariff announcements and crude spikes on RELIANCE"*):

1. **Coordinator Parsing**: Identifies target symbols (`RELIANCE.NS`), benchmark indices, and applicable themes (`TARIFF`, `WAR_CRISIS`).
2. **Parallel Ingestion & Retrieval**:
   - Fetches live quotes, valuation metrics, and intraday price dynamics.
   - Extracts relevant geopolitical and macroeconomic developments.
   - Queries historical crisis analogs matching current macro conditions.
3. **Quantitative Risk Modeling**:
   - Calculates historical VaR/CVaR, volatility regimes, and cross-asset correlations against Brent crude, USD/INR, and India VIX.
   - Projects historical disaster return bounds onto the asset.
4. **Hedging Formulation**:
   - Derives structured hedge recommendations (e.g. out-of-the-money put spreads, collar structures, beta-weighted index hedges).
5. **Evidence Auditing**:
   - Compares every metric mentioned in the synthesis against the evidence catalog.
   - Injects verifiable `[E#]` citations and generates a transparent Risk & Trust rating.
6. **Real-time SSE Streaming**:
   - Emits granular node lifecycle events (`run_started`, `node_started`, `node_finished`, `final_answer`) directly into the Next.js chat interface.

---

## Documentation & References

- [Architecture & Design Details](docs/architecture.md): System components, data flows, and persistence specifications.
- [Code Map](docs/CODEMAP.md): Comprehensive map of modules, package responsibilities, and key files.
- [Architectural Decision Records (ADRs)](docs/DECISIONS.md): Record of design decisions, compromises, and evolutions.
- [Data Contract](docs/data-contract.md): Strict Pydantic schemas, normalization contracts, and theme definitions.
- [Live Ingestion Latency Report](docs/latency_report.md): End-to-end telemetry measurements across all data streams.
- [Operational Contract (AGENTS.md)](AGENTS.md): Standing rules and architectural invariants for all contributors.
