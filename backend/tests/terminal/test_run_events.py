import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_agents import RELIANCE, make_service
from test_api import USER, sse_events
from test_portfolio_mode import portfolio_request

from stop_loss.agents import graph as graph_module
from stop_loss.agents.event_stream import classify, evidence_ids, sources
from stop_loss.agents.models import AGENTS, ChatRequest
from stop_loss.agents.run_events import (
    RUN_EVENT,
    SCHEMA_PATH,
    FinalAnswer,
    NodeError,
    NodeFinished,
    NodeStarted,
    RunStarted,
    render_schema,
)
from stop_loss.api.app import create_app
from stop_loss.api.run_store import RunStore

NODES = [a[0] for a in AGENTS]


def ticker_request(**overrides: Any) -> ChatRequest:
    fields = {
        "thread_id": "thread0001",
        "message_id": "message0001",
        "prompt": "I hold Reliance for 6 months. How should I hedge?",
        "asset": RELIANCE,
    }
    return ChatRequest(**{**fields, **overrides})


async def collect(service, request: ChatRequest) -> list:
    return [e async for e in service.stream_events(request, user_id="user1", run_id="run0001")]


def assert_lifecycle(events: list) -> None:
    assert isinstance(events[0], RunStarted) and events[0].nodes == NODES
    assert isinstance(events[-1], FinalAnswer)
    assert sum(isinstance(e, FinalAnswer) for e in events) == 1
    started = [e.node for e in events if isinstance(e, NodeStarted)]
    finished = [e.node for e in events if isinstance(e, NodeFinished)]
    assert sorted(started) == sorted(finished) == sorted(NODES)
    assert started[0] == "coordinator" and finished[-1] == "audit"
    for node in NODES:  # every node starts before it finishes
        first = next(i for i, e in enumerate(events) if getattr(e, "node", None) == node)
        assert isinstance(events[first], NodeStarted)
    for event in events:  # round-trips through the published union
        assert RUN_EVENT.validate_python(event.model_dump(mode="json")) == event


@pytest.mark.asyncio
async def test_ticker_run_streams_node_lifecycle_and_grounded_answer(settings) -> None:
    service = make_service(settings)
    events = await collect(service, ticker_request())
    assert_lifecycle(events)
    finished = {e.node: e for e in events if isinstance(e, NodeFinished)}
    assert all(e.duration_ms >= 0 for e in finished.values())
    assert finished["market"].status == "ok" and finished["market"].outputs_summary
    assert finished["news"].sources and all(
        s.url.startswith("http") for s in finished["news"].sources
    )
    # The evidence catalog is built by the hedging agent.
    catalog = finished["hedging"].evidence_ids
    assert catalog and all(i.startswith("E") for i in catalog)
    # No vector index offline: analogs reports unavailable, the run continues degraded.
    assert finished["analogs"].status == "degraded"
    errors = [e for e in events if isinstance(e, NodeError)]
    assert [(e.node, e.degraded) for e in errors] == [("analogs", True)]
    started = {e.node: e for e in events if isinstance(e, NodeStarted)}
    assert started["coordinator"].inputs_summary.asset == "RELIANCE.NS"
    assert {"market", "news", "macro", "weather", "analogs"} <= set(
        started["quant"].inputs_summary.upstream
    )
    final = events[-1]
    assert final.status == "ok" and final.result_kind == "analysis" and final.text
    assert final.citations and {c.id for c in final.citations} <= set(catalog)
    trail = final.audit_trail
    assert trail.checked_numbers is not None and trail.unverified_numbers == []
    assert [n.node for n in trail.nodes][-1] == "audit" and len(trail.nodes) == len(NODES)
    assert "analogs" in trail.failed_agents
    await service.aclose()


@pytest.mark.asyncio
async def test_portfolio_run_streams_same_lifecycle(settings) -> None:
    service = make_service(settings)
    events = await collect(service, portfolio_request())
    assert_lifecycle(events)
    assert events[0].label == "PORTFOLIO" and events[0].mode == "portfolio"
    started = next(e for e in events if isinstance(e, NodeStarted))
    assert started.inputs_summary.holdings == 1
    final = events[-1]
    assert final.status == "ok" and final.result_kind == "portfolio" and final.text
    assert final.audit_trail.steps and final.audit_trail.trust_score is not None
    await service.aclose()


@pytest.mark.asyncio
async def test_raising_node_ends_run_with_node_error(settings, monkeypatch) -> None:
    real = graph_module.build_nodes

    def broken(kit):
        nodes = real(kit)

        async def quant(state):
            raise RuntimeError("secret internals")

        return {**nodes, "quant": quant}

    monkeypatch.setattr(graph_module, "build_nodes", broken)
    service = make_service(settings)
    events = await collect(service, ticker_request())
    errors = [e for e in events if isinstance(e, NodeError) and not e.degraded]
    assert [e.node for e in errors] == ["quant"]
    assert errors[0].error == "RuntimeError"  # never echoes the exception message
    assert "quant" not in {e.node for e in events if isinstance(e, NodeFinished)}
    final = events[-1]
    assert isinstance(final, FinalAnswer) and final.status == "failed"
    assert final.error == "RuntimeError" and final.text is None
    await service.aclose()


def test_output_helpers_are_generic() -> None:
    update = {
        "news": {
            "status": "ok",
            "data": [
                {"title": "Oil jumps", "url": "https://x.test/a", "publisher": "Wire"},
                {"title": "dup", "url": "https://x.test/a", "publisher": "Wire"},
                {"title": "no link", "url": None},
            ],
        }
    }
    assert classify(update) == ("ok", {"news": "ok · 3 items"}, [])
    assert [s.url for s in sources(update)] == ["https://x.test/a"]
    status, _, failures = classify({"macro": {"status": "unavailable", "error": "rate_limited"}})
    assert status == "degraded" and failures == ["macro: unavailable (rate_limited)"]
    assert classify({"narrative": {"status": "skipped"}})[0] == "skipped"
    assert classify({"result": None})[0] == "skipped"
    nested = {"x": [{"id": "E2", "display": "1%"}, {"evidence_ids": ["E1", "E2"]}, {"id": "E9"}]}
    assert evidence_ids(nested) == ["E2", "E1"]


def test_run_store_is_idempotent_and_durable(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    store = RunStore(path)
    store.create(
        run_id="r1",
        user_id="u1",
        mode="ticker",
        thread_id="thread0001",
        message_id="message0001",
        label="RELIANCE.NS",
        started_at="2026-10-04T00:00:00+00:00",
    )
    event = FinalAnswer(run_id="r1", ts="2026-10-04T00:00:01+00:00", status="no_result")
    payload = event.model_dump(mode="json")
    store.append("r1", payload)
    store.append("r1", payload)  # retried write
    store.finish("r1", "no_result", "2026-10-04T00:00:02+00:00")
    store.close()
    reopened = RunStore(path)
    record = reopened.get("r1", "u1")
    assert record is not None and record.status == "no_result" and record.events == [event]
    assert reopened.get("r1", "someone-else") is None
    reopened.close()


def test_runs_endpoint_streams_persists_and_replays(settings) -> None:
    app = create_app(settings, make_service(settings))
    body = {
        "thread_id": "thread0002",
        "message_id": "message0002",
        "prompt": "How risky is this?",
        "asset": RELIANCE,
    }
    with TestClient(app) as client:
        response = client.post("/runs", json=body, headers=USER)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = sse_events(response.text)
        assert events[0]["type"] == "run_started" and events[-1]["type"] == "final_answer"
        assert [e["seq"] for e in events] == list(range(len(events)))
        run_id = events[0]["run_id"]
        replay = client.get(f"/runs/{run_id}", headers=USER)
        assert replay.status_code == 200
        record = replay.json()
        assert record["status"] == "completed" and record["label"] == "RELIANCE.NS"
        assert record["events"] == events
        assert client.get(f"/runs/{run_id}", headers={"X-User-Id": "other"}).status_code == 404
        assert client.get("/runs/missing", headers=USER).status_code == 404
        # The legacy /chat stream is unchanged.
        legacy = sse_events(client.post("/chat", json=body, headers=USER).text)
        assert legacy[0]["type"] == "run_started" and legacy[-1]["type"] == "final"
    # Durable across app restarts.
    with TestClient(create_app(settings, make_service(settings))) as client:
        assert client.get(f"/runs/{run_id}", headers=USER).json()["events"] == events


def test_frontend_schema_is_current() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == render_schema(), (
        "run python -m stop_loss.agents.run_events"
    )
    schema = json.loads(render_schema())
    assert {"RunRecord", "NodeFinished", "FinalAnswer"} <= set(schema["$defs"])
    assert schema["discriminator"]["propertyName"] == "type"
