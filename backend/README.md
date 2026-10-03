# StopLoss Intelligence Backend

This package contains the core backend services, ingestion pipelines, domain models, and storage layer for StopLoss Intelligence.

See the root [README.md](../README.md) for full setup instructions and development workflows.

## LangGraph ingestion entry point

From this directory, run `uv sync`, then `uv run python -m fin_terminal.ingest --once`
or `uv run python -m fin_terminal.ingest --stream`. The new package preserves the
existing `stop_loss` package. See [ingestion documentation](../docs/ingestion.md)
for smoke tests, failure injection, tracing, and vector service configuration.
