"""Translates LangGraph `astream_events` (v2) into the typed run events in `run_events.py`.

It only observes the graph: node functions, state and the custom stream are untouched."""

import re
import time
from typing import Any

from stop_loss.agents.models import AGENTS, AnalysisResult, EvidenceItem, TextReply
from stop_loss.agents.portfolio_models import PortfolioResult
from stop_loss.agents.reporting import now_iso
from stop_loss.agents.run_events import (
    AuditTrail,
    FinalAnswer,
    InputsSummary,
    NodeAudit,
    NodeError,
    NodeFinished,
    NodeStarted,
    NodeStatus,
    RunEvent,
    RunMode,
    SourceRef,
)

NODES = {agent_id for agent_id, _, _ in AGENTS}
UPSTREAM_KEYS = ("plan", "market", "news", "macro", "weather", "analogs", "quant", "narrative")
FAILED = {"unavailable", "error", "not_found"}
EVIDENCE_ID = re.compile(r"^E\d+$")
EVIDENCE_REF = re.compile(r"\bE\d+\b")
MAX_SOURCES = 50
MAX_DEPTH = 8


def _status_word(value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("status"), str):
        return value["status"]
    return "ready"


def summarize_inputs(state: dict[str, Any], mode: RunMode) -> InputsSummary:
    asset = state.get("asset") or {}
    holdings = state.get("holdings")
    return InputsSummary(
        mode=mode,
        asset=asset.get("symbol"),
        holdings=len(holdings) if isinstance(holdings, list) else None,
        prompt_chars=len(state.get("user_prompt") or ""),
        upstream={k: _status_word(state[k]) for k in UPSTREAM_KEYS if state.get(k) is not None},
    )


def _describe(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, dict) and isinstance(value.get("status"), str):
        text = value["status"]
        if value.get("error"):
            text += f" ({value['error']})"
        data = value.get("data")
        if isinstance(data, list):
            text += f" · {len(data)} items"
        return text
    if isinstance(value, dict):
        return f"{len(value)} fields"
    if isinstance(value, list):
        return f"{len(value)} items"
    text = str(value)
    return text if len(text) <= 80 else f"{text[:77]}..."


def classify(update: dict[str, Any]) -> tuple[NodeStatus, dict[str, str], list[str]]:
    """Returns (status, per-key summary, failure descriptions) for one node's state update."""
    summary = {key: _describe(value) for key, value in update.items()}
    values = [v for k, v in update.items() if k != "messages"]
    failures = [
        f"{key}: {_describe(value)}"
        for key, value in update.items()
        if isinstance(value, dict) and value.get("status") in FAILED
    ]
    if failures:
        return "degraded", summary, failures
    skipped = all(
        v is None or (isinstance(v, dict) and v.get("status") == "skipped") for v in values
    )
    return ("skipped" if values and skipped else "ok"), summary, []


def _walk(value: Any, depth: int = 0):
    if depth > MAX_DEPTH:
        return
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child, depth + 1)


def evidence_ids(value: Any) -> list[str]:
    found: dict[str, None] = {}
    for node in _walk(value):
        refs = node.get("evidence_ids")
        if isinstance(refs, list):
            found.update((r, None) for r in refs if isinstance(r, str))
        item_id = node.get("id")
        if isinstance(item_id, str) and EVIDENCE_ID.match(item_id) and "display" in node:
            found[item_id] = None
    return list(found)


def sources(value: Any) -> list[SourceRef]:
    found: dict[str, SourceRef] = {}
    for node in _walk(value):
        url = node.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        title = node.get("title") or node.get("label")
        publisher = node.get("publisher") or node.get("source")
        if url in found or not (title or publisher):
            continue
        published = node.get("published_at") or node.get("observed_at")
        found[url] = SourceRef(
            url=url,
            title=str(title) if title else None,
            publisher=str(publisher) if publisher else None,
            published_at=str(published) if published else None,
        )
        if len(found) >= MAX_SOURCES:
            break
    return list(found.values())


def _citations(evidence: list[EvidenceItem], refs: set[str]) -> list[EvidenceItem]:
    return [e for e in evidence if e.id in refs]


def final_answer(run_id: str, state: dict[str, Any] | None, nodes: list[NodeAudit]) -> FinalAnswer:
    result = (state or {}).get("result")
    if not result:
        return FinalAnswer(
            run_id=run_id, ts=now_iso(), status="no_result", audit_trail=AuditTrail(nodes=nodes)
        )
    if result.get("kind") == "portfolio":
        pf = PortfolioResult.model_validate(result)
        refs = {i for r in pf.recommendations for i in r.evidence_ids}
        refs |= set(EVIDENCE_REF.findall(pf.bottom_line))
        kind, text, citations = "portfolio", pf.bottom_line, _citations(pf.evidence, refs)
        audit, failed, partial = pf.audit, pf.failed_agents, pf.partial
        trust, steps = pf.risk.trust_score, pf.steps
    elif "content" in result:
        reply = TextReply.model_validate(result)
        kind, text, citations = "reply", reply.content, reply.evidence  # already the cited set
        audit, failed, partial, trust, steps = reply.audit, [], False, None, []
    else:
        an = AnalysisResult.model_validate(result)
        refs = {i for s in an.suggestions.items for i in s.evidence_ids}
        refs |= set(EVIDENCE_REF.findall(an.executive_answer or ""))
        kind, text, citations = "analysis", an.executive_answer, _citations(an.evidence, refs)
        audit, failed, partial = an.audit, an.failed_agents, an.partial
        trust, steps = an.risk.trust_score, []
    return FinalAnswer(
        run_id=run_id,
        ts=now_iso(),
        status="ok",
        result_kind=kind,
        text=text,
        citations=citations,
        audit_trail=AuditTrail(
            checked_numbers=audit.checked_numbers,
            unverified_numbers=audit.unverified_numbers,
            failed_agents=failed,
            partial=partial,
            trust_score=trust,
            nodes=nodes,
            steps=steps,
        ),
    )


class GraphEventTranslator:
    """Stateful per run: pairs node start/end events and keeps the final graph state."""

    def __init__(self, run_id: str, mode: RunMode) -> None:
        self.run_id = run_id
        self.mode = mode
        self._root: str | None = None
        self._running: dict[str, tuple[str, float]] = {}  # LangChain run id -> (node, t0)
        self.nodes: list[NodeAudit] = []
        self.final_state: dict[str, Any] | None = None

    def translate(self, event: dict[str, Any]) -> list[RunEvent]:
        kind = event.get("event")
        parents = event.get("parent_ids") or []
        data = event.get("data") or {}
        if not parents:  # the graph itself
            if kind == "on_chain_start":
                self._root = event.get("run_id")
            elif kind == "on_chain_end" and isinstance(data.get("output"), dict):
                self.final_state = data["output"]
            return []
        node = (event.get("metadata") or {}).get("langgraph_node")
        # Only the node runnables themselves: direct children of the graph run.
        if node not in NODES or event.get("name") != node or parents[-1] != self._root:
            return []
        if kind == "on_chain_start":
            self._running[event["run_id"]] = (node, time.perf_counter())
            state = data.get("input") if isinstance(data.get("input"), dict) else {}
            return [
                NodeStarted(
                    run_id=self.run_id,
                    ts=now_iso(),
                    node=node,
                    inputs_summary=summarize_inputs(state, self.mode),
                )
            ]
        if kind != "on_chain_end" or event["run_id"] not in self._running:
            return []
        _, started = self._running.pop(event["run_id"])
        duration = round((time.perf_counter() - started) * 1000, 2)
        update = data.get("output") if isinstance(data.get("output"), dict) else {}
        status, summary, failures = classify(update)
        ids = evidence_ids(update)
        self.nodes.append(
            NodeAudit(node=node, status=status, duration_ms=duration, evidence_ids=ids)
        )
        out: list[RunEvent] = []
        if failures:
            out.append(
                NodeError(
                    run_id=self.run_id,
                    ts=now_iso(),
                    node=node,
                    degraded=True,
                    error="; ".join(failures),
                )
            )
        out.append(
            NodeFinished(
                run_id=self.run_id,
                ts=now_iso(),
                node=node,
                duration_ms=duration,
                outputs_summary=summary,
                evidence_ids=ids,
                sources=sources(update),
                status=status,
            )
        )
        return out

    def finish(self) -> FinalAnswer:
        return final_answer(self.run_id, self.final_state, self.nodes)

    def fail(self, exc: BaseException) -> list[RunEvent]:
        """A node raised: the run stops. Nodes still in flight are reported as errors."""
        message = type(exc).__name__  # like /chat: never echo internals to the client
        out: list[RunEvent] = [
            NodeError(run_id=self.run_id, ts=now_iso(), node=node, degraded=False, error=message)
            for node, _ in self._running.values()
        ]
        self._running.clear()
        out.append(
            FinalAnswer(
                run_id=self.run_id,
                ts=now_iso(),
                status="failed",
                error=message,
                audit_trail=AuditTrail(nodes=self.nodes),
            )
        )
        return out
