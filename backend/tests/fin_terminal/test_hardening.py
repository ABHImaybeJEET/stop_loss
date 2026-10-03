import asyncio
import json
from datetime import timedelta

import httpx
import pytest

from fin_terminal.config import ConnectorPolicy
from fin_terminal.connectors.alphavantage import AlphaVantageMarketConnector
from fin_terminal.connectors.errors import ConnectorError, UnavailableError
from fin_terminal.connectors.factory import create_connectors
from fin_terminal.grounding import LastGoodCache, ToolSnapshot, require_provenance
from fin_terminal.schemas import utcnow


def test_live_missing_credentials_are_unavailable(settings):
    configured = settings.model_copy(update={"alpha_vantage_api_key": None, "fred_api_key": None})
    connectors = create_connectors(configured, live=True)
    for name in ("prices", "macro", "news_tariff"):
        with pytest.raises(UnavailableError):
            asyncio.run(connectors[name].fetch())
        assert asyncio.run(connectors[name].health_check()).status == "failed"


def test_provider_error_never_becomes_empty_success(settings):
    async def exercise():
        client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"Error Message": "bad symbol"})
        ))
        connector = AlphaVantageMarketConnector("offline-key", ["XOM"], client=client)
        connector.setup_http(settings)
        with pytest.raises(ConnectorError, match="provider_error"):
            await connector.fetch()
        assert (await connector.health_check()).status == "failed"
        await connector.close()
        assert not client.is_closed  # Injected resources are caller-owned.
        await client.aclose()
    asyncio.run(exercise())


def test_request_limits_apply_to_each_symbol_and_pool_is_reused(settings):
    async def exercise():
        calls = []
        def reply(request):
            calls.append(request.url.params["symbol"])
            return httpx.Response(200, json={"Global Quote": {"01. symbol": calls[-1]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
            connector = AlphaVantageMarketConnector("offline-key", ["A", "B"], client=client)
            connector.setup_http(settings)
            acquired = 0
            async def acquire():
                nonlocal acquired
                acquired += 1
            connector._guard.bucket.acquire = acquire
            assert len(await connector.fetch()) == 2
            assert acquired == 2 and calls == ["A", "B"]
    asyncio.run(exercise())


def test_shared_provider_quota_but_distinct_request_semaphores(settings):
    configured = settings.model_copy(update={"alpha_vantage_api_key": "offline-key"})
    connectors = create_connectors(configured, live=True)
    a, b = connectors["prices"], connectors["news_tariff"]
    assert a._guard.bucket is b._guard.bucket
    assert a._guard.semaphore is not b._guard.semaphore


def test_grounding_rejects_unsourced_and_marks_stale_without_inventing(document):
    cache = LastGoodCache()
    assert cache.read("news", 10).status == "unavailable"
    invalid = document.model_copy(update={"source_url": None, "raw_reference": None, "content_hash": ""})
    with pytest.raises(ValueError):
        require_provenance(invalid)
    cache.update("news", [document])
    cache.fail("news", "timeout")
    snapshot = cache.read("news", 10, now=utcnow() + timedelta(seconds=11))
    assert snapshot.status == "stale"
    assert snapshot.records[0].text == document.text
    with pytest.raises(ValueError):
        ToolSnapshot(source="news", status="unavailable", records=[document])


def test_connector_hard_timeout_is_typed_and_cancellable(settings):
    async def exercise():
        async def slow(request):
            await asyncio.sleep(10)
            return httpx.Response(200, json={})
        async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
            connector = AlphaVantageMarketConnector("offline-key", ["A"], client=client)
            configured = settings.model_copy(update={"connector_policies": {
                "alpha_vantage": ConnectorPolicy(timeout_seconds=0.02, retries=1)
            }})
            connector.setup_http(configured)
            with pytest.raises(TimeoutError):
                await connector.fetch()
    asyncio.run(exercise())
