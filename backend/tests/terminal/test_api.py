import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_agents import RELIANCE, make_service

from stop_loss.api.app import create_app

USER = {"X-User-Id": "user-1"}


def sse_events(text: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def client(settings):
    app = create_app(settings, make_service(settings))
    with TestClient(app) as test_client:
        yield test_client


def chat(client: TestClient, **overrides: Any):
    body = {
        "thread_id": "thread0001",
        "message_id": "message0001",
        "prompt": "How risky is this?",
        "asset": RELIANCE,
        **overrides,
    }
    return client.post("/chat", json=body, headers=USER)


def test_health_reports_llm_state(client) -> None:
    assert client.get("/health").json() == {"status": "ok", "llm_enabled": False, "model": None}


def test_chat_streams_sse_through_final_result(client) -> None:
    response = chat(client)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response.text)
    assert events[0]["type"] == "run_started"
    assert [e["seq"] for e in events] == list(range(len(events)))
    assert events[-1]["type"] == "final"
    run_id = events[0]["run_id"]
    # Resume after a dropped connection replays only what the client has not seen.
    replay = sse_events(client.get(f"/chat/runs/{run_id}/events?after=5", headers=USER).text)
    assert replay[0]["seq"] == 6 and replay[-1]["type"] == "final"
    # Runs are private to the user who started them.
    other = client.get(f"/chat/runs/{run_id}/events", headers={"X-User-Id": "someone-else"})
    assert other.status_code == 404


def test_chat_requires_user_and_validates_input(client) -> None:
    body = {
        "thread_id": "thread0001",
        "message_id": "message0001",
        "prompt": "x",
        "asset": RELIANCE,
    }
    assert client.post("/chat", json=body).status_code == 422
    assert chat(client, prompt="").status_code == 422
    assert chat(client, asset={"symbol": "BAD SYMBOL!", "name": "x"}).status_code == 422


def test_internal_token_is_enforced(settings) -> None:
    settings = settings.model_copy(update={"api_internal_token": "s3cret"})
    app = create_app(settings, make_service(settings))
    with TestClient(app) as test_client:
        assert test_client.get("/health").status_code == 401
        ok = test_client.get("/health", headers={"X-Internal-Token": "s3cret"})
        assert ok.status_code == 200


def test_market_endpoints(client) -> None:
    chart = client.get(
        "/market/chart", params={"symbol": "RELIANCE.NS", "range": "5y", "interval": "1d"}
    )
    assert chart.status_code == 200 and len(chart.json()["bars"]) > 1000
    bad = client.get("/market/chart", params={"symbol": "RELIANCE.NS", "range": "7y"})
    assert bad.status_code == 422
    missing = client.get(
        "/market/chart", params={"symbol": "NOTAREALTICKERXYZ", "range": "5y", "interval": "1d"}
    )
    assert missing.status_code == 404 and missing.json()["detail"] == "symbol_not_found"
    results = client.get("/assets/search", params={"q": "reliance"}).json()["results"]
    assert results[0]["symbol"] == "RELIANCE.NS"


def test_feedback_upsert_edit_and_undo(client) -> None:
    body = {
        "thread_id": "thread0001",
        "message_id": "message0001",
        "rating": "up",
        "tags": ["Accurate"],
        "comment": "useful",
    }
    first = client.post("/feedback", json=body, headers=USER)
    assert first.status_code == 200 and first.json()["rating"] == "up"
    edited = client.post(
        "/feedback", json={**body, "rating": "down", "tags": ["Too vague"]}, headers=USER
    ).json()
    assert edited["rating"] == "down" and edited["created_at"] == first.json()["created_at"]
    assert client.get("/feedback/message0001", headers=USER).json()["tags"] == ["Too vague"]
    assert (
        client.post("/feedback", json={**body, "tags": ["Bogus"]}, headers=USER).status_code == 422
    )
    assert client.delete("/feedback/message0001", headers=USER).json() == {"removed": True}
    assert client.get("/feedback/message0001", headers=USER).status_code == 404


def test_news_feed_uses_live_shapes(client) -> None:
    feed = client.get("/news/feed").json()
    assert set(feed) == {"topStories", "commodities", "indianStocks"}
    assert feed["topStories"] and all(a["url"].startswith("http") for a in feed["topStories"])
    assert feed["indianStocks"][0]["priceInr"]
