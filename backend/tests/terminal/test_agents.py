from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from terminal_fixtures import load_json, load_text

import stop_loss.agents.nodes as nodes
from fin_terminal.connectors.errors import ConnectorError
from fin_terminal.schemas import MacroIndicator
from stop_loss.agents.audit import extract_figures, verify_figures
from stop_loss.agents.llm import NarrativeDraft, QueryPlan, ReplyDraft, SuggestionDraft
from stop_loss.agents.models import AGENTS, AnalysisResult, ChatRequest, EvidenceItem, TextReply
from stop_loss.agents.service import AnalysisService
from stop_loss.analytics.macro import macro_flags, summarize_series
from stop_loss.analytics.models import MacroSnapshot
from stop_loss.analytics.news import NewsClient
from stop_loss.analytics.weather import WeatherClient
from stop_loss.analytics.yahoo import YahooFinanceClient

RELIANCE = {"symbol": "RELIANCE.NS", "name": "Reliance Industries Limited", "exchange": "NSE"}


def provider_transport(*, fail_news: bool = False) -> httpx.MockTransport:
    """Replays recorded real responses; anything unrecognized is a 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "fc.yahoo.com":
            return httpx.Response(404)
        if path.endswith("/getcrumb"):
            return httpx.Response(200, text="testcrumb")
        if "/v8/finance/chart/" in path:
            symbol = path.rsplit("/", 1)[-1]
            name = {
                "RELIANCE.NS": "yahoo_chart_reliance_5y_1d.json",
                "%5ENSEI": "yahoo_chart_nsei_5y_1d.json",
                "^NSEI": "yahoo_chart_nsei_5y_1d.json",
            }.get(symbol)
            return httpx.Response(200, json=load_json(name or "yahoo_chart_unknown.json"))
        if "/quoteSummary/" in path:
            if "RELIANCE" in path:
                return httpx.Response(200, json=load_json("yahoo_quote_summary_reliance.json"))
            return httpx.Response(404, json={"quoteSummary": {"result": None, "error": {}}})
        if path.endswith("/v1/finance/search"):
            if fail_news:
                return httpx.Response(503)
            return httpx.Response(200, json=load_json("yahoo_search_reliance.json"))
        if host == "news.google.com":
            if fail_news:
                return httpx.Response(503)
            return httpx.Response(200, text=load_text("google_news_reliance.xml"))
        if host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json=load_json("openmeteo_geocode_mumbai.json"))
        if host == "api.open-meteo.com":
            return httpx.Response(200, json=load_json("openmeteo_forecast_mumbai.json"))
        return httpx.Response(404)

    return httpx.MockTransport(handler)


class FixtureMacro:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def snapshot(self) -> MacroSnapshot:
        if self.fail:
            raise ConnectorError("fred_down")
        rec = MacroIndicator(
            source="macro",
            provider="fred",
            series_id="DCOILWTICO",
            value=96.16,
            unit="USD/bbl",
            observed_at=datetime(2026, 9, 29, tzinfo=UTC),
            source_url="https://fred.stlouisfed.org/series/DCOILWTICO",
            fetched_at=datetime.now(UTC),
            ingest_run_id="t",
        )
        views = [summarize_series("DCOILWTICO", [rec])]
        return MacroSnapshot(indicators=views, flags=macro_flags(views))

class FixtureYahoo:
    async def chart(self, symbol: str, range_: str, interval: str):
        from stop_loss.analytics.yahoo_parsers import parse_chart
        name = {
            "RELIANCE.NS": "yahoo_chart_reliance_5y_1d.json",
            "%5ENSEI": "yahoo_chart_nsei_5y_1d.json",
            "^NSEI": "yahoo_chart_nsei_5y_1d.json",
        }.get(symbol, "yahoo_chart_unknown.json")
        payload = load_json(name)
        return parse_chart(payload, symbol, range_, interval)

    async def quote(self, symbol: str):
        # We can just return the same 1d chart fixture for quotes
        return await self.chart(symbol, "1d", "1m")

    async def profile(self, symbol: str):
        from stop_loss.analytics.yahoo_parsers import parse_quote_summary, SymbolNotFoundError
        if "RELIANCE" in symbol:
            return parse_quote_summary(load_json("yahoo_quote_summary_reliance.json"), symbol)
        raise SymbolNotFoundError(symbol)

    async def search(self, query: str, quotes: int = 8, news: int = 0):
        from stop_loss.analytics.yahoo_parsers import parse_search
        payload = load_json("yahoo_search_reliance.json")
        matches, articles = parse_search({"quotes": payload.get("quotes", []), "news": []})
        from stop_loss.symbols import is_nse_symbol
        return ([m for m in matches if is_nse_symbol(m.symbol)][:quotes], articles)

    async def aclose(self):
        pass


def make_service(settings, *, fail_news: bool = False, fail_macro: bool = False):
    client = httpx.AsyncClient(transport=provider_transport(fail_news=fail_news))
    return AnalysisService(
        settings,
        yahoo=FixtureYahoo(),
        news=NewsClient(settings, client),
        macro=FixtureMacro(fail_macro),
        weather=WeatherClient(settings, client),
        use_llm=False,
        checkpointer=InMemorySaver(),
    )


async def run(
    service: AnalysisService,
    prompt: str,
    asset: dict[str, Any] = RELIANCE,
    thread: str = "thread0001",
    message: str = "message0001",
) -> list[dict[str, Any]]:
    request = ChatRequest(thread_id=thread, message_id=message, prompt=prompt, asset=asset)
    return [e async for e in service.stream(request, user_id="user1", run_id="run0001")]


@pytest.mark.asyncio
async def test_full_analysis_streams_agents_sections_and_grounded_result(settings) -> None:
    service = make_service(settings)
    events = await run(service, "I hold Reliance for 6 months. How should I hedge?")
    assert events[0]["type"] == "run_started"
    queued = [e for e in events[1:9]]
    assert [e["agent_id"] for e in queued] == [a[0] for a in AGENTS]
    assert all(e["status"] == "queued" for e in queued)
    done = {e["agent_id"] for e in events if e.get("status") == "done"}
    assert done == {a[0] for a in AGENTS}
    sections = [e["section"] for e in events if e["type"] == "section"]
    assert set(sections) == {"snapshot", "sources", "historical", "risk"}
    final = events[-1]
    assert final["type"] == "final"
    result = AnalysisResult.model_validate(final["result"])
    assert result.narrative_source == "rules" and not result.partial
    assert result.snapshot.price == 1167.7 and result.snapshot.summary
    assert result.risk.risk_score is not None and result.risk.trust_score is not None
    assert result.historical.metrics and result.suggestions.items
    ids = {e.id for e in result.evidence}
    assert all(set(s.evidence_ids) <= ids for s in result.suggestions.items)
    # The deterministic narrative only quotes catalog figures, so the audit finds nothing.
    assert result.audit.unverified_numbers == []
    assert settings.evidence_path.read_text(encoding="utf-8").count("agent:") >= 8
    await service.aclose()


@pytest.mark.asyncio
async def test_unknown_symbol_reports_unrecoverable_error(settings) -> None:
    service = make_service(settings)
    asset = {"symbol": "NOTAREALTICKERXYZ.NS", "name": "Nothing", "exchange": None}
    events = await run(service, "analyze", asset)
    assert not [e for e in events if e["type"] == "final"]
    error = events[-1]
    assert error["type"] == "error" and error["recoverable"] is False
    market = [e for e in events if e.get("agent_id") == "market" and e["status"] == "error"]
    assert market and "delisted" in market[0]["message"]


@pytest.mark.asyncio
async def test_failed_streams_degrade_to_partial_result(settings) -> None:
    service = make_service(settings, fail_news=True, fail_macro=True)
    events = await run(service, "risk?")
    result = AnalysisResult.model_validate(events[-1]["result"])
    assert result.partial and set(result.failed_agents) == {"news", "macro"}
    assert result.sources.items == [] and result.snapshot.price == 1167.7
    errored = {e["agent_id"] for e in events if e.get("status") == "error"}
    assert errored == {"news", "macro"}


@pytest.mark.asyncio
async def test_follow_up_reply_keeps_thread_memory(settings, monkeypatch) -> None:
    service = make_service(settings)
    await run(service, "Give me a full analysis", message="message0001")

    async def plan(*_: Any, **__: Any) -> QueryPlan:
        return QueryPlan(mode="reply", intent="what-if", horizon="6 months", position="long")

    seen_history: list[list[str]] = []

    async def reply(_model, *, prompt, asset, history, evidence) -> ReplyDraft:
        seen_history.append(history)
        price = next(e for e in evidence if e.label == "Last price")
        return ReplyDraft(
            markdown=f"Holding 6 months: last price {price.display} [{price.id}].",
            evidence_ids=[price.id],
        )

    monkeypatch.setattr(nodes, "plan_query", plan)
    monkeypatch.setattr(nodes, "write_reply", reply)
    service.kit.llm = object()  # any non-None model enables the LLM path (calls are patched)
    events = await run(service, "What if I hold 6 months?", message="message0002")
    assert events[-1]["type"] == "reply", events[-4:]
    reply_payload = TextReply.model_validate(events[-1]["reply"])
    assert reply_payload.audit.unverified_numbers == []
    assert reply_payload.evidence and reply_payload.evidence[0].label == "Last price"
    assert any("Give me a full analysis" in line for line in seen_history[0])
    assert not [e for e in events if e["type"] == "section"]


@pytest.mark.asyncio
async def test_first_look_at_asset_forces_full_analysis(settings, monkeypatch) -> None:
    service = make_service(settings)
    service.kit.llm = object()

    async def plan(*_: Any, **__: Any) -> QueryPlan:
        return QueryPlan(mode="reply", intent="x")

    monkeypatch.setattr(nodes, "plan_query", plan)
    monkeypatch.setattr(nodes, "classify_headlines", lambda *a, **k: _none())
    monkeypatch.setattr(nodes, "write_narrative", lambda *a, **k: _none())
    events = await run(service, "and this one?")
    assert events[-1]["type"] == "final"
    assert events[-1]["result"]["narrative_source"] == "rules"  # LLM failure falls back


@pytest.mark.asyncio
async def test_audit_flags_invented_figures(settings, monkeypatch) -> None:
    async def narrative(*_: Any, **__: Any) -> NarrativeDraft:
        return NarrativeDraft(
            snapshot_summary="Trades at ₹1,167.70 [E1].",
            sources_summary="Mixed news.",
            historical_summary="Volatile.",
            suggestions=[
                SuggestionDraft(
                    action="Buy",
                    rationale="Target ₹2,400 by March.",
                    confidence=0.9,
                    evidence_ids=["E1", "E999"],
                )
            ],
        )

    monkeypatch.setattr(nodes, "write_narrative", narrative)
    service = make_service(settings)
    service.kit.llm = object()
    monkeypatch.setattr(nodes, "plan_query", lambda *a, **k: _none())
    monkeypatch.setattr(nodes, "classify_headlines", lambda *a, **k: _none())
    events = await run(service, "analyze")
    result = AnalysisResult.model_validate(events[-1]["result"])
    assert result.narrative_source == "llm"
    assert result.audit.unverified_numbers == ["₹2,400"]
    assert result.suggestions.items[0].evidence_ids == ["E1"]  # unknown ids dropped
    audit_component = [b for b in result.risk.trust_breakdown if b.label == "Evidence audit"]
    assert audit_component and audit_component[0].value == 75


async def _none() -> None:
    return None


def test_figure_extraction_ignores_ids_horizons_and_years() -> None:
    text = "Hold 6 months [E3]; in 2025 VaR was 2.16% and cap ₹15.8T; 52-week high ₹1,611.80."
    raw = [r for r, _ in extract_figures(text)]
    assert raw == ["2.16%", "₹15.8T", "₹1,611.80"]
    evidence = [
        EvidenceItem(
            id="E1", agent="quant", label="1-day 95% VaR", value=2.16, display="2.16%", source="x"
        )
    ]
    assert verify_figures(["VaR at 95% is 2.2%"], evidence) == (2, [])
    assert verify_figures(["VaR is 3.4%"], evidence) == (1, ["3.4%"])
