import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fin_terminal.config import Settings
from fin_terminal.connectors.stub import StubConnector


def test_empty_stub_payloads_match_fixture():
    import asyncio

    fixture = Path(__file__).parents[1] / "fixtures" / "stub_sources.json"
    for source, payload in json.loads(fixture.read_text()).items():
        assert asyncio.run(StubConnector(source).fetch()) == payload


@pytest.mark.parametrize("mode", ["--once", "--stream"])
def test_cli_reports_forced_failure(settings: Settings, mode: str):
    env = {
        **os.environ,
        "DATABASE_PATH": str(settings.database_path),
        "CHECKPOINT_PATH": str(settings.checkpoint_path),
        "EVIDENCE_PATH": str(settings.evidence_path),
        "LANGSMITH_TRACING": "false",
        "LANGSMITH_API_KEY": "",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "fin_terminal.ingest",
            mode,
            "--max-cycles",
            "1",
            "--fail-source",
            "weather",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "weather              failed" in result.stdout
    assert "news_tariff          ok" in result.stdout
    assert "no LANGSMITH_API_KEY" in result.stderr
