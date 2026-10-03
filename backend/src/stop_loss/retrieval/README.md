# Retrieval Engine (Checkpoint 2)

## Purpose & Scope
This module provides hybrid retrieval across historical and current financial intelligence:
- **Relational & Temporal Filtering**: Querying normalized weather, news, macro, and market prices in SQLite.
- **Semantic & Vector Indexing**: Embedding news articles, analyst commentary, and historical event narratives for vector similarity search.
- **Event Analog Matching**: Identifying past historical scenarios (e.g. Hurricane Katrina, deep freeze, refinery shut-ins) that match current emerging conditions.

## Planned Interfaces
- `HybridRetriever`: Combines keyword/BM25 and dense vector similarity.
- `EventMatcher`: Matches multi-modal condition vectors (weather intensity + energy volatility) to historical analogies.
