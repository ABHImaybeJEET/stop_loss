"""Owns provider clients, the checkpointer and the compiled graph; streams run events."""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from fin_terminal.config import secret_value
from fin_terminal.evidence import EvidenceLog
from stop_loss.agents.event_stream import GraphEventTranslator
from stop_loss.agents.graph import build_analysis_graph
from stop_loss.agents.llm import build_agent_models
from stop_loss.agents.models import AGENTS, ChatRequest
from stop_loss.agents.nodes import Toolkit
from stop_loss.agents.reporting import now_iso
from stop_loss.agents.run_events import RunEvent, RunStarted
from stop_loss.agents.state import PER_RUN_KEYS
from stop_loss.analytics.hazards import HazardClient
from stop_loss.analytics.macro import MacroClient
from stop_loss.analytics.news import NewsClient
from stop_loss.analytics.weather import WeatherClient
from stop_loss.analytics.yahoo import YahooFinanceClient
from stop_loss.retrieval.search import HistoricalRetriever
from stop_loss.settings import TerminalSettings

logger = logging.getLogger("stop_loss.agents")


class AnalysisService:
    def __init__(
        self,
        settings: TerminalSettings,
        *,
        yahoo: YahooFinanceClient | None = None,
        news: NewsClient | None = None,
        macro: MacroClient | None = None,
        weather: WeatherClient | None = None,
        hazards: HazardClient | None = None,
        llm: BaseChatModel | None = None,
        use_llm: bool = True,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self.settings = settings
        models = build_agent_models(settings) if use_llm and llm is None else {}
        yahoo_client = yahoo or YahooFinanceClient(settings)
        self.kit = Toolkit(
            settings=settings,
            yahoo=yahoo_client,
            news=news or NewsClient(settings),
            macro=macro or MacroClient(settings, yahoo_client),
            weather=weather or WeatherClient(settings),
            hazards=hazards or HazardClient(settings),
            retriever=self._build_retriever(settings),
            llm=llm,
            agent_models=models,
            evidence_log=EvidenceLog(settings.evidence_path),
        )
        self._checkpointer = checkpointer
        self._stack = AsyncExitStack()
        self.graph: Any = None
        self.portfolio_graph: Any = None

    @property
    def llm_enabled(self) -> bool:
        return self.kit.llm is not None or any(self.kit.agent_models.values())

    async def start(self) -> None:
        if self._checkpointer is None:
            self.settings.conversation_db_path.parent.mkdir(parents=True, exist_ok=True)
            self._checkpointer = await self._stack.enter_async_context(
                AsyncSqliteSaver.from_conn_string(str(self.settings.conversation_db_path))
            )
        self.graph = build_analysis_graph(self.kit, self._checkpointer)
        self.portfolio_graph = build_analysis_graph(self.kit, self._checkpointer, portfolio=True)

    async def stream(
        self, request: ChatRequest, *, user_id: str, run_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        if self.graph is None:
            await self.start()
        graph, inputs, config, langsmith_run_id = self._prepare(request, user_id, run_id)
        yield {
            "type": "run_started",
            "run_id": run_id,
            "thread_id": request.thread_id,
            "message_id": request.message_id,
            "started_at": now_iso(),
            "langsmith_run_id": langsmith_run_id,
            "llm_enabled": self.llm_enabled,
        }
        for agent_id, name, role in AGENTS:
            yield {
                "type": "agent_update",
                "agent_id": agent_id,
                "name": name,
                "role": role,
                "status": "queued",
                "message": "Queued",
            }
        async for chunk in graph.astream(inputs, config, stream_mode="custom"):
            if isinstance(chunk, dict):
                yield chunk

    async def stream_events(
        self, request: ChatRequest, *, user_id: str, run_id: str
    ) -> AsyncIterator[RunEvent]:
        """Same run as `stream`, observed through `astream_events` as typed node lifecycle
        events. Always ends with exactly one `final_answer`."""
        if self.graph is None:
            await self.start()
        graph, inputs, config, langsmith_run_id = self._prepare(request, user_id, run_id)
        yield RunStarted(
            run_id=run_id,
            ts=now_iso(),
            mode=request.mode,
            thread_id=request.thread_id,
            message_id=request.message_id,
            label="PORTFOLIO" if request.mode == "portfolio" else request.asset.symbol,
            langsmith_run_id=langsmith_run_id,
            llm_enabled=self.llm_enabled,
            nodes=[agent_id for agent_id, _, _ in AGENTS],
        )
        translator = GraphEventTranslator(run_id, request.mode)
        try:
            async for event in graph.astream_events(inputs, config, version="v2"):
                for out in translator.translate(event):
                    yield out
        except Exception as exc:  # noqa: BLE001 - a raising node ends the run, not the server
            logger.exception("run %s failed", run_id)
            for out in translator.fail(exc):
                yield out
            return
        yield translator.finish()

    def _prepare(
        self, request: ChatRequest, user_id: str, run_id: str
    ) -> tuple[Any, dict[str, Any], dict[str, Any], str | None]:
        trace_id = uuid4()
        tracing = bool(
            self.settings.langsmith_tracing and secret_value(self.settings.langsmith_api_key)
        )
        langsmith_run_id = str(trace_id) if tracing else None
        portfolio = request.mode == "portfolio"
        asset = None if portfolio else request.asset.model_dump()
        holdings = [h.model_dump() for h in request.holdings] if portfolio else None
        label = "PORTFOLIO" if portfolio else asset["symbol"]
        inputs: dict[str, Any] = {
            "messages": [
                HumanMessage(content=f"[{label}] {request.prompt}", id=f"{request.message_id}-u")
            ],
            "run_id": run_id,
            "message_id": request.message_id,
            "thread_id": request.thread_id,
            "langsmith_run_id": langsmith_run_id,
            "user_prompt": request.prompt,
            "asset": asset,
            **{key: None for key in PER_RUN_KEYS},
            "holdings": holdings,
            "scope_mode": request.mode,
        }
        config = {
            "run_name": "stoploss-analysis",
            "run_id": trace_id,
            "tags": ["analysis", f"mode:{request.mode}", f"asset:{label}"],
            "metadata": {
                # "run_id" is reserved by LangGraph checkpoint metadata: reusing it makes a
                # follow-up run on the same thread silently no-op.
                "stoploss_run_id": run_id,
                "stoploss_thread_id": request.thread_id,
                "user_id": user_id,
            },
            # Namespaced by user so one user can never resume another user's thread memory.
            "configurable": {"thread_id": f"{user_id}:{request.thread_id}"},
        }
        graph = self.portfolio_graph if portfolio else self.graph
        return graph, inputs, config, langsmith_run_id

    async def aclose(self) -> None:
        await self.kit.yahoo.aclose()
        await self.kit.news.aclose()
        await self.kit.weather.aclose()
        if self.kit.hazards is not None:
            await self.kit.hazards.aclose()
        await self._stack.aclose()

    def _build_retriever(self, settings: TerminalSettings) -> HistoricalRetriever | None:
        try:
            from fin_terminal.config import secret_value
            from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter
            from fin_terminal.vectorstore.factory import create_vectorstore
            from fin_terminal.embeddings import LazyEmbeddings

            if not secret_value(settings.pinecone_api_key):
                return None

            adapter = create_vectorstore(settings)
            if not isinstance(adapter, PineconeVectorAdapter):
                return None

            embedder = LazyEmbeddings(settings)
            return HistoricalRetriever(embedder, adapter, settings.pinecone_history_namespace)
        except Exception as exc:
            import logging

            logging.getLogger("stop_loss.agents").warning(
                "Failed to init HistoricalRetriever: %s", exc
            )
            return None
