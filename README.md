# StopLoss Intelligence

The `fin_terminal` ingestion scaffold is ready for offline use. Run `make test`
and `make smoke` to exercise the graph, including a forced source failure.
See [ingestion setup and operation](docs/ingestion.md) for CLI and tracing details.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Checked with Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/managed%20by-uv-blueviolet)](https://github.com/astral-sh/uv)

StopLoss Intelligence is an AI financial intelligence terminal and automated risk analysis platform that synthesizes environmental risk (weather, hurricanes), real-time geopolitical & disruption news, live market quotes, and macroeconomic indicators to generate evidence-backed hedging recommendations.

---

## The Problem

Severe physical events—such as Gulf of Mexico hurricanes, extreme winter freezes, and sudden geopolitical maritime chokepoints—produce rapid, non-linear market shocks. Portfolio managers, risk officers, and energy traders typically struggle with:
1. **Siloed Data**: Weather forecasts, news alerts, commodity prices, and macro series reside in separate disconnected tools.
2. **Lagged Analysis**: Calculating cross-asset portfolio exposure during rapidly unfolding emergencies takes hours or days.
3. **Unsubstantiated Suggestions**: Generic LLMs hallucinate financial advice without grounding recommendations in primary records, verifiable historical analogs, or rigorous math.

## The Planned System

StopLoss Intelligence bridges this gap with an end-to-end pipeline:
- **Multi-Modal Data Ingestion**: Continuously ingests weather forecasts (Open-Meteo), real-time news (GDELT), market quotes (Yahoo Finance), and macroeconomic data (FRED).
- **Normalized Storage**: Stores atomic observations in SQLite with full lineage tracking.
- **Retrieval & Analog Matching**: Retrieves relevant historical disaster scenarios to assess how assets reacted in comparable past conditions.
- **Quantitative Risk Engine**: Computes Value-at-Risk (VaR), sensitivity matrices, and stress scenario drawdowns.
- **Multi-Agent Orchestration**: A LangGraph graph of 8 specialized agents evaluates risks, formulates hedging options, and audits every statement against underlying records.
- **Trader Terminal**: An interactive Next.js cockpit with geospatial threat tracking, real-time telemetry, and actionable hedge tickets.

---

## Checkpoint 0 Scope: Project Foundation

This repository currently implements **Checkpoint 0: Project Foundation**.
It provides a clean, strongly typed foundation enabling four developers to collaborate in parallel:

### Included in Checkpoint 0:
- **Repository Structure**: Clean monorepo scaffold separating backend, frontend, data, docs, and scripts.
- **Typed Domain Models**: Pydantic v2 `NormalizedRecord` and `IngestionRun` schemas with strict timezone and data validation.
- **Domain Enums & Error Hierarchy**: `DataType`, `RunStatus`, `ProviderErrorType`, and resilient provider exceptions.
- **Provider & Storage Interfaces**: `DataProvider` and `RecordRepository` abstract base classes establishing clear contracts.
- **Configuration Management**: `Settings` using `pydantic-settings` supporting environment variables and `.env` files.
- **CLI Foundation**: Operational command-line interface with informative placeholder subcommands (`ingest`, `status`, `records`).
- **Comprehensive Documentation**: Complete system architecture, data contracts, roadmap, and progress tracking.

### Still Pending (Future Checkpoints):
- **Checkpoint 1**: Concrete provider implementations (Open-Meteo, GDELT, Yahoo Finance, FRED) and working SQLite persistence.
- **Checkpoint 2**: Historical crisis catalog, relational querying, and vector retrieval.
- **Checkpoint 3**: Quantitative portfolio risk engine (VaR, CVaR, stress testing, hedging calculations).
- **Checkpoint 4**: LangGraph multi-agent orchestration and deliberative reasoning graph.
- **Checkpoint 5**: FastAPI streaming endpoints and Next.js trader terminal frontend.
- **Checkpoint 6**: Resilience testing, agent benchmark evaluations, and final demonstration playback.

---

## Project Structure

```text
stop_loss/
├── backend/
│   ├── pyproject.toml              # Build config, dependencies, and tool definitions
│   ├── src/
│   │   └── stop_loss/
│   │       ├── __init__.py         # Package root
│   │       ├── __main__.py         # CLI entrypoint
│   │       ├── config.py           # Pydantic Settings configuration
│   │       ├── logging_config.py   # Structured logging configuration
│   │       │
│   │       ├── domain/             # Core business models, enums, and errors
│   │       │   ├── __init__.py
│   │       │   ├── enums.py
│   │       │   ├── models.py
│   │       │   └── errors.py
│   │       │
│   │       ├── ingestion/          # Data collection layer & provider adapters
│   │       │   ├── __init__.py
│   │       │   ├── base.py
│   │       │   ├── runner.py
│   │       │   └── providers/
│   │       │       ├── __init__.py
│   │       │       ├── weather.py
│   │       │       ├── news.py
│   │       │       ├── market.py
│   │       │       └── macro.py
│   │       │
│   │       ├── storage/            # Persistence abstractions & SQLite store
│   │       │   ├── __init__.py
│   │       │   ├── base.py
│   │       │   └── sqlite.py
│   │       │
│   │       ├── retrieval/          # Semantic & relational query engine (Checkpoint 2)
│   │       │   ├── __init__.py
│   │       │   └── README.md
│   │       │
│   │       ├── analytics/          # Quantitative risk & hedging math (Checkpoint 3)
│   │       │   ├── __init__.py
│   │       │   └── README.md
│   │       │
│   │       ├── agents/             # Multi-agent graph & reasoning (Checkpoint 4)
│   │       │   ├── __init__.py
│   │       │   └── README.md
│   │       │
│   │       └── api/                # FastAPI application & endpoints (Checkpoint 5)
│   │           ├── __init__.py
│   │           └── README.md
│   │
│   └── tests/
│       ├── unit/
│       │   ├── test_models.py
│       │   └── test_config.py
│       ├── integration/
│       │   └── README.md
│       └── fixtures/
│           └── README.md
│
├── frontend/                       # Next.js trader terminal (Checkpoint 5)
│   └── README.md
│
├── data/
│   ├── raw/                        # Raw API response payloads
│   │   └── .gitkeep
│   └── processed/                  # Normalized and cached datasets
│       └── .gitkeep
│
├── docs/                           # Architecture, contracts, and roadmap
│   ├── architecture.md
│   ├── data-contract.md
│   ├── roadmap.md
│   └── progress.md
│
├── scripts/                        # Automation & playback utilities
│   └── README.md
│
├── .env.example                    # Sample environment variables
├── .gitignore                      # Git ignore rules
├── Makefile                        # Convenience developer commands
└── README.md                       # Project overview
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (fast Python package and environment manager)

### Installation
Clone the repository and install backend dependencies:

```bash
cd backend
uv sync
```

Optionally copy the sample environment file:

```bash
cp ../.env.example ../.env
```

---

## Validation Commands

Run these commands to validate the environment and codebase:

```bash
cd backend
uv sync
uv run python -m stop_loss --help
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Or run via `make` from the repository root:

```bash
make check
```

---

## Team Development Workflow

To ensure smooth collaboration among multiple developers:
1. **Branching**: Always branch off `main` with descriptive feature branches (e.g. `feat/open-meteo-provider`, `feat/sqlite-storage`, `test/provider-fixtures`). **Never push directly to `main`.**
2. **Contract Preservation**: Do not alter `NormalizedRecord` or `IngestionRun` fields without updating `docs/data-contract.md` and notifying the team.
3. **Pre-PR Verification**: Run `make check` (or the equivalent `uv run` commands) before opening a pull request.
4. **Independent Failure Isolation**: In Checkpoint 1, ensure providers fail independently without halting the entire ingestion cycle.
## LangGraph ingestion scaffold

The new `fin_terminal` package is available alongside the existing `stop_loss`
package. Run `make test` and `make smoke` from the repository root. Smoke runs
the six empty source stubs and verifies that a forced weather failure still
produces a complete report. See [ingestion setup and operation](docs/ingestion.md)
and [repository inspection decisions](docs/DECISIONS.md#adr-009-repository-inventory-and-compatibility-2026-10-03).
