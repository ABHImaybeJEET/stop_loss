from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_agents import make_service

from stop_loss.agents.models import ChatRequest
from stop_loss.agents.portfolio_llm import heuristic_portfolio_plan
from stop_loss.agents.portfolio_models import PortfolioResult
from stop_loss.agents.portfolio_nodes import region_box
from stop_loss.analytics.event_windows import aggregate, forward_return


def portfolio_request(**overrides: Any) -> ChatRequest:
    fields: dict[str, Any] = {
        "thread_id": "pfthread01",
        "message_id": "pfmessage01",
        "mode": "portfolio",
        "prompt": "How will a Category 4 cyclone in the Bay of Bengal affect my energy holdings?",
        "holdings": [{"symbol": "RELIANCE.NS", "quantity": 10}],
    }
    return ChatRequest(**{**fields, **overrides})


def test_request_scope_validation() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(thread_id="pfthread01", message_id="pfmessage01", prompt="x")  # no asset
    with pytest.raises(ValidationError):
        ChatRequest(
            thread_id="pfthread01",
            message_id="pfmessage01",
            prompt="x",
            mode="portfolio",
            holdings=[],
        )
    with pytest.raises(ValidationError):
        portfolio_request(holdings=[{"symbol": "AAPL", "quantity": 1}])
    merged = portfolio_request(
        holdings=[{"symbol": "tcs.ns", "quantity": 2}, {"symbol": "TCS.NS", "quantity": 3}]
    )
    assert [(h.symbol, h.quantity) for h in merged.holdings] == [("TCS.NS", 5)]


def test_heuristic_plan_and_regions() -> None:
    holdings = [{"symbol": "BPCL.NS", "sector": "Energy"}, {"symbol": "TCS.NS"}]
    plan = heuristic_portfolio_plan(
        "Will a Category 4 hurricane in the Gulf of Mexico hit BPCL and my energy stocks?", holdings
    )
    assert plan.event_kind == "cyclone" and plan.event_severity == "Category 4"
    assert plan.event_region == "Gulf Of Mexico" and "Energy" in plan.target_sectors
    assert plan.target_symbols == ["BPCL.NS"]
    assert region_box("Bay of Bengal") == (5, 24, 78, 100) and region_box("Atlantis") is None


def test_forward_returns_from_local_files(tmp_path: Path) -> None:
    (tmp_path / "nse_historical").mkdir()
    rows = "\n".join(f"2020-01-{d:02d} 00:00:00+00:00,{100 + d}" for d in range(1, 25))
    (tmp_path / "nse_historical" / "ABC.NS.csv").write_text(f"Date,Close\n{rows}\n")
    r5 = forward_return("ABC.NS", date(2020, 1, 1), 5, tmp_path)
    assert r5 == pytest.approx(106 / 101 - 1)
    assert forward_return("ABC.NS", date(2020, 1, 22), 5, tmp_path) is None  # window not covered
    assert forward_return("ABC.NS", date(2019, 6, 1), 5, tmp_path) is None  # no nearby session
    assert forward_return("MISSING.NS", date(2020, 1, 1), 5, tmp_path) is None
    agg = aggregate([1.0, -2.0, None, 3.0])
    assert agg["n"] == 3 and agg["median"] == 1.0 and agg["share_negative"] == pytest.approx(1 / 3)


@pytest.mark.asyncio
async def test_portfolio_run_streams_sections_and_grounded_result(settings) -> None:
    service = make_service(settings)
    events = [
        e async for e in service.stream(portfolio_request(), user_id="user1", run_id="run0001")
    ]
    assert events[0]["type"] == "run_started"
    sections = {e["section"] for e in events if e["type"] == "portfolio_section"}
    assert {"portfolio", "sentiment", "event", "exposure"} <= sections
    final = events[-1]
    assert final["type"] == "portfolio_final"
    result = PortfolioResult.model_validate(final["result"])
    assert result.narrative_source == "rules"  # no LLM in tests
    assert "analogs" in result.failed_agents  # no vector index configured offline
    assert result.portfolio.holdings[0].value is not None
    assert result.recommendations and result.bottom_line
    assert result.audit.unverified_numbers == []  # rules text only quotes evidence
    assert [s.agent for s in result.steps][:3] == ["coordinator", "market", "news"]
    # No analog scenario is produced without >= 3 measured parallels.
    assert all(r.scenario_impact is None for r in result.exposure.rows)
    await service.aclose()
