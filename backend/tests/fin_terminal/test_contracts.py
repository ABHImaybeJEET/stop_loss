import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fin_terminal.config import Settings
from fin_terminal.evidence import EvidenceLog
from fin_terminal.schemas import (
    Document,
    EvidenceLogEntry,
    MacroIndicator,
    PricePoint,
    WeatherEvent,
)


@pytest.mark.parametrize(
    "model, extra",
    [
        (PricePoint, {"symbol": "TEST"}),
        (MacroIndicator, {"series_id": "TEST"}),
        (WeatherEvent, {"location": "fixture", "metric": "fixture"}),
    ],
)
def test_missing_metrics_stay_null(model, extra):
    record = model(
        source="fixture",
        provider="fixture",
        fetched_at="2026-10-03T00:00:00Z",
        ingest_run_id="fixture",
        **extra,
    )
    assert record.data_quality == "missing_fields"
    assert getattr(record, "price", getattr(record, "value", None)) is None
    assert len(record.content_hash) == 64


def test_hash_is_stable_across_runs_and_timezone_offsets(document: Document):
    payload = document.model_dump(mode="json")
    payload.update(
        {
            "ingest_run_id": "another-run",
            "published_at": "2026-10-03T05:30:00+05:30",
            "fetched_at": "2026-10-04T00:00:00Z",
            "fetch_latency_ms": 100,
            "process_latency_ms": 25,
            "theme_tags": ["TARIFF"],
        }
    )
    assert type(document).model_validate(payload).content_hash == document.content_hash
    payload["title"] = "Changed content"
    with pytest.raises(ValidationError, match="content_hash"):
        type(document).model_validate(payload)
    payload["content_hash"] = ""
    assert type(document).model_validate(payload).content_hash != document.content_hash


def test_naive_timestamps_and_nonfinite_metrics_rejected(document: Document):
    payload = document.model_dump(mode="json")
    payload["fetched_at"] = datetime(2026, 10, 3)
    with pytest.raises(ValidationError):
        type(document).model_validate(payload)
    with pytest.raises(ValidationError):
        PricePoint(
            source="fixture",
            provider="fixture",
            ingest_run_id="fixture",
            fetched_at="2026-10-03T00:00:00Z",
            symbol="TEST",
            price=float("nan"),
        )


def test_evidence_append_preserves_history(tmp_path: Path):
    path = tmp_path / "evidence.jsonl"
    entry = EvidenceLogEntry(ingest_run_id="a", stage="plan", event="started")
    EvidenceLog(path).append(entry)
    prefix = path.read_bytes()
    EvidenceLog(path).append(entry.model_copy(update={"ingest_run_id": "b"}))
    assert path.read_bytes().startswith(prefix)
    assert [json.loads(line)["ingest_run_id"] for line in path.read_text().splitlines()] == [
        "a",
        "b",
    ]


def test_new_settings_from_env_and_redacted_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHECKPOINT_PATH", "custom/checkpoint.sqlite")
    monkeypatch.setenv("VECTOR_BACKEND", "pinecone")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "fixture-secret")
    monkeypatch.setenv("SOURCE_RATE_PER_SECOND", "0.5")
    settings = Settings(_env_file=None)
    assert settings.checkpoint_path == Path("custom/checkpoint.sqlite")
    assert settings.vector_backend == "pinecone"
    assert settings.source_rate_per_second == 0.5
    assert "fixture-secret" not in repr(settings)
    assert settings.alpha_vantage_api_key.get_secret_value() == "fixture-secret"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vector_backend="unsupported")


def test_environment_example_covers_every_setting():
    example = Path(__file__).parents[3] / ".env.example"
    names = {
        line.split("=", 1)[0].lower()
        for line in example.read_text().splitlines()
        if line and not line.startswith("#")
    }
    assert set(Settings.model_fields) <= names
