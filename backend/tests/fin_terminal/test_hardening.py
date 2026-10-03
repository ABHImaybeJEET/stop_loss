import asyncio
from datetime import timedelta

import pytest

from fin_terminal.connectors.errors import UnavailableError
from fin_terminal.connectors.factory import create_connectors
from fin_terminal.grounding import LastGoodCache, ToolSnapshot, require_provenance
from fin_terminal.schemas import utcnow


def test_live_missing_credentials_are_unavailable(settings):
    configured = settings.model_copy(update={"alpha_vantage_api_key": None, "fred_api_key": None})
    connectors = create_connectors(configured, live=True)
    # yfinance is keyless so prices always creates a live connector;
    # FRED needs a key, so macro falls back to UnavailableConnector.
    from fin_terminal.connectors.unavailable import UnavailableConnector

    assert isinstance(connectors["macro"], UnavailableConnector)
    with pytest.raises(UnavailableError):
        asyncio.run(connectors["macro"].fetch())
    assert asyncio.run(connectors["macro"].health_check()).status == "failed"




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


