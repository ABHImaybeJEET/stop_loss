import json
import logging
import time
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langsmith import Client, traceable
from pydantic import JsonValue
from tenacity import retry, stop_after_attempt, wait_fixed

from fin_terminal.config import Settings, secret_value
from fin_terminal.schemas import StreamStatus, Theme

logger = logging.getLogger("fin_terminal")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


class LatencyTimer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000


def tracing_client(settings: Settings) -> Client | None:
    if not secret_value(settings.langsmith_api_key):
        logger.info("LangSmith trace skipped: no LANGSMITH_API_KEY set")
        return None
    if not settings.langsmith_tracing:
        logger.info("LangSmith trace skipped: LANGSMITH_TRACING=false")
        return None
    return Client(
        api_key=secret_value(settings.langsmith_api_key),
        api_url=settings.langsmith_endpoint,
        workspace_id=settings.langsmith_workspace_id or None,
        timeout_ms=5000,
    )


def run_config(
    ingest_run_id: str, trace_id: UUID, sources: list[str], *, stream: bool = False
) -> RunnableConfig:
    return {
        "run_name": "fin-terminal-ingestion",
        "run_id": trace_id,
        "tags": [
            "ingestion",
            *[f"source:{s}" for s in sources],
            *[f"theme:{theme.value}" for theme in Theme],
        ],
        "metadata": {
            "ingest_run_id": ingest_run_id,
            "mode": "stub",
            "execution_mode": "stream" if stream else "once",
        },
        "configurable": {"thread_id": ingest_run_id},
    }


@traceable(name="ingestion-report", run_type="tool")
def render_report(statuses: dict[str, dict[str, JsonValue]], indexed: int, duplicates: int) -> str:
    rows = ["SOURCE               STATUS         FETCHED  NORMALIZED"]
    for source, payload in sorted(statuses.items()):
        status = StreamStatus.model_validate(payload)
        rows.append(
            f"{source:<20} {status.status:<14} "
            f"{status.records_fetched:>7}  {status.records_normalized:>10}"
        )
    rows.append(f"Indexed: {indexed}; duplicates skipped: {duplicates}; mode: stub")
    return "\n".join(rows)


def confirm_trace(client: Client, trace_id: UUID) -> None:
    """Smoke succeeds only when the completed root trace is readable remotely."""
    client.flush(timeout=10)

    @retry(stop=stop_after_attempt(4), wait=wait_fixed(0.5), reraise=True)
    def verify() -> None:
        run = client.read_run(trace_id)
        if run.end_time is None:
            raise RuntimeError("LangSmith trace has not completed")

    verify()
    logger.info("LangSmith trace confirmed: %s", trace_id)
