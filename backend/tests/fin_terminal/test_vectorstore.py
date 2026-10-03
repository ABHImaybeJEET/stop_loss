import asyncio
import json
from pathlib import Path

import httpx
import pytest

from fin_terminal.config import Settings
from fin_terminal.schemas import Document
from fin_terminal.vectorstore.factory import create_vectorstore
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter
from fin_terminal.vectorstore.weaviate import WeaviateVectorAdapter

FIXTURES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "vector_responses.json").read_text()
)


def test_weaviate_creates_collection_and_reuses_object_id(document: Document):
    requests = []
    exists = False

    def transport(request: httpx.Request):
        nonlocal exists
        requests.append(request)
        path = request.url.path
        if path == "/v1/schema/FinancialDocument":
            return httpx.Response(404, json=FIXTURES["weaviate_missing"])
        if path == "/v1/schema":
            assert json.loads(request.content)["vectorizer"] == "none"
            return httpx.Response(200, json=FIXTURES["weaviate_schema"])
        if path == "/v1/objects":
            exists = True
            return httpx.Response(200, json=FIXTURES["weaviate_object"])
        if path.startswith("/v1/objects/"):
            return httpx.Response(200 if exists else 404, json={})
        return httpx.Response(200)

    async def exercise():
        client = httpx.AsyncClient(
            base_url="https://example.invalid", transport=httpx.MockTransport(transport)
        )
        adapter = WeaviateVectorAdapter(client, "FinancialDocument")
        try:
            await adapter.upsert(document, [0.1, 0.2])
            await adapter.upsert(document, [0.1, 0.2])
            assert await adapter.health()
        finally:
            await adapter.close()
        assert client.is_closed

    asyncio.run(exercise())
    puts = [request for request in requests if request.method == "PUT"]
    assert len(puts) == 2 and puts[0].url == puts[1].url
    assert sum(request.url.path == "/v1/schema" for request in requests) == 1
    payload = json.loads(puts[0].content)
    assert payload["properties"]["content_hash"] == document.content_hash
    assert payload["vector"] == [0.1, 0.2]


def test_pinecone_upsert_is_stable_and_failures_propagate(document: Document):
    requests = []
    fail = False

    def transport(request):
        requests.append(request)
        if fail:
            return httpx.Response(429, json={"message": "rate limited"})
        key = "pinecone_upsert" if request.url.path == "/vectors/upsert" else "pinecone_stats"
        return httpx.Response(200, json=FIXTURES[key])

    async def exercise():
        nonlocal fail
        client = httpx.AsyncClient(
            base_url="https://example.invalid", transport=httpx.MockTransport(transport)
        )
        adapter = PineconeVectorAdapter(client, "fixture")
        try:
            await adapter.upsert(document, [0.1, 0.2])
            assert await adapter.health()
            fail = True
            with pytest.raises(httpx.HTTPStatusError):
                await adapter.upsert(document, [0.1, 0.2])
            assert not await adapter.health()
        finally:
            await adapter.close()

    asyncio.run(exercise())
    payload = json.loads(requests[0].content)
    assert payload["namespace"] == "fixture"
    assert payload["vectors"][0]["id"] == document.content_hash


def test_factory_and_missing_pinecone_settings(settings: Settings):
    async def exercise():
        adapter = create_vectorstore(settings.model_copy(update={"vector_backend": "weaviate"}))
        assert isinstance(adapter, WeaviateVectorAdapter)
        await adapter.close()

    asyncio.run(exercise())
    with pytest.raises(ValueError, match="PINECONE"):
        create_vectorstore(
            settings.model_copy(
                update={
                    "vector_backend": "pinecone",
                    "pinecone_host": "",
                    "pinecone_api_key": None,
                }
            )
        )
