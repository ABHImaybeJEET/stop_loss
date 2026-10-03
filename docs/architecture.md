# StopLoss Intelligence: System Architecture

StopLoss Intelligence is an AI financial intelligence terminal designed to combine weather intelligence, news feeds, market quotes, macroeconomic indicators, historical event analog matching, and portfolio risk calculations to deliver evidence-backed hedging recommendations.

## End-to-End System Pipeline

```text
Weather, News, Market and Macro APIs
                  ↓
          Provider adapters
                  ↓
        Normalized records
                  ↓
        SQLite record store
                  ↓
  Historical and vector retrieval
                  ↓
 Risk, sentiment and event analytics
                  ↓
       LangGraph agent workflow
                  ↓
             FastAPI
                  ↓
      Next.js intelligence terminal
```

## Layer Architecture & Responsibilities

### 1. Ingestion Layer (`stop_loss.ingestion`)
- **Adapters**: Concrete implementations of `DataProvider` (`OpenMeteoProvider`, `GDELTProvider`, `YahooFinanceProvider`, `FREDProvider`).
- **Resilience**: Independent error categorization (`timeout`, `rate_limit`, `authentication`, `invalid_response`, `unavailable`), circuit breakers, and bounded retries.
- **Normalization**: Immediate transformation of heterogeneous external schemas into strongly typed `NormalizedRecord` models.

### 2. Storage & Persistence (`stop_loss.storage`)
- **SQLite Engine**: Local, zero-configuration relational persistence with Write-Ahead Logging (WAL) enabled for concurrent reads and writes.
- **Auditing**: Dedicated `IngestionRun` tracking table recording batch metrics (fetched, inserted, updated, skipped, errors).
- **Indexing**: High-performance indexes on `data_type`, `provider`, `ticker`, `entity`, and `observed_at`.

### 3. Retrieval & Semantic Search (`stop_loss.retrieval` - Future Checkpoint 2)
- **Hybrid Querying**: Combines exact SQL relational filtering with dense semantic embeddings.
- **Analog Matching**: Indexes historical crisis scenarios (e.g. Hurricane Katrina 2005, Texas Freeze 2021, Red Sea shipping attacks 2023) to identify historical market behavior patterns.

### 4. Quantitative & Sentiment Analytics (`stop_loss.analytics` - Future Checkpoint 3)
- **Risk Models**: Value at Risk (VaR), Conditional VaR (CVaR), and drawdown projections under extreme physical/macro shocks.
- **Stress Testing**: Simulates supply disruptions, hurricane path intersections with oil infrastructure, and energy price volatility.

### 5. Multi-Agent Orchestration (`stop_loss.agents` - Future Checkpoint 4)
The cognitive layer is driven by a cooperative multi-agent graph orchestrated with LangGraph. Each agent possesses a focused domain responsibility:

1. **Query Coordinator**: Parses incoming user questions or portfolio scenarios, decomposing them into directed sub-tasks for specialist agents.
2. **News Sentiment Agent**: Evaluates news feeds, press releases, and geopolitical statements for negative tone, disruption alerts, and supply bottlenecks.
3. **Weather Impact Agent**: Translates storm trajectories, wind velocities, and flood levels into facility-level operational threat ratings.
4. **Macro Analysis Agent**: Contextualizes interest rate shifts, CPI surprises, and inventory reports in relation to sector vulnerability.
5. **Quantitative Risk Agent**: Executes VaR calculations, scenario stress tests, and portfolio sensitivity matrices.
6. **Historical Event Retrieval Agent**: Finds past comparable market disruptions (e.g. Hurricane Katrina, Texas deep freeze) and identifies how assets responded.
7. **Hedging Strategy Agent**: Synthesizes multi-agent signals to formulate tactical hedging recommendations (protective puts, futures spreads, collar structures).
8. **Evidence and Audit Agent**: Validates all generated recommendations against stored primary records, ensuring citation transparency and zero hallucinated claims.

### 6. API Layer (`stop_loss.api` - Future Checkpoint 5)
- **FastAPI**: Asynchronous REST endpoints and Server-Sent Events (SSE) / WebSocket streams for live terminal updates and agent chain-of-thought streaming.

### 7. Intelligence Terminal Frontend (`frontend` - Future Checkpoint 5)
- **Next.js**: High-density trader interface featuring geospatial hurricane tracking maps, asset heatmaps, multi-agent reasoning logs, and hedging execution tickets.
