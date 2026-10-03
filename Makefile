.PHONY: help install test smoke lint format check

help:
	@echo "StopLoss Intelligence Developer Commands:"
	@echo "  make install  - Install dependencies using uv in backend"
	@echo "  make test     - Run pytest suite in backend"
	@echo "  make smoke    - Run baseline + forced failure graph; verify tracing when configured"
	@echo "  make lint     - Run ruff lint check in backend"
	@echo "  make format   - Check code formatting with ruff in backend"
	@echo "  make check    - Run lint, format check, and tests in backend"

install:
	cd backend && uv sync

test:
	cd backend && uv run pytest

smoke:
	cd backend && uv run python -m fin_terminal.ingest --once --smoke

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format --check .

check: lint format test
