from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from fin_terminal.config import Settings
from fin_terminal.ingestion.graph import SOURCES
from fin_terminal.observability import confirm_trace, run_config, tracing_client
from fin_terminal.schemas import Theme


def test_run_config_has_correlation_tags_and_identity():
    trace_id = uuid4()
    config = run_config("ingest-123", trace_id, list(SOURCES))
    assert config["run_name"] == "fin-terminal-ingestion"
    assert config["run_id"] == trace_id
    assert config["metadata"]["ingest_run_id"] == "ingest-123"
    assert all(f"source:{s}" in config["tags"] for s in SOURCES)
    assert all(f"theme:{t.value}" in config["tags"] for t in Theme)


def test_trace_is_not_claimed_without_key(settings: Settings, caplog):
    caplog.set_level("INFO", logger="fin_terminal")
    assert tracing_client(settings) is None
    assert "no LANGSMITH_API_KEY" in caplog.text


def test_smoke_trace_confirmation_reads_completed_run():
    client = Mock()
    client.read_run.return_value = SimpleNamespace(end_time="completed")
    trace_id = uuid4()
    confirm_trace(client, trace_id)
    client.flush.assert_called_once_with(timeout=10)
    client.read_run.assert_called_once_with(trace_id)
