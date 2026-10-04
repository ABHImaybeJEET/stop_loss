"""Live-path latency probe (`make latency`): fetch → embed → upsert → queryable, per stage
and per source, written to docs/latency_report.md.

Measured against a scratch namespace that is emptied first and without content-hash
dedupe, so every record is a genuinely new write (re-upserting already-indexed live
records would be visible instantly and understate the real indexing latency)."""

import math
import platform
from collections.abc import Iterable
from datetime import UTC, datetime

from stop_loss.retrieval.live import RecordTiming

STAGES = ("fetch_ms", "embed_ms", "upsert_ms", "process_ms", "queryable_ms", "end_to_end_ms")
STAGE_LABELS = {
    "fetch_ms": "fetch (per poll)",
    "embed_ms": "embed (micro-batch)",
    "upsert_ms": "upsert (micro-batch)",
    "process_ms": "process = embed + upsert",
    "queryable_ms": "upsert ack → queryable",
    "end_to_end_ms": "end-to-end (fetch → queryable)",
}
LATENCY_BUDGET_MS = 1000.0


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (no interpolation: every reported value was observed)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def stage_values(timings: Iterable[RecordTiming], stage: str) -> list[float]:
    out: list[float] = []
    for t in timings:
        if stage == "process_ms":
            out.append(t.process_ms)
        elif stage == "end_to_end_ms":
            if t.queryable_ms is not None:
                out.append(t.fetch_ms + t.process_ms + t.queryable_ms)
        elif stage == "queryable_ms":
            if t.queryable_ms is not None:
                out.append(t.queryable_ms)
        else:
            out.append(getattr(t, stage))
    return out


def summarize(timings: list[RecordTiming]) -> dict[str, dict[str, dict[str, float | None]]]:
    """{scope: {stage: {n, p50, p95, p99}}}; scope is 'all' or a source name."""
    scopes = {"all": timings}
    for t in timings:
        scopes.setdefault(t.source, []).append(t)
    return {
        scope: {
            stage: {
                "n": float(len(vals := stage_values(items, stage))),
                "p50": percentile(vals, 50),
                "p95": percentile(vals, 95),
                "p99": percentile(vals, 99),
            }
            for stage in STAGES
        }
        for scope, items in scopes.items()
    }


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.0f}"


def render_report(
    timings: list[RecordTiming],
    *,
    embedder: str,
    namespace: str,
    failures: dict[str, str],
    duration_seconds: float,
    microbatch: int = 1,
    round_trip_ms: list[float] | None = None,
) -> str:
    summary = summarize(timings)
    process_p95 = summary["all"]["process_ms"]["p95"]
    if process_p95 is None:
        verdict = "No records were indexed, so the latency invariant could not be measured."
    elif process_p95 < LATENCY_BUDGET_MS:
        verdict = f"Within budget: p95 process+embed+index {process_p95:,.0f} ms < 1,000 ms."
    else:
        verdict = f"Over budget: p95 process+embed+index {process_p95:,.0f} ms ≥ 1,000 ms."
    embed_p95 = summary["all"]["embed_ms"]["p95"]
    upsert_p95 = summary["all"]["upsert_ms"]["p95"]
    if embed_p95 is not None and upsert_p95 is not None:
        verdict += (
            f" Local share (embed) p95 {embed_p95:,.0f} ms; Pinecone write round trip "
            f"p95 {upsert_p95:,.0f} ms."
        )
    unseen = sum(1 for t in timings if t.queryable_ms is None)
    lines = [
        "# Live ingestion latency report",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC} by `make latency` "
        f"(`stop-loss-vectors latency`) on {platform.system()} {platform.machine()}.",
        "",
        f"- Records measured: **{len(timings)}** over {duration_seconds:,.0f} s "
        f"(scratch namespace `{namespace}`, emptied first; no dedupe).",
        f"- Embedder: {embedder}; micro-batch size {microbatch}; sources probed one at a "
        "time so no probe traffic overlaps a measured write.",
        f"- {verdict}",
        "- Queryable = time from the upsert acknowledgement until a `content_hash`-filtered "
        f"query returns the record (polled every 250 ms). {unseen} record(s) were not "
        "observed within the timeout and are excluded from that row (not imputed).",
        "- `fetch` is per poll (all items of one poll share it); embed/upsert are per "
        "micro-batch, which is the latency each item in it experiences.",
    ]
    if round_trip_ms:
        lines.append(
            "- Network floor: a bare Pinecone `describe_index_stats` round trip from this "
            f"machine took p50 {_fmt(percentile(round_trip_ms, 50))} ms / min "
            f"{_fmt(min(round_trip_ms))} ms (n={len(round_trip_ms)}). Every upsert pays at "
            "least this, so the index leg is bounded by the distance to the index region."
        )
    if failures:
        lines += ["", "Sources that failed during the probe:", ""]
        lines += [f"- `{name}`: {error}" for name, error in sorted(failures.items())]
    for scope in ["all", *sorted(s for s in summary if s != "all")]:
        lines += [
            "",
            f"## {'All sources' if scope == 'all' else scope}",
            "",
            "| stage | n | p50 ms | p95 ms | p99 ms |",
            "|---|---:|---:|---:|---:|",
        ]
        for stage in STAGES:
            row = summary[scope][stage]
            lines.append(
                f"| {STAGE_LABELS[stage]} | {int(row['n'] or 0)} | {_fmt(row['p50'])} | "
                f"{_fmt(row['p95'])} | {_fmt(row['p99'])} |"
            )
    return "\n".join(lines) + "\n"
