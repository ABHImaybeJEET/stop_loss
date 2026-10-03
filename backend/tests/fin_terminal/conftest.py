import json
from pathlib import Path

import pytest

from fin_terminal.config import Settings
from fin_terminal.schemas import RECORD_ADAPTER, Document

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture(autouse=True)
def offline_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_path=tmp_path / "records.sqlite",
        checkpoint_path=tmp_path / "checkpoints.sqlite",
        evidence_path=tmp_path / "evidence.jsonl",
        langsmith_tracing=False,
        langsmith_api_key=None,
        source_rate_per_second=10000,
        source_burst=10,
        retry_max_wait_seconds=0.001,
        stub_fail_source="",
    )


@pytest.fixture
def document() -> Document:
    return RECORD_ADAPTER.validate_python(
        json.loads((FIXTURES / "normalized_news.json").read_text(encoding="utf-8"))
    )
