"""Typed SSE contract for graph runs streamed through LangGraph `astream_events`.

Every model the `/runs` stream and replay endpoints emit lives here. Regenerate the frontend
JSON schema after changing any of them: `python -m stop_loss.agents.run_events`."""

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter

from stop_loss.agents.models import AgentId, EvidenceItem, Wire
from stop_loss.agents.portfolio_models import AuditStep

RunMode = Literal["ticker", "portfolio"]
# ok: the node produced its outputs; degraded: it finished with failed/unavailable inputs;
# skipped: it had nothing to do (e.g. no market data to narrate).
NodeStatus = Literal["ok", "degraded", "skipped"]
FinalStatus = Literal["ok", "no_result", "failed", "cancelled"]
RunStatus = Literal["running", "completed", "no_result", "failed", "cancelled"]
SCHEMA_PATH = Path(__file__).parents[4] / "frontend" / "types" / "run-events.schema.json"


class SourceRef(Wire):
    url: str
    title: str | None = None
    publisher: str | None = None
    published_at: str | None = None


class InputsSummary(Wire):
    mode: RunMode
    asset: str | None = None
    holdings: int | None = None
    prompt_chars: int
    # Upstream state already populated for this run: key -> status (or "ready").
    upstream: dict[str, str] = Field(default_factory=dict)


class NodeAudit(Wire):
    node: AgentId
    status: NodeStatus
    duration_ms: float
    evidence_ids: list[str] = Field(default_factory=list)


class AuditTrail(Wire):
    checked_numbers: int | None = None
    unverified_numbers: list[str] = Field(default_factory=list)
    failed_agents: list[str] = Field(default_factory=list)
    partial: bool = False
    trust_score: float | None = None
    nodes: list[NodeAudit] = Field(default_factory=list)
    steps: list[AuditStep] = Field(default_factory=list)


class RunEventBase(Wire):
    run_id: str
    seq: int = Field(default=0, ge=0)
    ts: str


class RunStarted(RunEventBase):
    type: Literal["run_started"] = "run_started"
    mode: RunMode
    thread_id: str
    message_id: str
    label: str
    langsmith_run_id: str | None = None
    llm_enabled: bool
    nodes: list[AgentId]


class NodeStarted(RunEventBase):
    type: Literal["node_started"] = "node_started"
    node: AgentId
    inputs_summary: InputsSummary


class NodeFinished(RunEventBase):
    type: Literal["node_finished"] = "node_finished"
    node: AgentId
    duration_ms: float
    outputs_summary: dict[str, str] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    status: NodeStatus


class NodeError(RunEventBase):
    type: Literal["node_error"] = "node_error"
    node: AgentId
    # True: the node reported failed inputs and the run continued with partial data.
    # False: the node raised and the run stopped.
    degraded: bool
    error: str | None = None


class FinalAnswer(RunEventBase):
    type: Literal["final_answer"] = "final_answer"
    status: FinalStatus
    result_kind: Literal["analysis", "reply", "portfolio"] | None = None
    text: str | None = None
    citations: list[EvidenceItem] = Field(default_factory=list)
    audit_trail: AuditTrail = Field(default_factory=AuditTrail)
    error: str | None = None


RunEvent = Annotated[
    RunStarted | NodeStarted | NodeFinished | NodeError | FinalAnswer,
    Field(discriminator="type"),
]
RUN_EVENT = TypeAdapter(RunEvent)


class RunRecord(Wire):
    run_id: str
    mode: RunMode
    thread_id: str
    message_id: str
    label: str
    status: RunStatus
    started_at: str
    finished_at: str | None = None
    events: list[RunEvent] = Field(default_factory=list)


def json_schema() -> dict[str, Any]:
    """One document: the root validates a single stream event; `$defs.RunRecord` is the
    replay payload of GET /runs/{id}."""
    template = "#/$defs/{model}"
    schema = RUN_EVENT.json_schema(mode="serialization", ref_template=template)
    record = RunRecord.model_json_schema(mode="serialization", ref_template=template)
    schema["$defs"] = {**schema.get("$defs", {}), **record.pop("$defs", {}), "RunRecord": record}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "StopLossRunEvent",
        **schema,
    }


def render_schema() -> str:
    return json.dumps(json_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(render_schema(), encoding="utf-8", newline="\n")
    print(f"wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
