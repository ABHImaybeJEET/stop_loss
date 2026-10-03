"""The eight agents. Each node reports live status, isolates its own failures, and writes
an append-only evidence-log entry; a failed agent never aborts the run."""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from fin_terminal.evidence import EvidenceLog
from fin_terminal.schemas import EvidenceLogEntry
from stop_loss.agents.audit import verify_figures
from stop_loss.agents.evidence import build_catalog
from stop_loss.agents.fallback import heuristic_plan, rules_narrative
from stop_loss.agents.llm import (
    NarrativeDraft,
    ReplyDraft,
    classify_headlines,
    plan_query,
    write_narrative,
    write_reply,
)
from stop_loss.agents.models import (
    DATA_AGENTS,
    AgentId,
    AnalysisResult,
    AssetRef,
    Audit,
    EvidenceItem,
    SuggestionItem,
    Suggestions,
    TextReply,
)
from stop_loss.agents.reporting import AgentReporter
from stop_loss.agents.result import (
    historical_section,
    risk_section,
    snapshot_section,
    sources_section,
)
from stop_loss.agents.state import AnalysisState
from stop_loss.analytics.hazards import HazardClient
from stop_loss.analytics.macro import MacroClient
from stop_loss.analytics.models import (
    AssetProfile,
    ChartSeries,
    MacroSnapshot,
    NewsItem,
    QuantMetrics,
    WeatherOutlook,
)
from stop_loss.analytics.news import NewsClient, company_terms
from stop_loss.analytics.risk import benchmark_for, compute_quant_metrics
from stop_loss.analytics.scoring import (
    RiskAssessment,
    assess_risk,
    assess_trust,
    sentiment_counts,
)
from stop_loss.analytics.weather import WeatherClient
from stop_loss.analytics.yahoo import SymbolNotFoundError, YahooFinanceClient
from stop_loss.settings import TerminalSettings

logger = logging.getLogger("stop_loss.agents")
NAME_SUFFIX = re.compile(
    r"[,.]?\s+(limited|ltd\.?|inc\.?|incorporated|corporation|corp\.?|plc|co\.?|holdings?|"
    r"company|s\.a\.|ag|n\.v\.)$",
    re.I,
)
MAX_HEADLINES = 10


@dataclass
class Toolkit:
    settings: TerminalSettings
    yahoo: YahooFinanceClient
    news: NewsClient
    macro: MacroClient
    weather: WeatherClient
    llm: BaseChatModel | None
    evidence_log: EvidenceLog
    agent_models: dict[AgentId, BaseChatModel | None] = field(default_factory=dict)
    hazards: HazardClient | None = None

    def model_for(self, agent: AgentId) -> BaseChatModel | None:
        return self.agent_models.get(agent) if self.agent_models else self.llm

    def log(self, state: AnalysisState, agent: str, event: str, **details: Any) -> None:
        try:
            self.evidence_log.append(
                EvidenceLogEntry(
                    ingest_run_id=state["run_id"],
                    stage=f"agent:{agent}",
                    event=event,
                    source=agent,
                    langsmith_run_id=state.get("langsmith_run_id"),
                    details={"thread_id": state.get("thread_id"), **details},
                )
            )
        except OSError as exc:  # evidence logging must never break a run
            logger.warning("evidence log append failed: %s", exc)


def short_error(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    return str(code or type(exc).__name__)


def history_lines(messages: list[AnyMessage]) -> list[str]:
    lines = []
    for message in messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        lines.append(f"{role}: {str(message.content)[:1500]}")
    return lines


def clean_company_name(name: str) -> str:
    previous = None
    while previous != name:
        previous, name = name, NAME_SUFFIX.sub("", name.strip())
    return name


def us_listed(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{1,5}", symbol))


def _load(model: type, data: Any) -> Any:
    return model.model_validate(data) if data else None


def _ok(output: dict[str, Any] | None) -> Any:
    return output.get("data") if output and output.get("status") == "ok" else None


def build_nodes(kit: Toolkit) -> dict[str, Any]:  # noqa: C901 - one closure per agent
    async def coordinator(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("coordinator")
        rep.start("Parsing the request")
        asset, prompt = state["asset"], state["user_prompt"]
        previous = state.get("active_asset")
        switched = bool(previous) and previous.get("symbol") != asset["symbol"]
        first_look = asset["symbol"] not in (state.get("analyzed_symbols") or [])
        history = history_lines(state.get("messages", [])[:-1])
        plan = heuristic_plan(prompt)
        if kit.model_for("coordinator") is not None:
            rep.progress("Classifying intent, horizon and position")
            plan = await plan_query(kit.model_for("coordinator"), prompt, asset, history) or plan
        if first_look or switched:
            plan = plan.model_copy(update={"mode": "analysis"})
        data = plan.model_dump() | {"asset_switched": switched}
        label = "Full analysis" if plan.mode == "analysis" else "Follow-up answer"
        extras = [
            f"horizon {plan.horizon}" if plan.horizon else None,
            f"position {plan.position}" if plan.position != "unknown" else None,
        ]
        rep.done(" · ".join([label, *[e for e in extras if e]]))
        kit.log(state, "coordinator", "planned", mode=plan.mode, intent=plan.intent)
        return {"plan": data, "active_asset": asset}

    async def market(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("market")
        symbol = state["asset"]["symbol"]
        rep.start(f"Fetching {symbol} quote and 5-year daily history")
        daily, profile = await asyncio.gather(
            kit.yahoo.chart(symbol, "5y", "1d"),
            kit.yahoo.profile(symbol),
            return_exceptions=True,
        )
        if isinstance(daily, SymbolNotFoundError):
            rep.error(f"No market data for {symbol}; it may be delisted or mistyped")
            kit.log(state, "market", "not_found", symbol=symbol)
            return {"market": {"status": "not_found", "error": "symbol_not_found"}}
        if isinstance(daily, BaseException):
            rep.error(f"Market data unavailable ({short_error(daily)})")
            kit.log(state, "market", "error", error=short_error(daily))
            return {"market": {"status": "unavailable", "error": short_error(daily)}}
        if isinstance(profile, BaseException):
            rep.progress("Company profile unavailable; continuing with price data")
            profile = None
        bench_symbol = benchmark_for(symbol, daily.instrument_type)
        if bench_symbol:
            rep.progress(f"Loading benchmark {bench_symbol} for beta")
        if (state.get("plan") or {}).get("mode") == "analysis":
            rep.section("snapshot", snapshot_section(daily, profile).model_dump(mode="json"))
        price = f"{daily.price:,.2f} {daily.currency or ''}".strip() if daily.price else "n/a"
        change = f" · {daily.change_pct:+.2f}%" if daily.change_pct is not None else ""
        rep.done(
            f"{price}{change} · {len(daily.bars)} daily bars · market {daily.market_state}",
            quality=daily.data_quality,
        )
        kit.log(
            state,
            "market",
            "done",
            price=daily.price,
            bars=len(daily.bars),
            source_url=daily.source_url,
        )
        return {
            "market": {
                "status": "ok",
                "data": {
                    "daily": daily.model_copy(update={"bars": []}).model_dump(mode="json"),
                    "profile": profile.model_dump(mode="json") if profile else None,
                    "benchmark_symbol": bench_symbol,
                },
            }
        }

    async def news(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("news")
        asset = state["asset"]
        symbol, company = asset["symbol"], clean_company_name(asset["name"])
        rep.start(f"Collecting headlines for {company}")
        try:
            collected, failures = await kit.news.collect(
                f'"{company}"',
                yahoo=kit.yahoo,
                symbol=symbol,
                terms=company_terms(asset["name"], symbol),
            )
        except Exception as exc:
            rep.error("Live news sources are unavailable")
            kit.log(state, "news", "error", error=short_error(exc))
            return {"news": {"status": "unavailable", "error": short_error(exc)}}
        items = _dedupe(collected)[:MAX_HEADLINES]
        unscored = [i for i in items if i.sentiment is None]
        if unscored and kit.model_for("news") is not None:
            rep.progress(f"Classifying sentiment of {len(unscored)} headlines")
            labels = await classify_headlines(kit.model_for("news"), company, unscored) or {}
            items = [
                i.model_copy(update={"sentiment": labels[i.id], "sentiment_source": "llm"})
                if i.id in labels and i.sentiment is None
                else i
                for i in items
            ]
        if (state.get("plan") or {}).get("mode") == "analysis":
            rep.section("sources", sources_section(items).model_dump(mode="json"))
        counts = sentiment_counts(items)
        degraded = f" · {len(failures)} source(s) failed" if failures else ""
        rep.done(
            f"{len(items)} headlines · {counts['positive']} positive, {counts['negative']} "
            f"negative, {counts['neutral']} neutral{degraded}",
            quality="degraded" if failures else "good",
        )
        kit.log(
            state,
            "news",
            "done",
            headlines=len(items),
            failures=failures,
            urls=[i.url for i in items],
        )
        return {
            "news": {
                "status": "ok",
                "data": [i.model_dump(mode="json") for i in items],
                "error": ",".join(failures) or None,
            }
        }

    async def macro(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("macro")
        rep.start("Pulling FRED: WTI, CPI, Fed funds, 10Y and the 2s10s curve")
        try:
            snapshot = await kit.macro.snapshot()
        except Exception as exc:  # noqa: BLE001
            rep.error(f"Macro data unavailable ({short_error(exc)})")
            kit.log(state, "macro", "error", error=short_error(exc))
            return {"macro": {"status": "unavailable", "error": short_error(exc)}}
        flags = ", ".join(f.replace("_", " ") for f in snapshot.flags) or "no flags"
        rep.done(f"{len(snapshot.indicators)} indicators · {flags}")
        kit.log(state, "macro", "done", series=[i.series_id for i in snapshot.indicators])
        return {"macro": {"status": "ok", "data": snapshot.model_dump(mode="json")}}

    async def weather(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("weather")
        symbol = state["asset"]["symbol"]
        rep.start("Locating facilities exposed to weather")
        try:
            profile: AssetProfile | None = await kit.yahoo.profile(symbol)
        except Exception:  # noqa: BLE001 - no profile simply means no known facility
            profile = None
        targets: list[tuple[float, float, str, str]] = []
        if profile and profile.city:
            rep.progress(f"Geocoding headquarters: {profile.city}")
            try:
                place = await kit.weather.geocode(profile.city)
            except Exception:  # noqa: BLE001
                place = None
            if place:
                targets.append((*place, "Company headquarters"))
        if profile and (profile.sector or "").lower() == "energy":
            s = kit.settings
            targets.append(
                (
                    s.weather_latitude,
                    s.weather_longitude,
                    s.weather_location_name,
                    "Gulf Coast refining hub (energy exposure)",
                )
            )
        if not targets:
            rep.done("Not applicable: no facility location known for this asset")
            kit.log(state, "weather", "not_applicable")
            return {"weather": {"status": "not_applicable", "data": []}}
        rep.progress(f"Fetching 7-day forecast for {len(targets)} location(s)")
        results = await asyncio.gather(
            *(
                kit.weather.outlook(lat, lon, location=label, reason=reason)
                for lat, lon, label, reason in targets
            ),
            return_exceptions=True,
        )
        outlooks = [r for r in results if not isinstance(r, BaseException)]
        if not outlooks:
            rep.error("Weather forecast unavailable")
            kit.log(state, "weather", "error")
            return {"weather": {"status": "unavailable", "error": "forecast_unavailable"}}
        extremes = sum(len(o.extremes) for o in outlooks)
        rep.done(f"{len(outlooks)} location(s) · {extremes} extreme(s) in the 7-day forecast")
        kit.log(
            state, "weather", "done", locations=[o.location for o in outlooks], extremes=extremes
        )
        return {"weather": {"status": "ok", "data": [o.model_dump(mode="json") for o in outlooks]}}

    async def quant(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("quant")
        rep.start("Computing volatility, VaR, drawdowns and beta")
        market_data = _ok(state.get("market"))
        news_items = [NewsItem.model_validate(n) for n in _ok(state.get("news")) or []]
        macro_snap = _load(MacroSnapshot, _ok(state.get("macro")))
        outlooks = [WeatherOutlook.model_validate(w) for w in _ok(state.get("weather")) or []]
        if not market_data:
            rep.error("Skipped: no price history available")
            kit.log(state, "quant", "skipped")
            return {"quant": {"status": "unavailable", "error": "no_price_history"}}
        symbol = state["asset"]["symbol"]
        try:
            daily = await kit.yahoo.chart(symbol, "5y", "1d")
            bench = None
            if bench_symbol := market_data.get("benchmark_symbol"):
                try:
                    bench = await kit.yahoo.chart(bench_symbol, "5y", "1d")
                except Exception:  # noqa: BLE001 - beta simply drops out
                    bench = None
            metrics = compute_quant_metrics(daily, bench)
        except Exception as exc:  # noqa: BLE001
            rep.error(f"Risk computation failed ({short_error(exc)})")
            kit.log(state, "quant", "error", error=short_error(exc))
            return {"quant": {"status": "unavailable", "error": short_error(exc)}}
        rep.progress("Scoring risk from volatility, tails, sentiment and events")
        risk = assess_risk(metrics, news_items, macro_snap, outlooks)
        if (state.get("plan") or {}).get("mode") == "analysis":
            rep.section("historical", historical_section(metrics).model_dump(mode="json"))
            rep.section(
                "risk",
                risk_section(metrics, risk, news_items, macro_snap, outlooks).model_dump(
                    mode="json"
                ),
            )
        var = f" · VaR95 {metrics.var_95_1d:.2%}" if metrics.var_95_1d is not None else ""
        score = f"risk {risk.score:.0f} ({risk.band})" if risk.score is not None else "risk n/a"
        rep.done(f"{score}{var} · {metrics.observations} observations")
        kit.log(state, "quant", "done", risk_score=risk.score, observations=metrics.observations)
        return {
            "quant": {
                "status": "ok",
                "data": {
                    "metrics": metrics.model_dump(mode="json"),
                    "risk": risk.model_dump(mode="json"),
                },
            }
        }

    def _inputs(state: AnalysisState) -> dict[str, Any]:
        market_data = _ok(state.get("market")) or {}
        quant_data = _ok(state.get("quant")) or {}
        return {
            "market": _load(ChartSeries, market_data.get("daily")),
            "profile": _load(AssetProfile, market_data.get("profile")),
            "quant": _load(QuantMetrics, quant_data.get("metrics")),
            "risk": _load(RiskAssessment, quant_data.get("risk")),
            "news": [NewsItem.model_validate(n) for n in _ok(state.get("news")) or []],
            "macro": _load(MacroSnapshot, _ok(state.get("macro"))),
            "weather": [WeatherOutlook.model_validate(w) for w in _ok(state.get("weather")) or []],
        }

    async def hedging(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("hedging")
        if (state.get("market") or {}).get("status") == "not_found":
            rep.error("Skipped: the asset has no market data")
            return {"narrative": {"status": "skipped"}}
        rep.start("Assembling the evidence catalog")
        data = _inputs(state)
        catalog = build_catalog(**data)
        plan = state.get("plan") or {}
        mode = plan.get("mode", "analysis")
        history = history_lines(state.get("messages", [])[:-1])
        draft: NarrativeDraft | ReplyDraft | None = None
        source = "llm"
        if mode == "reply":
            rep.progress("Drafting a grounded follow-up answer")
            draft = await write_reply(
                kit.model_for("hedging"),
                prompt=state["user_prompt"],
                asset=state["asset"],
                history=history,
                evidence=catalog.items,
            )
            if draft is None:
                mode = "analysis"
        if mode == "analysis":
            rep.progress(
                f"Writing analysis and hedge actions from {len(catalog.items)} evidence items"
            )
            draft = await write_narrative(
                kit.model_for("hedging"),
                prompt=state["user_prompt"],
                asset=state["asset"],
                plan=plan,
                history=history,
                evidence=catalog.items,
            )
            if draft is None:
                source = "rules"
                draft = rules_narrative(
                    asset=state["asset"],
                    plan=plan,
                    catalog=catalog,
                    quant=data["quant"],
                    risk=data["risk"],
                    news=data["news"],
                    weather=data["weather"],
                )
        how = "language model" if source == "llm" else "deterministic rules (no LLM configured)"
        detail = (
            f"{len(draft.suggestions)} suggestions"
            if isinstance(draft, NarrativeDraft)
            else "answer drafted"
        )
        rep.done(f"{detail} · via {how}", quality="good" if source == "llm" else "degraded")
        kit.log(
            state,
            "hedging",
            "done",
            mode=mode,
            narrative_source=source,
            evidence_items=len(catalog.items),
        )
        return {
            "narrative": {
                "status": "ok",
                "mode": mode,
                "source": source,
                "draft": draft.model_dump(),
                "evidence": [e.model_dump() for e in catalog.items],
            }
        }

    async def audit(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("audit")
        narrative = state.get("narrative") or {}
        symbol = state["asset"]["symbol"]
        if narrative.get("status") != "ok":
            rep.error("Nothing to audit")
            rep.emit(
                {
                    "type": "error",
                    "recoverable": False,
                    "message": f"No market data found for {symbol}. The symbol may be "
                    "delisted or mistyped; pick another asset.",
                }
            )
            return {"result": None}
        rep.start("Verifying every figure against the evidence catalog")

        evidence = [EvidenceItem.model_validate(e) for e in narrative["evidence"]]
        known = {e.id for e in evidence}
        data = _inputs(state)
        statuses = {a: (state.get(a) or {}).get("status") for a in DATA_AGENTS}
        ok = sum(1 for s in statuses.values() if s in ("ok", "not_applicable"))
        failed = [a for a, s in statuses.items() if s not in ("ok", "not_applicable")]
        generated_at = datetime.now(UTC).isoformat()
        base = {
            "message_id": state["message_id"],
            "run_id": state["run_id"],
            "thread_id": state["thread_id"],
            "generated_at": generated_at,
            "narrative_source": narrative["source"],
            "langsmith_run_id": state.get("langsmith_run_id"),
        }
        if narrative["mode"] == "reply":
            draft = ReplyDraft.model_validate(narrative["draft"])
            texts = [draft.markdown]
        else:
            draft = NarrativeDraft.model_validate(narrative["draft"])
            texts = [
                draft.snapshot_summary,
                draft.sources_summary,
                draft.historical_summary,
                *(f"{s.action} {s.rationale}" for s in draft.suggestions),
            ]
        checked, unverified = verify_figures(texts, evidence, state["user_prompt"])
        trust = assess_trust(
            agents_ok=ok,
            agents_total=len(DATA_AGENTS),
            market=data["market"],
            news=data["news"],
            quant=data["quant"],
            unverified_numbers=len(unverified),
        )
        audit_block = Audit(checked_numbers=checked, unverified_numbers=unverified)
        if isinstance(draft, ReplyDraft):
            cited = [
                e for e in evidence if e.id in set(draft.evidence_ids) | _cited(draft.markdown)
            ]
            payload = TextReply(**base, content=draft.markdown, evidence=cited, audit=audit_block)
            event = {"type": "reply", "reply": payload.model_dump(mode="json")}
            memory = draft.markdown
        else:
            if data["market"] is None:
                raise RuntimeError("analysis without market data")  # guarded by hedging
            result = AnalysisResult(
                **base,
                partial=bool(failed),
                failed_agents=failed,
                asset=AssetRef.model_validate(state["asset"]),
                snapshot=snapshot_section(data["market"], data["profile"], draft.snapshot_summary),
                sources=sources_section(data["news"], draft.sources_summary),
                historical=historical_section(data["quant"], draft.historical_summary),
                suggestions=Suggestions(
                    items=[
                        SuggestionItem(
                            action=s.action,
                            rationale=s.rationale,
                            horizon=s.horizon,
                            confidence=s.confidence,
                            evidence_ids=[i for i in s.evidence_ids if i in known],
                        )
                        for s in draft.suggestions
                    ]
                ),
                risk=risk_section(
                    data["quant"], data["risk"], data["news"], data["macro"], data["weather"], trust
                ),
                evidence=evidence,
                audit=audit_block,
            )
            payload = result
            event = {"type": "final", "result": result.model_dump(mode="json")}
            memory = "\n".join(
                [
                    draft.snapshot_summary,
                    draft.historical_summary,
                    *(f"- {s.action}: {s.rationale}" for s in draft.suggestions),
                ]
            )
        score = f"trust {trust.score:.0f}" if trust.score is not None else "trust n/a"
        rep.done(
            f"{checked} figures checked · {len(unverified)} unverified · {score}",
            quality="good" if not unverified else "suspect",
        )
        kit.log(
            state,
            "audit",
            "done",
            checked=checked,
            unverified=unverified,
            trust_score=trust.score,
            failed_agents=failed,
        )
        rep.emit(event)
        analyzed = list(dict.fromkeys([*(state.get("analyzed_symbols") or []), symbol]))
        return {
            "result": payload.model_dump(mode="json"),
            "messages": [AIMessage(content=memory, id=f"{state['message_id']}-a")],
            "analyzed_symbols": analyzed,
        }

    return {
        "coordinator": coordinator,
        "market": market,
        "news": news,
        "macro": macro,
        "weather": weather,
        "quant": quant,
        "hedging": hedging,
        "audit": audit,
    }


def _cited(text: str) -> set[str]:
    return set(re.findall(r"\[(E\d+)\]", text))


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    out: list[NewsItem] = []
    for item in items:
        key = re.sub(r"[^a-z0-9]", "", item.title.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    far_past = datetime.min.replace(tzinfo=UTC)
    return sorted(out, key=lambda i: i.published_at or far_past, reverse=True)
