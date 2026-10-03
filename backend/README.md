# StopLoss Intelligence Backend

This package contains the core backend services, ingestion pipelines, domain models, and storage layer for StopLoss Intelligence.

See the root [README.md](../README.md) for full setup instructions and development workflows.

## LangGraph ingestion entry point

From this directory, run `uv sync`, then `uv run python -m fin_terminal.ingest --once`
or `uv run python -m fin_terminal.ingest --stream`. The new package preserves the
existing `stop_loss` package. See [ingestion documentation](../docs/ingestion.md)
for smoke tests, failure injection, tracing, and vector service configuration.

## Analysis terminal API (Checkpoints 3–5)

```bash
uv sync
uv run stop-loss-api            # FastAPI on 127.0.0.1:8000 (keep it private; Next.js proxies it)
```

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Start a multi-agent run; SSE stream of `run_started`, `agent_update`, `section`, `final` / `reply` / `error` (each with `seq`) |
| `GET /chat/runs/{id}/events?after=N` | Resume a stream after a disconnect |
| `POST /chat/runs/{id}/cancel` | Stop a run |
| `GET /chat/threads/{id}/active-run` | Re-attach after a page reload |
| `GET /market/chart`, `GET /market/quote` | Yahoo Finance OHLCV + live quote (with market state) |
| `GET /assets/search?q=` | Ticker / company search |
| `POST/GET/DELETE /feedback` | Per-message feedback (SQLite WAL) |
| `GET /news/feed` | Landing-page feed |

All endpoints except `/health`, `/market/*`, `/assets/search` and `/news/feed` need `X-User-Id`. If `API_INTERNAL_TOKEN` is set, every request also needs `X-Internal-Token`.

Agents (`stop_loss/agents`): Query Coordinator → Market Data, News Sentiment, Macro (FRED), Weather (Open-Meteo) in parallel → Quantitative Risk → Hedging Strategy → Evidence & Audit. With `OPENAI_API_KEY` set, OpenAI writes the routing, sentiment and narrative. Without it, a deterministic, evidence-only narrative is used. See `docs/DECISIONS.md` ADR T01–T10.

Tests: `uv run pytest tests/terminal` (offline; replays recorded real provider responses from `tests/fixtures/terminal/`).
