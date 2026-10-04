.PHONY: help install test smoke lint format check schema live latency

help:
	@echo "StopLoss Intelligence Developer Commands:"
	@echo "  make install  - Install dependencies using uv in backend"
	@echo "  make test     - Run pytest suite in backend"
	@echo "  make smoke    - Run baseline + forced failure graph; verify tracing when configured"
	@echo "  make lint     - Run ruff lint check in backend"
	@echo "  make format   - Check code formatting with ruff in backend"
	@echo "  make check    - Run lint, format check, and tests in backend"
	@echo "  make schema   - Export run-event JSON schema to frontend/types"
	@echo "  make live     - Continuous live ingestion (news, GDACS, USGS, weather) into Pinecone live"
	@echo "  make latency  - Probe the live path; writes docs/latency_report.md"

install:
	cd backend && uv sync --extra onnx-embeddings

test:
	cd backend && uv run pytest

smoke:
	cd backend && uv run python -m fin_terminal.ingest --once --smoke

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format --check .

check: lint format test

schema:
	cd backend && uv run python -m stop_loss.agents.run_events

live:
	cd backend && uv run stop-loss-vectors live

latency:
	cd backend && uv run stop-loss-vectors latency
