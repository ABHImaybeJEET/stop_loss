"""`stop-loss-vectors`: manage the Pinecone index and the historical-data backfill.

init                      create/verify the serverless index (cosine, EMBEDDING_DIMENSIONS)
stats                     vector counts per namespace
count   --source S        how many records a backfill would index (no embedding/upsert)
backfill --source S       embed on the local GPU and upsert (resumable; --reset to restart)
search  "text"            semantic search over the history namespace
purge   --yes             delete the history namespace + backfill bookkeeping (re-index)
        --source S        ...or only one dataset's vectors (by stored ids)
"""

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Iterator

from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.storage import DocumentStore
from fin_terminal.vectorstore.factory import create_vectorstore
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter
from fin_terminal.vectorstore.pinecone_control import ensure_index
from stop_loss.retrieval import datasets
from stop_loss.retrieval.backfill import Backfill, BackfillStats, Progress
from stop_loss.retrieval.search import HistoricalRetriever
from stop_loss.settings import TerminalSettings, get_terminal_settings

DOC_TYPES = ("news", "company", "cyclone", "earthquake")


def pinecone_settings() -> TerminalSettings:
    return get_terminal_settings().model_copy(update={"vector_backend": "pinecone"})


def records_for(source: str, settings: TerminalSettings) -> Iterator[datasets.Record]:
    root = settings.datasets_dir
    if source == "india_news":
        return datasets.india_news(
            root,
            min_year=settings.india_news_min_year,
            categories=tuple(settings.india_news_categories),
        )
    return getattr(datasets, source)(root)


def adapter_for(settings: TerminalSettings) -> PineconeVectorAdapter:
    adapter = create_vectorstore(settings)
    assert isinstance(adapter, PineconeVectorAdapter)
    return adapter


async def cmd_stats(settings: TerminalSettings) -> None:
    adapter = adapter_for(settings)
    try:
        print(json.dumps(await adapter.stats(), indent=2))
    finally:
        await adapter.close()


def cmd_count(settings: TerminalSettings, sources: list[str]) -> None:
    total = 0
    for source in sources:
        count = sum(1 for _ in records_for(source, settings))
        total += count
        print(f"{source:<12} {count:>10,}")
    print(f"{'total':<12} {total:>10,}")


async def cmd_backfill(
    settings: TerminalSettings, sources: list[str], limit: int | None, reset: bool
) -> None:
    adapter = adapter_for(settings)
    store = DocumentStore(settings.database_path)
    progress = Progress(settings.backfill_progress_path)
    runner = Backfill(
        LazyEmbeddings(settings),
        adapter,
        store,
        progress,
        namespace=settings.pinecone_history_namespace,
    )

    def report(stats: BackfillStats) -> None:
        print(
            f"  {stats.source}: {stats.upserted:,} upserted, {stats.skipped_existing:,} "
            f"already indexed, {stats.rate:,.0f}/s",
            flush=True,
        )

    try:
        for source in sources:
            if reset:
                progress.reset(source)
            print(f"[{source}] starting (resume after line {progress.get(source)})", flush=True)
            stats = await runner.run(
                source, records_for(source, settings), limit=limit, on_progress=report
            )
            print(
                f"[{source}] done: {stats.upserted:,} upserted, {stats.skipped_existing:,} "
                f"skipped in {stats.seconds:,.1f}s",
                flush=True,
            )
    finally:
        await adapter.close()
        store.close()
        progress.close()


async def cmd_purge_source(settings: TerminalSettings, source: str) -> None:
    store = DocumentStore(settings.database_path)
    ids = store.hashes_for_source(datasets.SOURCE_IDS[source], datasets.RUN_ID)
    adapter = adapter_for(settings)
    try:
        await adapter.delete_ids(ids, settings.pinecone_history_namespace)
    finally:
        await adapter.close()
    store.delete_hashes(ids)
    store.close()
    progress = Progress(settings.backfill_progress_path)
    progress.reset(source)
    progress.close()
    print(f"purged {len(ids):,} '{source}' vectors and their backfill bookkeeping")


async def cmd_purge(settings: TerminalSettings) -> None:
    adapter = adapter_for(settings)
    try:
        await adapter.delete_namespace(settings.pinecone_history_namespace)
    finally:
        await adapter.close()
    store = DocumentStore(settings.database_path)
    removed = store.delete_run(datasets.RUN_ID)
    store.close()
    progress = Progress(settings.backfill_progress_path)
    for source in datasets.SOURCES:
        progress.reset(source)
    progress.close()
    print(
        f"purged namespace '{settings.pinecone_history_namespace}', {removed:,} stored docs, "
        "and backfill progress"
    )


async def cmd_search(settings: TerminalSettings, args: argparse.Namespace) -> None:
    adapter = adapter_for(settings)
    retriever = HistoricalRetriever(
        LazyEmbeddings(settings), adapter, settings.pinecone_history_namespace
    )
    try:
        hits = await retriever.search(
            args.query,
            top_k=args.top_k,
            doc_types=args.type or None,
            year_from=args.year_from,
            year_to=args.year_to,
            regions=args.region or None,
            min_category=args.min_category,
        )
    finally:
        await adapter.close()
    for hit in hits:
        meta = hit.metadata
        print(
            f"{hit.score:.3f}  [{meta.get('doc_type')}] {meta.get('year', '')}  "
            f"{(meta.get('title') or hit.text)[:110]}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="stop-loss-vectors",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("stats")
    for name in ("count", "backfill"):
        p = sub.add_parser(name)
        p.add_argument("--source", choices=[*datasets.SOURCES, "all"], default="all")
        if name == "backfill":
            p.add_argument("--limit", type=int, default=None, help="records per source")
            p.add_argument("--reset", action="store_true", help="ignore saved progress")
    purge = sub.add_parser("purge")
    purge.add_argument("--yes", action="store_true", help="confirm deletion")
    purge.add_argument("--source", choices=datasets.SOURCES, help="only this dataset")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--top-k", type=int, default=8)
    s.add_argument("--type", action="append", choices=DOC_TYPES)
    s.add_argument("--year-from", type=int)
    s.add_argument("--year-to", type=int)
    s.add_argument("--region", action="append", help='e.g. "Gulf of Mexico", "Bay of Bengal"')
    s.add_argument("--min-category", type=int, help="cyclones: Saffir-Simpson equivalent")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    settings = pinecone_settings()
    sources = list(datasets.SOURCES) if getattr(args, "source", "all") == "all" else [args.source]

    if args.command == "init":
        index = ensure_index(settings)
        print(
            f"index={index.get('name')} dimension={index.get('dimension')} "
            f"metric={index.get('metric')} host={index.get('host')} ready="
            f"{(index.get('status') or {}).get('ready')}"
        )
    elif args.command == "stats":
        asyncio.run(cmd_stats(settings))
    elif args.command == "count":
        cmd_count(settings, sources)
    elif args.command == "backfill":
        asyncio.run(cmd_backfill(settings, sources, args.limit, args.reset))
    elif args.command == "purge":
        if not args.yes:
            print("Refusing to purge without --yes")
            return 1
        if args.source:
            asyncio.run(cmd_purge_source(settings, args.source))
        else:
            asyncio.run(cmd_purge(settings))
    elif args.command == "search":
        asyncio.run(cmd_search(settings, args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
