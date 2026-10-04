from pathlib import Path

import pytest

from stop_loss.settings import TerminalSettings


@pytest.fixture(autouse=True)
def offline_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def settings(tmp_path: Path) -> TerminalSettings:
    return TerminalSettings(
        _env_file=None,
        database_path=tmp_path / "records.sqlite",
        checkpoint_path=tmp_path / "checkpoints.sqlite",
        evidence_path=tmp_path / "evidence.jsonl",
        dead_letter_path=tmp_path / "dead_letters.jsonl",
        conversation_db_path=tmp_path / "conversations.sqlite",
        feedback_db_path=tmp_path / "feedback.sqlite",
        runs_db_path=tmp_path / "runs.sqlite",
        langsmith_tracing=False,
        langsmith_api_key=None,
        openai_api_key=None,
        alpha_vantage_api_key=None,
        fred_api_key="test-fred-key",
        source_rate_per_second=10000,
        source_burst=10,
        yahoo_rate_per_second=10000,
        retry_max_wait_seconds=0.001,
    )
