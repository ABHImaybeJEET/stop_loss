"""Portfolio-mode agents. Same eight agents and live reporting as ticker mode, applied to the
user's holdings: event + channel exposure (sector, Brent, USD/INR, NIFTY), historical
analog reactions per holding, per-stock quant risk, and sized hedges. No figure is
invented: scenarios exist only where >= MIN_ANALOGS historical parallels were measured."""

import asyncio
import re
from datetime import UTC, date, datetime
from typing import Any

from langchain_core.messages import AIMessage

from stop_loss.agents.audit import verify_figures
from stop_loss.agents.evidence import Catalog, compact, money
from stop_loss.agents.llm import classify_headlines
from stop_loss.agents.models import AGENTS, DATA_AGENTS, Audit, EvidenceItem
from stop_loss.agents.nodes import Toolkit, history_lines, normalize_citations, short_error
from stop_loss.agents.portfolio_llm import (
    PortfolioNarrative,
    PortfolioPlan,
    RecommendationDraft,
    heuristic_portfolio_plan,
    plan_portfolio,
    write_portfolio_narrative,
)
from stop_loss.agents.portfolio_models import (
    AnalogAggregate,
    AnalogEvent,
    AnalogsSection,
    AuditStep,
    EventAlert,
    EventSection,
    ExposureRow,
    ExposureSection,
    HoldingRisk,
    HoldingRow,
    HoldingSentiment,
    PortfolioResult,
    PortfolioRisk,
    PortfolioSnapshot,
    PortfolioSource,
    Recommendation,
    SectorWeight,
    SentimentSection,
)
from stop_loss.agents.reporting import AgentReporter
from stop_loss.agents.state import AnalysisState
from stop_loss.analytics.event_windows import aggregate, forward_return
from stop_loss.analytics.exposure import exposure_points
from stop_loss.analytics.models import MacroSnapshot, NewsItem
from stop_loss.analytics.news import company_terms
from stop_loss.analytics.risk import beta, closes_of, compute_quant_metrics, correlation
from stop_loss.analytics.scoring import assess_risk, assess_trust, risk_band, sentiment_counts
from stop_loss.universe import get_universe

MIN_ANALOGS = 3
MAX_NEWS_HOLDINGS = 8
HEADLINES_PER_HOLDING = 4
MAX_WEATHER_POINTS = 6
CHANNELS = {"brent": "BZ=F", "inr": "INR=X", "nifty": "^NSEI"}
EVENT_GDACS = {
    "cyclone": "tropical cyclone",
    "flood": "flood",
    "earthquake": "earthquake",
    "drought": "drought",
    "wildfire": "wildfire",
}
EVENT_DOC_TYPES = {"cyclone": "cyclone", "earthquake": "earthquake"}
REGION_LABELS = (
    "Gulf of Mexico",
    "Bay of Bengal",
    "Arabian Sea",
    "South China Sea",
    "Caribbean Sea",
)
ALERT_RANK = {"Red": 0, "Orange": 1, "Green": 2}
NAMES = {agent_id: name for agent_id, name, _ in AGENTS}
# (lat_min, lat_max, lon_min, lon_max) for regions users name in questions.
REGION_BOXES = {
    "bay of bengal": (5, 24, 78, 100),
    "arabian sea": (5, 26, 50, 78),
    "gulf of mexico": (17, 32, -98, -80),
    "caribbean": (9, 23, -90, -59),
    "south china sea": (0, 25, 105, 122),
    "gujarat": (20, 25, 67, 75),
    "odisha": (17, 23, 81, 88),
    "mumbai": (17, 21, 70, 75),
    "chennai": (11, 15, 78, 82),
    "kerala": (8, 13, 74, 78),
    "india": (5, 37, 66, 98),
}


def region_box(region: str | None) -> tuple[float, float, float, float] | None:
    low = (region or "").lower()
    return next((box for name, box in REGION_BOXES.items() if name in low), None)


def disp(symbol: str) -> str:
    return symbol.removesuffix(".NS")


def _ok(output: dict[str, Any] | None) -> Any:
    return output.get("data") if output and output.get("status") == "ok" else None


def _pct(x: float | None) -> float | None:
    return round(x * 100, 2) if x is not None else None


def section(rep: AgentReporter, name: str, data: dict[str, Any]) -> None:
    rep.emit({"type": "portfolio_section", "section": name, "data": data})


def build_portfolio_nodes(kit: Toolkit) -> dict[str, Any]:  # noqa: C901 - one closure per agent
    universe = get_universe()

    def holdings_meta(state: AnalysisState) -> list[dict[str, Any]]:
        out = []
        for h in state.get("holdings") or []:
            company = universe.get(h["symbol"])
            out.append(
                {
                    **h,
                    "name": (company.name if company else None)
                    or h.get("name")
                    or disp(h["symbol"]),
                    "sector": company.sector if company else None,
                }
            )
        return out

    def targets(state: AnalysisState) -> list[str]:
        return (state.get("plan") or {}).get("targets") or [
            h["symbol"] for h in state.get("holdings") or []
        ]

    # ── Query Coordinator ──────────────────────────────────────────────────────────
    async def coordinator(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("coordinator")
        rep.start("Parsing the portfolio question")
        holdings = holdings_meta(state)
        prompt = state["user_prompt"]
        plan: PortfolioPlan = heuristic_portfolio_plan(prompt, holdings)
        model = kit.model_for("coordinator")
        if model is not None:
            rep.progress("Extracting event, region, severity and target holdings")
            plan = (
                await plan_portfolio(
                    model, prompt, holdings, history_lines(state.get("messages", [])[:-1])
                )
                or plan
            )
        by_base = {disp(h["symbol"]): h["symbol"] for h in holdings}
        named = [
            by_base[t.upper().removesuffix(".NS")]
            for t in plan.target_symbols
            if t.upper().removesuffix(".NS") in by_base
        ]
        wanted = {s.lower() for s in plan.target_sectors}
        by_sector = [
            h["symbol"]
            for h in holdings
            if h.get("sector")
            and any(w in h["sector"].lower() or h["sector"].lower() in w for w in wanted)
        ]
        chosen = list(dict.fromkeys(named + by_sector)) or [h["symbol"] for h in holdings]
        scope = (
            "all holdings"
            if len(chosen) == len(holdings)
            else (f"{len(chosen)} of {len(holdings)} holdings")
        )
        event = plan.event_kind if plan.event_kind != "none" else "no specific event"
        summary = (
            f"{event}"
            + (f" · {plan.event_region}" if plan.event_region else "")
            + (f" · {plan.event_severity}" if plan.event_severity else "")
            + f" · {scope}"
        )
        rep.done(summary)
        kit.log(state, "coordinator", "planned", intent=plan.intent, targets=chosen)
        return {
            "plan": {**plan.model_dump(), "targets": chosen, "summary": summary, "mode": "analysis"}
        }

    # ── Market Data ────────────────────────────────────────────────────────────────
    async def market(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("market")
        holdings = holdings_meta(state)
        rep.start(f"Fetching live quotes for {len(holdings)} holdings")
        quotes = await asyncio.gather(
            *(kit.yahoo.quote(h["symbol"]) for h in holdings), return_exceptions=True
        )
        target_set = set(targets(state))
        rows: list[HoldingRow] = []
        for h, q in zip(holdings, quotes, strict=True):
            ok = not isinstance(q, BaseException) and q.price is not None
            rows.append(
                HoldingRow(
                    symbol=h["symbol"],
                    name=h["name"],
                    sector=h.get("sector"),
                    quantity=h["quantity"],
                    avg_price=h.get("avg_price"),
                    price=q.price if ok else None,
                    change_pct=q.change_pct if ok else None,
                    value=q.price * h["quantity"] if ok else None,
                    target=h["symbol"] in target_set,
                    status="ok" if ok else "unavailable",
                )
            )
        priced = [r for r in rows if r.value is not None]
        if not priced:
            rep.error("No live prices for any holding")
            return {
                "market": {
                    "status": "unavailable",
                    "error": "no_prices",
                    "summary": "no live prices",
                }
            }
        total = sum(r.value or 0 for r in priced)
        rows = [
            r.model_copy(update={"weight": (r.value / total * 100) if r.value else None})
            for r in rows
        ]
        day = [r for r in priced if r.change_pct is not None]
        day_change = sum((r.value or 0) * (1 - 1 / (1 + r.change_pct / 100)) for r in day)
        sectors: dict[str, float] = {}
        for r in rows:
            if r.weight is not None:
                sectors[r.sector or "Unclassified"] = (
                    sectors.get(r.sector or "Unclassified", 0) + r.weight
                )
        snapshot = PortfolioSnapshot(
            total_value=total,
            day_change=day_change if day else None,
            day_change_pct=(day_change / (total - day_change) * 100) if day else None,
            priced=len(priced),
            holdings=rows,
            sectors=[
                SectorWeight(sector=k, weight=v)
                for k, v in sorted(sectors.items(), key=lambda kv: -kv[1])
            ],
        )
        section(rep, "portfolio", snapshot.model_dump(mode="json"))
        summary = (
            f"{len(priced)}/{len(rows)} priced · value {compact(total, 'INR')} · "
            f"{len(sectors)} sectors"
        )
        rep.done(summary, quality="good" if len(priced) == len(rows) else "degraded")
        kit.log(state, "market", "done", priced=len(priced), total_value=total)
        return {
            "market": {"status": "ok", "data": snapshot.model_dump(mode="json"), "summary": summary}
        }

    # ── News Sentiment ─────────────────────────────────────────────────────────────
    async def news(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("news")
        holdings = {h["symbol"]: h for h in holdings_meta(state)}
        chosen = targets(state)[:MAX_NEWS_HOLDINGS]
        plan = state.get("plan") or {}
        rep.start(f"Collecting headlines for {len(chosen)} holdings")
        model = kit.model_for("news")

        async def one(symbol: str) -> tuple[str, list[NewsItem]]:
            name = holdings[symbol]["name"]
            items, _ = await kit.news.collect(
                f'"{name}"', yahoo=kit.yahoo, symbol=symbol, terms=company_terms(name, symbol)
            )
            items = items[:HEADLINES_PER_HOLDING]
            unscored = [i for i in items if i.sentiment is None]
            if unscored and model is not None:
                labels = await classify_headlines(model, name, unscored) or {}
                items = [
                    i.model_copy(update={"sentiment": labels[i.id], "sentiment_source": "llm"})
                    if i.id in labels and i.sentiment is None
                    else i
                    for i in items
                ]
            return symbol, items

        results = await asyncio.gather(*(one(s) for s in chosen), return_exceptions=True)
        per_holding = {s: i for r in results if not isinstance(r, BaseException) for s, i in [r]}
        event_items: list[NewsItem] = []
        if plan.get("event_description"):
            rep.progress("Searching live coverage of the event")
            try:
                event_items = (await kit.news.google_news(plan["event_description"]))[:5]
                if model is not None and event_items:
                    labels = (
                        await classify_headlines(
                            model, "Indian energy and commodity markets", event_items
                        )
                        or {}
                    )
                    event_items = [
                        i.model_copy(
                            update={"sentiment": labels.get(i.id), "sentiment_source": "llm"}
                        )
                        if i.id in labels
                        else i
                        for i in event_items
                    ]
            except Exception:  # noqa: BLE001 - event coverage is additive
                event_items = []
        if not per_holding and not event_items:
            rep.error("Live news sources are unavailable")
            return {
                "news": {
                    "status": "unavailable",
                    "error": "news_unavailable",
                    "summary": "news unavailable",
                }
            }
        sentiments = []
        for symbol, items in per_holding.items():
            c = sentiment_counts(items)
            scored = sum(c.values())
            sentiments.append(
                HoldingSentiment(
                    symbol=symbol,
                    positive=c["positive"],
                    negative=c["negative"],
                    neutral=c["neutral"],
                    score=((c["positive"] - c["negative"]) / scored) if scored else None,
                )
            )
        section(
            rep,
            "sentiment",
            {
                "per_holding": [s.model_dump() for s in sentiments],
                "items": [
                    _source(i, [s]).model_dump(mode="json")
                    for s, items in per_holding.items()
                    for i in items
                ],
            },
        )
        total = sum(len(v) for v in per_holding.values()) + len(event_items)
        summary = f"{total} headlines · {len(per_holding)} holdings scored"
        rep.done(summary, quality="good" if len(per_holding) == len(chosen) else "degraded")
        kit.log(state, "news", "done", headlines=total)
        return {
            "news": {
                "status": "ok",
                "summary": summary,
                "data": {
                    "per_holding": {
                        s: [i.model_dump(mode="json") for i in v] for s, v in per_holding.items()
                    },
                    "event": [i.model_dump(mode="json") for i in event_items],
                    "sentiments": [s.model_dump() for s in sentiments],
                },
            }
        }

    # ── Weather & Macro Impact ─────────────────────────────────────────────────────
    async def impact(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("impact")
        plan = state.get("plan") or {}
        rep.start("Macro channels: USD/INR, Brent, India VIX, NIFTY Bank, CPI")
        macro_out: dict[str, Any]
        try:
            snap = await kit.macro.snapshot()
            macro_out = {"status": "ok", "data": snap.model_dump(mode="json")}
        except Exception as exc:  # noqa: BLE001
            macro_out = {"status": "unavailable", "error": short_error(exc)}
        alerts: list[EventAlert] = []
        if kit.hazards is not None:
            rep.progress("Tracking live hazards (GDACS, USGS)")
            try:
                wanted = EVENT_GDACS.get(plan.get("event_kind") or "")
                live = await (kit.hazards.global_events() if wanted else kit.hazards.alerts())
                if wanted:
                    live = [a for a in live if a.event_type == wanted]
                box = region_box(plan.get("event_region"))
                if box:  # a named region: only alerts inside it (none = no live event there)
                    live = [
                        a
                        for a in live
                        if box[0] <= a.latitude <= box[1] and box[2] <= a.longitude <= box[3]
                    ]
                live.sort(
                    key=lambda a: (
                        not a.current,
                        ALERT_RANK.get(a.alert_level or "", 3),
                        -(datetime.fromisoformat(a.started_at).timestamp() if a.started_at else 0),
                    )
                )
                alerts = [
                    EventAlert(**a.model_dump(include=set(EventAlert.model_fields)))
                    for a in live[:6]
                ]
            except Exception as exc:  # noqa: BLE001 - hazard feeds are additive
                kit.log(state, "impact", "hazards_error", error=short_error(exc))
        rep.progress("7-day forecasts at target holdings' head offices and sector hubs")
        weather_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        points = []
        for symbol in targets(state):
            company = universe.get(symbol)
            if company is None:
                continue
            for p in await exposure_points(company, kit.weather):
                if p.label not in seen and len(points) < MAX_WEATHER_POINTS:
                    seen.add(p.label)
                    points.append(p)
        outlooks = await asyncio.gather(
            *(
                kit.weather.outlook(p.latitude, p.longitude, location=p.label, reason=p.reason)
                for p in points
            ),
            return_exceptions=True,
        )
        for o in outlooks:
            if isinstance(o, BaseException):
                continue
            for e in o.extremes:
                weather_rows.append(
                    {
                        "location": o.location,
                        "date": e.date,
                        "description": e.description,
                        "value": e.value,
                        "unit": e.unit,
                    }
                )
        macro_data = macro_out.get("data") or {}
        event = EventSection(
            kind=plan.get("event_kind"),
            region=plan.get("event_region"),
            severity=plan.get("event_severity"),
            description=plan.get("event_description"),
            alerts=alerts,
            macro=macro_data.get("indicators", []),
            flags=macro_data.get("flags", []),
            weather=weather_rows,
        )
        section(rep, "event", event.model_dump(mode="json"))
        summary = (
            f"{len(alerts)} live alert(s) · {len(macro_data.get('indicators', []))} macro "
            f"series · {len(weather_rows)} weather extreme(s) at {len(points)} location(s)"
        )
        status = "ok" if macro_out["status"] == "ok" or alerts or points else "unavailable"
        if status == "ok":
            rep.done(summary, quality="good" if macro_out["status"] == "ok" else "degraded")
        else:
            rep.error("Macro and hazard feeds unavailable")
        kit.log(state, "impact", "done", alerts=len(alerts), extremes=len(weather_rows))
        return {
            "macro": macro_out,
            "weather": {
                "status": status,
                "summary": summary,
                "data": event.model_dump(mode="json"),
            },
        }

    # ── Historical Analogs ─────────────────────────────────────────────────────────
    async def analogs(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("analogs")
        if kit.retriever is None:
            rep.error("Vector index not configured")
            return {
                "analogs": {
                    "status": "unavailable",
                    "error": "not_configured",
                    "summary": "vector index unavailable",
                }
            }
        plan = state.get("plan") or {}
        query = plan.get("analog_query") or state["user_prompt"]
        doc_type = EVENT_DOC_TYPES.get(plan.get("event_kind") or "")
        region = next(
            (r for r in REGION_LABELS if r.lower() in (plan.get("event_region") or "").lower()),
            None,
        )
        severity = re.search(r"(\d)", plan.get("event_severity") or "")
        filters: dict[str, Any] = {}
        rep.start(f"Searching 323k indexed records for parallels: {query[:60]}")
        try:
            hits = []
            if doc_type:
                filters = {"doc_types": [doc_type]}
                if region and doc_type == "cyclone":
                    filters["regions"] = [region]
                if severity and doc_type == "cyclone":
                    filters["min_category"] = int(severity.group(1))
                hits = await kit.retriever.search(query, top_k=8, **filters)
                if len(hits) < MIN_ANALOGS and "min_category" in filters:
                    filters.pop("min_category")  # widen before giving up on event analogs
                    hits = await kit.retriever.search(query, top_k=8, **filters)
            news_hits = await kit.retriever.search(query, top_k=8, doc_types=["news"])
        except Exception as exc:  # noqa: BLE001
            rep.error("Analog search failed")
            kit.log(state, "analogs", "error", error=short_error(exc))
            return {
                "analogs": {
                    "status": "unavailable",
                    "error": short_error(exc),
                    "summary": "analog search failed",
                }
            }
        rep.progress("Measuring each holding's 5/20-day reaction after every parallel")
        root = kit.settings.datasets_dir
        chosen = targets(state)
        events: list[AnalogEvent] = []
        for hit in [*hits, *news_hits]:
            ts = hit.metadata.get("published_ts")
            day: date | None = datetime.fromtimestamp(float(ts), UTC).date() if ts else None
            returns = {}
            if day:
                for s in chosen:
                    returns[s] = {
                        "d5": _pct(forward_return(s, day, 5, root)),
                        "d20": _pct(forward_return(s, day, 20, root)),
                    }
            events.append(
                AnalogEvent(
                    id=hit.id,
                    title=str(hit.metadata.get("title") or hit.text)[:160],
                    date=day.isoformat() if day else None,
                    doc_type=hit.metadata.get("doc_type"),
                    score=round(hit.score, 3),
                    returns=returns,
                    brent_5d=_pct(forward_return(CHANNELS["brent"], day, 5, root)) if day else None,
                    nifty_5d=_pct(forward_return(CHANNELS["nifty"], day, 5, root)) if day else None,
                )
            )

        def agg(symbol: str, values5: list, values20: list) -> AnalogAggregate:
            a5, a20 = aggregate(values5), aggregate(values20)
            return AnalogAggregate(
                symbol=symbol,
                n=int(a5["n"] or 0),
                median_5d=a5["median"],
                min_5d=a5["min"],
                max_5d=a5["max"],
                share_negative_5d=a5["share_negative"],
                median_20d=a20["median"],
            )

        aggregates = [
            agg(
                s,
                [e.returns.get(s, {}).get("d5") for e in events],
                [e.returns.get(s, {}).get("d20") for e in events],
            )
            for s in chosen
        ]
        result = AnalogsSection(
            query=query,
            filters=filters,
            events=events,
            aggregates=aggregates,
            brent=agg(CHANNELS["brent"], [e.brent_5d for e in events], []),
            nifty=agg(CHANNELS["nifty"], [e.nifty_5d for e in events], []),
        )
        section(rep, "analogs", result.model_dump(mode="json"))
        measured = sum(1 for a in aggregates if a.n >= MIN_ANALOGS)
        summary = (
            f"{len(hits)} event + {len(news_hits)} news parallels · "
            f"{measured}/{len(chosen)} holdings with ≥{MIN_ANALOGS} measured reactions"
        )
        rep.done(summary, quality="good" if measured else "degraded")
        kit.log(state, "analogs", "done", events=len(events), measured=measured)
        return {
            "analogs": {"status": "ok", "summary": summary, "data": result.model_dump(mode="json")}
        }

    # ── Quantitative Risk (per stock) ──────────────────────────────────────────────
    async def quant(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("quant")
        snap = _ok(state.get("market"))
        if not snap:
            rep.error("Skipped: no live portfolio prices")
            return {
                "quant": {"status": "unavailable", "error": "no_prices", "summary": "no prices"}
            }
        rows = {r["symbol"]: r for r in snap["holdings"]}
        chosen = [s for s in targets(state) if rows.get(s, {}).get("value")]
        rep.start(f"Per-stock risk for {len(chosen)} holdings + Brent/USD-INR/NIFTY betas")
        series = await asyncio.gather(
            *(kit.yahoo.chart(s, "1y", "1d") for s in [*chosen, *CHANNELS.values()]),
            return_exceptions=True,
        )
        charts = dict(zip([*chosen, *CHANNELS.values()], series, strict=True))
        factor = {
            k: (None if isinstance(charts[v], BaseException) else closes_of(charts[v].bars))
            for k, v in CHANNELS.items()
        }
        analog = _ok(state.get("analogs")) or {}
        aggregates = {a["symbol"]: a for a in analog.get("aggregates", [])}
        brent_move = (analog.get("brent") or {}).get("median_5d")
        news_data = _ok(state.get("news")) or {}
        sentiments = {s["symbol"]: s for s in news_data.get("sentiments", [])}
        macro = _ok(state.get("macro"))
        macro_snap = MacroSnapshot.model_validate(macro) if macro else None
        risks: list[HoldingRisk] = []
        exposure: list[ExposureRow] = []
        for symbol in chosen:
            row, chart = rows[symbol], charts[symbol]
            value = row["value"]
            entry = ExposureRow(
                symbol=symbol,
                name=row["name"],
                sector=row.get("sector"),
                value=value,
                weight=row.get("weight"),
                sentiment_score=sentiments.get(symbol, {}).get("score"),
            )
            if not isinstance(chart, BaseException) and chart.bars:
                own = closes_of(chart.bars)
                bench = charts[CHANNELS["nifty"]]
                metrics = compute_quant_metrics(
                    chart, None if isinstance(bench, BaseException) else bench
                )
                items = [
                    NewsItem.model_validate(i)
                    for i in news_data.get("per_holding", {}).get(symbol, [])
                ]
                risk = assess_risk(metrics, items, macro_snap, [])
                risks.append(
                    HoldingRisk(
                        symbol=symbol,
                        risk_score=risk.score,
                        band=risk.band,
                        vol_1y=_pct(metrics.vol_1y),
                        var_95_1d=_pct(metrics.var_95_1d),
                        max_drawdown_1y=_pct(metrics.max_drawdown_1y),
                        beta=metrics.beta_1y,
                    )
                )
                entry = entry.model_copy(
                    update={
                        "beta_nifty": metrics.beta_1y,
                        "beta_brent": beta(own, factor["brent"]) if factor["brent"] else None,
                        "beta_inr": beta(own, factor["inr"]) if factor["inr"] else None,
                        "corr_brent": correlation(own, factor["brent"])[0]
                        if factor["brent"]
                        else None,
                    }
                )
            a = aggregates.get(symbol) or {}
            if (a.get("n") or 0) >= MIN_ANALOGS and a.get("median_5d") is not None:
                entry = entry.model_copy(
                    update={
                        "analog_n": a["n"],
                        "analog_median_5d": round(a["median_5d"], 2),
                        "scenario_impact": a["median_5d"] / 100 * value,
                        "scenario_low": a["min_5d"] / 100 * value,
                        "scenario_high": a["max_5d"] / 100 * value,
                    }
                )
            elif a:
                entry = entry.model_copy(update={"analog_n": a.get("n") or 0})
            if (
                entry.beta_brent is not None
                and brent_move is not None
                and (analog.get("brent") or {}).get("n", 0) >= MIN_ANALOGS
            ):
                entry = entry.model_copy(
                    update={"channel_impact": entry.beta_brent * brent_move / 100 * value}
                )
            exposure.append(entry)
        with_scenario = [e for e in exposure if e.scenario_impact is not None]
        totals = {
            "total_impact": sum(e.scenario_impact for e in with_scenario)
            if with_scenario
            else None,
            "total_low": sum(e.scenario_low or 0 for e in with_scenario) if with_scenario else None,
            "total_high": sum(e.scenario_high or 0 for e in with_scenario)
            if with_scenario
            else None,
        }
        scored = [(r, rows[r.symbol]["value"]) for r in risks if r.risk_score is not None]
        weight_sum = sum(v for _, v in scored)
        port_score = (sum(r.risk_score * v for r, v in scored) / weight_sum) if weight_sum else None
        hedge = sum((e.beta_nifty or 0) * (e.value or 0) for e in exposure if e.beta_nifty) or None
        section(
            rep, "exposure", {**ExposureSection(rows=exposure, **totals).model_dump(mode="json")}
        )
        summary = (
            f"risk {port_score:.0f} ({risk_band(port_score)})"
            if port_score is not None
            else "risk n/a"
        ) + f" · {len(with_scenario)}/{len(exposure)} scenario estimates"
        rep.done(summary)
        kit.log(state, "quant", "done", risk_score=port_score, scenarios=len(with_scenario))
        return {
            "quant": {
                "status": "ok",
                "summary": summary,
                "data": {
                    "exposure": [e.model_dump(mode="json") for e in exposure],
                    "risks": [r.model_dump(mode="json") for r in risks],
                    "totals": totals,
                    "risk_score": port_score,
                    "risk_band": risk_band(port_score) if port_score is not None else None,
                    "nifty_hedge_notional": hedge,
                },
            }
        }

    # ── Hedging Strategy ───────────────────────────────────────────────────────────
    async def hedging(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("hedging")
        if not _ok(state.get("market")):
            rep.error("Skipped: no portfolio prices")
            return {"narrative": {"status": "skipped"}}
        rep.start("Assembling the portfolio evidence catalog")
        catalog = build_portfolio_catalog(state)
        plan = state.get("plan") or {}
        rep.progress(
            f"Writing the answer and sized actions from {len(catalog.items)} evidence items"
        )
        draft = await write_portfolio_narrative(
            kit.model_for("hedging"),
            prompt=state["user_prompt"],
            plan=plan,
            history=history_lines(state.get("messages", [])[:-1]),
            evidence=catalog.items,
        )
        source = "llm"
        if draft is None:
            source = "rules"
            draft = rules_portfolio_narrative(state, catalog)
        draft = draft.model_copy(
            update={
                k: normalize_citations(getattr(draft, k))
                for k in (
                    "bottom_line",
                    "event_summary",
                    "exposure_summary",
                    "analogs_summary",
                    "sentiment_summary",
                    "risk_summary",
                )
            }
            | {
                "recommendations": [
                    r.model_copy(update={"rationale": normalize_citations(r.rationale)})
                    for r in draft.recommendations
                ]
            }
        )
        summary = f"{len(draft.recommendations)} actions · via " + (
            "language model" if source == "llm" else "deterministic rules"
        )
        rep.done(summary, quality="good" if source == "llm" else "degraded")
        kit.log(state, "hedging", "done", narrative_source=source, evidence=len(catalog.items))
        return {
            "narrative": {
                "status": "ok",
                "mode": "portfolio",
                "source": source,
                "summary": summary,
                "draft": draft.model_dump(),
                "evidence": [e.model_dump() for e in catalog.items],
            }
        }

    # ── Evidence & Audit ───────────────────────────────────────────────────────────
    async def audit(state: AnalysisState) -> dict[str, Any]:
        rep = AgentReporter("audit")
        narrative = state.get("narrative") or {}
        if narrative.get("status") != "ok":
            rep.error("Nothing to audit")
            rep.emit(
                {
                    "type": "error",
                    "recoverable": True,
                    "message": "Live prices for your holdings are unavailable. Retry shortly.",
                }
            )
            return {"result": None}
        rep.start("Verifying every figure against the evidence catalog")
        evidence = [EvidenceItem.model_validate(e) for e in narrative["evidence"]]
        known = {e.id for e in evidence}
        draft = PortfolioNarrative.model_validate(narrative["draft"])
        texts = [
            draft.bottom_line,
            draft.event_summary,
            draft.exposure_summary,
            draft.analogs_summary,
            draft.sentiment_summary,
            draft.risk_summary,
            *(f"{r.action} {r.size or ''} {r.rationale}" for r in draft.recommendations),
        ]
        checked, unverified = verify_figures(texts, evidence, state["user_prompt"])
        statuses = {a: _status(state, a) for a in DATA_AGENTS}
        ok = sum(1 for s in statuses.values() if s in ("ok", "not_applicable"))
        failed = [a for a, s in statuses.items() if s not in ("ok", "not_applicable")]
        news_data = _ok(state.get("news")) or {}
        news_items = [
            NewsItem.model_validate(i) for v in news_data.get("per_holding", {}).values() for i in v
        ]
        trust = assess_trust(
            agents_ok=ok,
            agents_total=len(DATA_AGENTS),
            market=None,
            news=news_items,
            quant=None,
            unverified_numbers=len(unverified),
        )
        snap = PortfolioSnapshot.model_validate(_ok(state.get("market")))
        quant_data = _ok(state.get("quant")) or {}
        values = {h.symbol: h.value or 0 for h in snap.holdings}
        sentiments = [HoldingSentiment.model_validate(s) for s in news_data.get("sentiments", [])]
        weighted = [(s.score, values.get(s.symbol, 0)) for s in sentiments if s.score is not None]
        wsum = sum(v for _, v in weighted)
        steps = [
            AuditStep(
                agent=a,
                name=NAMES[a],
                status=_status(state, a) or "skipped",
                summary=_summary(state, a),
                evidence_ids=[e.id for e in evidence if e.agent == a][:40],
            )
            for a in ("coordinator", "market", "news", "impact", "analogs", "quant", "hedging")
        ]
        result = PortfolioResult(
            message_id=state["message_id"],
            run_id=state["run_id"],
            thread_id=state["thread_id"],
            generated_at=datetime.now(UTC).isoformat(),
            narrative_source=narrative["source"],
            partial=bool(failed),
            failed_agents=failed,
            langsmith_run_id=state.get("langsmith_run_id"),
            bottom_line=draft.bottom_line,
            portfolio=snap,
            event=EventSection.model_validate(_ok(state.get("weather")) or {}).model_copy(
                update={"summary": draft.event_summary}
            ),
            exposure=ExposureSection(
                summary=draft.exposure_summary,
                rows=[ExposureRow.model_validate(r) for r in quant_data.get("exposure", [])],
                **(quant_data.get("totals") or {}),
            ),
            analogs=AnalogsSection.model_validate(_ok(state.get("analogs")) or {}).model_copy(
                update={"summary": draft.analogs_summary}
            ),
            sentiment=SentimentSection(
                summary=draft.sentiment_summary,
                per_holding=sentiments,
                portfolio_score=(sum(s * v for s, v in weighted) / wsum) if wsum else None,
                items=[
                    _source(NewsItem.model_validate(i), [sym])
                    for sym, v in news_data.get("per_holding", {}).items()
                    for i in v
                ]
                + [
                    _source(NewsItem.model_validate(i), ["EVENT"])
                    for i in news_data.get("event", [])
                ],
            ),
            risk=PortfolioRisk(
                summary=draft.risk_summary,
                risk_score=quant_data.get("risk_score"),
                risk_band=quant_data.get("risk_band"),
                per_holding=[HoldingRisk.model_validate(r) for r in quant_data.get("risks", [])],
                trust_score=trust.score,
                trust_band=trust.band,
                trust_reasons=trust.reasons,
                nifty_hedge_notional=quant_data.get("nifty_hedge_notional"),
            ),
            recommendations=[
                Recommendation(
                    action=r.action,
                    kind=r.kind,
                    symbols=[disp(s) for s in r.symbols],
                    size=r.size,
                    rationale=r.rationale,
                    horizon=r.horizon,
                    confidence=r.confidence,
                    evidence_ids=[i for i in r.evidence_ids if i in known],
                )
                for r in draft.recommendations
            ],
            evidence=evidence,
            audit=Audit(checked_numbers=checked, unverified_numbers=unverified),
            steps=steps,
        )
        score = f"trust {trust.score:.0f}" if trust.score is not None else "trust n/a"
        rep.done(
            f"{checked} figures checked · {len(unverified)} unverified · {score}",
            quality="good" if not unverified else "suspect",
        )
        kit.log(
            state, "audit", "done", checked=checked, unverified=unverified, failed_agents=failed
        )
        rep.emit({"type": "portfolio_final", "result": result.model_dump(mode="json")})
        memory = "\n".join(
            [draft.bottom_line, *(f"- {r.action}: {r.rationale}" for r in draft.recommendations)]
        )
        return {
            "result": result.model_dump(mode="json"),
            "messages": [AIMessage(content=memory, id=f"{state['message_id']}-a")],
        }

    return {
        "coordinator": coordinator,
        "market": market,
        "news": news,
        "impact": impact,
        "analogs": analogs,
        "quant": quant,
        "hedging": hedging,
        "audit": audit,
    }


def _status(state: AnalysisState, agent: str) -> str | None:
    if agent == "impact":
        return (state.get("weather") or {}).get("status")
    if agent == "coordinator":
        return "ok" if state.get("plan") else None
    if agent == "hedging":
        return (state.get("narrative") or {}).get("status")
    return (state.get(agent) or {}).get("status")


def _summary(state: AnalysisState, agent: str) -> str | None:
    key = {"impact": "weather", "coordinator": "plan", "hedging": "narrative"}.get(agent, agent)
    return (state.get(key) or {}).get("summary")


def _source(item: NewsItem, symbols: list[str]) -> PortfolioSource:
    return PortfolioSource(
        publisher=item.publisher,
        title=item.title,
        url=item.url,
        published_at=item.published_at.isoformat() if item.published_at else None,
        sentiment=item.sentiment,
        sentiment_source=item.sentiment_source,
        themes=[t.value for t in item.themes],
        symbols=[disp(s) for s in symbols],
    )


def build_portfolio_catalog(state: AnalysisState) -> Catalog:
    """Numbered evidence for the portfolio answer (each figure with its provenance)."""
    cat = Catalog()
    snap = _ok(state.get("market")) or {}
    yf = "Yahoo Finance (yfinance)"
    if snap.get("total_value") is not None:
        cat.add(
            "market",
            "Portfolio market value",
            round(snap["total_value"], 2),
            money(snap["total_value"], "INR"),
            unit="INR",
            source=yf,
        )
    if snap.get("day_change_pct") is not None:
        cat.add(
            "market",
            "Portfolio change today",
            round(snap["day_change_pct"], 2),
            f"{snap['day_change_pct']:+.2f}%",
            unit="%",
            source=yf,
        )
    for h in snap.get("holdings", []):
        t = disp(h["symbol"])
        if h.get("value") is not None:
            cat.add(
                "market",
                f"{t} position value",
                round(h["value"], 2),
                money(h["value"], "INR"),
                unit="INR",
                source=yf,
            )
            cat.add(
                "market",
                f"{t} weight in portfolio",
                round(h["weight"], 2),
                f"{h['weight']:.2f}%",
                unit="%",
                source=yf,
            )
        if h.get("change_pct") is not None:
            cat.add(
                "market",
                f"{t} change today",
                round(h["change_pct"], 2),
                f"{h['change_pct']:+.2f}%",
                unit="%",
                source=yf,
            )
        if h.get("sector"):
            cat.add("market", f"{t} sector", h["sector"], h["sector"], source="NSE universe")
    for s in snap.get("sectors", []):
        cat.add(
            "market",
            f"{s['sector']} sector weight",
            round(s["weight"], 2),
            f"{s['weight']:.2f}%",
            unit="%",
            source=yf,
        )
    news = _ok(state.get("news")) or {}
    for s in news.get("sentiments", []):
        if s.get("score") is not None:
            scored = s["positive"] + s["negative"] + s["neutral"]
            cat.add(
                "news",
                f"{disp(s['symbol'])} headline sentiment",
                round(s["score"], 2),
                f"{s['positive']} positive, {s['negative']} negative of {scored} scored "
                f"(score {s['score']:+.2f})",
                source="News Sentiment Agent (Groq)",
            )
    for symbol, items in news.get("per_holding", {}).items():
        for i in items[:3]:
            cat.add(
                "news",
                f"Headline ({disp(symbol)}): {i['title']}",
                i.get("sentiment") or "unscored",
                f"{i['publisher']}: {i['title']} (sentiment {i.get('sentiment') or 'unscored'})",
                source=i["publisher"],
                url=i["url"],
                observed_at=i.get("published_at"),
            )
    for i in news.get("event", []):
        cat.add(
            "news",
            f"Event coverage: {i['title']}",
            i.get("sentiment") or "unscored",
            f"{i['publisher']}: {i['title']}",
            source=i["publisher"],
            url=i["url"],
            observed_at=i.get("published_at"),
        )
    event = _ok(state.get("weather")) or {}
    for a in event.get("alerts", []):
        cat.add(
            "impact",
            f"Live {a['event_type']}: {a['name']}",
            a.get("alert_level") or "n/a",
            f"{a['name']}: {a.get('alert_level') or 'n/a'} alert ({a['source'].upper()})"
            + (f", {a['country']}" if a.get("country") else "")
            + (f", since {a['started_at'][:10]}" if a.get("started_at") else "")
            + (f"; {a['severity']}" if a.get("severity") else ""),
            source=a["source"].upper(),
            url=a.get("url"),
            observed_at=a.get("started_at"),
        )
    for ind in event.get("macro", []):
        if ind.get("latest") is None:
            continue
        cat.add(
            "impact",
            ind["label"],
            ind["latest"],
            f"{ind['latest']:,.2f} {ind.get('unit') or ''}".strip(),
            unit=ind.get("unit"),
            source=ind.get("source", "FRED"),
            url=ind.get("source_url"),
            observed_at=ind.get("latest_date"),
        )
        if ind.get("change_pct") is not None and ind.get("previous_date"):
            cat.add(
                "impact",
                f"{ind['label']} change since {ind['previous_date']}",
                round(ind["change_pct"], 2),
                f"{ind['change_pct']:+.2f}%",
                unit="%",
                source=ind.get("source", "FRED"),
                url=ind.get("source_url"),
            )
    for flag in event.get("flags", []):
        cat.add(
            "impact", "Macro flag", flag, flag.replace("_", " "), source="StopLoss macro thresholds"
        )
    for w in event.get("weather", []):
        cat.add(
            "impact",
            f"{w['location']} {w['date']}",
            w["value"],
            w["description"],
            unit=w.get("unit"),
            source="Open-Meteo",
            observed_at=w["date"],
        )
    analogs = _ok(state.get("analogs")) or {}
    for e in analogs.get("events", [])[:10]:
        cat.add(
            "analogs",
            f"Analog: {e['title'][:90]}",
            e["score"],
            f"{e.get('date') or 'undated'} · similarity {e['score']:.2f}",
            source="Pinecone history index",
            observed_at=e.get("date"),
        )
    for a in [*analogs.get("aggregates", []), analogs.get("brent"), analogs.get("nifty")]:
        if not a or not a.get("n") or a.get("median_5d") is None:
            continue
        name = {"BZ=F": "Brent crude", "^NSEI": "NIFTY 50"}.get(a["symbol"], disp(a["symbol"]))
        cat.add(
            "analogs",
            f"{name} median 5-day move after parallels",
            round(a["median_5d"], 2),
            f"{a['median_5d']:+.2f}% (n={a['n']}, range {a['min_5d']:+.2f}% to "
            f"{a['max_5d']:+.2f}%, fell in {a['share_negative_5d'] * 100:.0f}% of cases)",
            unit="%",
            source="Local NSE/macro daily closes",
        )
    quant = _ok(state.get("quant")) or {}
    for r in quant.get("risks", []):
        t = disp(r["symbol"])
        for label, key, fmt in (
            ("1Y volatility", "vol_1y", "{:.2f}%"),
            ("1-day 95% VaR", "var_95_1d", "{:.2f}%"),
            ("risk score (0-100)", "risk_score", "{:.1f}"),
        ):
            if r.get(key) is not None:
                cat.add(
                    "quant",
                    f"{t} {label}",
                    round(r[key], 2),
                    fmt.format(r[key]),
                    source="Computed from yfinance daily closes",
                )
    for e in quant.get("exposure", []):
        t = disp(e["symbol"])
        for label, key in (
            ("beta vs NIFTY", "beta_nifty"),
            ("beta vs Brent", "beta_brent"),
            ("beta vs USD/INR", "beta_inr"),
        ):
            if e.get(key) is not None:
                cat.add(
                    "quant",
                    f"{t} {label}",
                    round(e[key], 2),
                    f"{e[key]:.2f}",
                    source="Computed from yfinance daily closes (1Y)",
                )
        if e.get("scenario_impact") is not None:
            cat.add(
                "quant",
                f"{t} analog-based 5-day scenario",
                round(e["scenario_impact"], 2),
                f"{money(e['scenario_impact'], 'INR')} (range {money(e['scenario_low'], 'INR')}"
                f" to {money(e['scenario_high'], 'INR')}, n={e['analog_n']})",
                unit="INR",
                source="Analog median x position value",
            )
        if e.get("channel_impact") is not None:
            cat.add(
                "quant",
                f"{t} Brent-channel estimate",
                round(e["channel_impact"], 2),
                money(e["channel_impact"], "INR"),
                unit="INR",
                source="Beta to Brent x analog Brent median x position value",
            )
        if e.get("value") is not None:
            cat.add(
                "hedging",
                f"{t} protective put notional (sizing)",
                round(e["value"], 2),
                money(e["value"], "INR"),
                unit="INR",
                source="Position value",
            )
    totals = quant.get("totals") or {}
    if totals.get("total_impact") is not None:
        cat.add(
            "quant",
            "Portfolio analog-based 5-day scenario (simple sum)",
            round(totals["total_impact"], 2),
            f"{money(totals['total_impact'], 'INR')} (range {money(totals['total_low'], 'INR')}"
            f" to {money(totals['total_high'], 'INR')})",
            unit="INR",
            source="Sum of per-holding scenarios",
        )
    if quant.get("risk_score") is not None:
        cat.add(
            "quant",
            "Portfolio risk score (value-weighted)",
            round(quant["risk_score"], 1),
            f"{quant['risk_score']:.1f} ({quant['risk_band']})",
            source="StopLoss risk model",
        )
    if quant.get("nifty_hedge_notional"):
        cat.add(
            "hedging",
            "NIFTY hedge notional for target holdings (sizing)",
            round(quant["nifty_hedge_notional"], 2),
            money(quant["nifty_hedge_notional"], "INR"),
            unit="INR",
            source="Sum of beta x position value",
        )
    return cat


def rules_portfolio_narrative(state: AnalysisState, catalog: Catalog) -> PortfolioNarrative:
    """Deterministic, catalog-only answer used when no LLM is available."""
    by_label = {i.label: i for i in catalog.items}

    def ref(label: str) -> str | None:
        item = by_label.get(label)
        return f"{item.display} [{item.id}]" if item else None

    plan = state.get("plan") or {}
    quant = _ok(state.get("quant")) or {}
    exposure = sorted(quant.get("exposure", []), key=lambda e: e.get("scenario_impact") or 0)
    worst = [e for e in exposure if (e.get("scenario_impact") or 0) < 0]
    total = ref("Portfolio analog-based 5-day scenario (simple sum)")
    event = plan.get("event_kind") if plan.get("event_kind") not in (None, "none") else None
    bottom = " ".join(
        filter(
            None,
            [
                f"Portfolio value {ref('Portfolio market value')}."
                if ref("Portfolio market value")
                else None,
                f"Historical parallels for this {event} imply a 5-day portfolio move of {total}."
                if total and event
                else (
                    f"Historical parallels imply a 5-day move of {total}."
                    if total
                    else "Historical parallels are insufficient for a scenario estimate."
                ),
                f"Most exposed: {', '.join(disp(e['symbol']) for e in worst[:3])}."
                if worst
                else None,
            ],
        )
    )
    recs: list[RecommendationDraft] = []
    for e in worst[:3]:
        t = disp(e["symbol"])
        label = f"{t} protective put notional (sizing)"
        recs.append(
            RecommendationDraft(
                action=f"Hedge {t} with a protective put",
                kind="hedge",
                symbols=[t],
                size=by_label[label].display if label in by_label else None,
                rationale=f"Analog scenario {ref(t + ' analog-based 5-day scenario') or 'n/a'}.",
                horizon=plan.get("horizon"),
                confidence=0.5,
                evidence_ids=[i.id for k, i in by_label.items() if k.startswith(t + " ")][:4],
            )
        )
    if hedge := by_label.get("NIFTY hedge notional for target holdings (sizing)"):
        recs.append(
            RecommendationDraft(
                action="Hedge market beta with NIFTY futures or puts",
                kind="hedge",
                symbols=[],
                size=hedge.display,
                rationale=f"Beta-weighted exposure {hedge.display} [{hedge.id}].",
                horizon=plan.get("horizon"),
                confidence=0.5,
                evidence_ids=[hedge.id],
            )
        )
    if not recs:
        recs.append(
            RecommendationDraft(
                action="Monitor holdings; no measured adverse scenario",
                kind="monitor",
                rationale="No holding has >= 3 historical parallels with a measured decline.",
                confidence=0.4,
                evidence_ids=[],
            )
        )
    alerts = [i for i in catalog.items if i.label.startswith("Live ")]
    return PortfolioNarrative(
        bottom_line=bottom,
        event_summary=(
            f"{len(alerts)} live alert(s): "
            + "; ".join(f"{a.display} [{a.id}]" for a in alerts[:3])
        )
        if alerts
        else "No matching live alerts.",
        exposure_summary=f"{len(exposure)} target holdings analysed for sector, Brent, USD/INR "
        "and NIFTY exposure.",
        analogs_summary=(
            f"Brent after parallels: {ref('Brent crude median 5-day move after parallels')}."
            if ref("Brent crude median 5-day move after parallels")
            else "Few measurable parallels."
        ),
        sentiment_summary="Headline sentiment per holding is shown below.",
        risk_summary=(
            f"Portfolio risk score {ref('Portfolio risk score (value-weighted)')}."
            if ref("Portfolio risk score (value-weighted)")
            else "Risk score unavailable."
        ),
        recommendations=recs,
    )
