"""python -m fin_terminal.ingest --once | --stream (stub sources)."""

import argparse
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langsmith import tracing_context

from fin_terminal.config import Settings
from fin_terminal.ingestion.graph import SOURCES, IngestionPipeline, IngestionState
from fin_terminal.observability import (
    configure_logging,
    confirm_trace,
    logger,
    run_config,
    tracing_client,
)


async def run(
    settings: Settings,
    *,
    stream: bool = False,
    smoke: bool = False,
    max_cycles: int | None = None,
    live: bool = False,
) -> list[IngestionState]:
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    client = tracing_client(settings)
    results: list[IngestionState] = []
    pipeline = IngestionPipeline(settings, live=live)
    try:
        async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_path)) as saver:
            await saver.setup()  # sets WAL journal mode
            graph = pipeline.build_graph(saver)
            cycles = 0
            while True:
                run_id, trace_id = str(uuid4()), uuid4()
                with tracing_context(
                    enabled=client is not None,
                    client=client,
                    project_name=settings.langsmith_project,
                ):
                    result = await graph.ainvoke(
                        {
                            "ingest_run_id": run_id,
                            "langsmith_run_id": str(trace_id) if client else None,
                        },
                        config=run_config(run_id, trace_id, list(SOURCES), stream=stream),
                    )
                print(result["report"], flush=True)
                cycles += 1
                if smoke and client is not None:
                    await asyncio.to_thread(confirm_trace, client, trace_id)
                # Retain only the latest cycle; streaming must not accumulate unbounded state.
                results[:] = [result]
                if not stream or (max_cycles is not None and cycles >= max_cycles):
                    break
                await asyncio.sleep(settings.ingestion_poll_seconds)
    finally:
        await pipeline.close()
        if client is not None:
            await asyncio.to_thread(client.flush, timeout=10)
    return results


async def smoke_run(settings: Settings) -> None:
    with TemporaryDirectory(prefix="fin-terminal-smoke-") as directory:
        root = Path(directory)
        settings = settings.model_copy(
            update={
                "checkpoint_path": root / "checkpoints.sqlite",
                "database_path": root / "records.sqlite",
                "evidence_path": root / "evidence.jsonl",
                "stub_fail_source": "",
            }
        )
        result = (await run(settings, smoke=True))[0]
        if any(status["status"] != "ok" for status in result["statuses"].values()):
            raise RuntimeError("baseline smoke did not report all six streams ok")
        print("\nForced failure smoke: weather", flush=True)
        settings = settings.model_copy(
            update={
                "stub_fail_source": "weather",
                "stub_failure_mode": "failed",
            }
        )
        result = (await run(settings, smoke=True))[0]
        if len(result["statuses"]) != 6 or result["statuses"]["weather"]["status"] != "failed":
            raise RuntimeError("forced-failure smoke did not preserve the full stream report")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ingestion graph with empty stub sources")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--stream", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="isolated baseline + failure smoke")
    parser.add_argument(
        "--live",
        action="store_true",
        help="use real external API connectors (Alpha Vantage, FRED, Open-Meteo)",
    )
    parser.add_argument("--fail-source", choices=SOURCES)
    parser.add_argument("--failure-mode", choices=("failed", "degraded", "rate_limited"))
    parser.add_argument("--max-cycles", type=int, help="stop streaming after N cycles")
    args = parser.parse_args()
    if args.max_cycles is not None and args.max_cycles < 1:
        parser.error("--max-cycles must be positive")
    if args.smoke and args.stream:
        parser.error("--smoke requires --once")
    settings = Settings()
    updates = {}
    if args.fail_source:
        updates["stub_fail_source"] = args.fail_source
    if args.failure_mode:
        updates["stub_failure_mode"] = args.failure_mode
    settings = settings.model_copy(update=updates)
    configure_logging(settings.log_level)
    try:
        asyncio.run(
            smoke_run(settings)
            if args.smoke
            else run(
                settings,
                stream=args.stream,
                max_cycles=args.max_cycles,
                live=args.live,
            )
        )
    except KeyboardInterrupt:
        logger.info("Ingestion stopped")


if __name__ == "__main__":
    main()
