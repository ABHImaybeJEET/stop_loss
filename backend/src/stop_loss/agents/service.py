"""Owns provider clients, the checkpointer and the compiled graph; streams run events."""

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
from stop_loss.agents.graph import build_analysis_graph
from stop_loss.agents.llm import build_chat_model
from stop_loss.agents.models import AGENTS, ChatRequest
from stop_loss.agents.nodes import Toolkit
from stop_loss.agents.reporting import now_iso
from stop_loss.agents.state import PER_RUN_KEYS
from stop_loss.analytics.macro import MacroClient
from stop_loss.analytics.news import NewsClient
from stop_loss.analytics.weather import WeatherClient
from stop_loss.analytics.yahoo import YahooFinanceClient
from stop_loss.settings import TerminalSettings


class AnalysisService:
    def __init__(
        self,
        settings: TerminalSettings,
        *,
        yahoo: YahooFinanceClient | None = None,
        news: NewsClient | None = None,
        macro: MacroClient | None = None,
        weather: WeatherClient | None = None,
        llm: BaseChatModel | None = None,
        use_llm: bool = True,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self.settings = settings
        self.kit = Toolkit(
            settings=settings,
            yahoo=yahoo or YahooFinanceClient(settings),
            news=news or NewsClient(settings),
            macro=macro or MacroClient(settings),
            weather=weather or WeatherClient(settings),
            llm=llm if llm is not None else (build_chat_model(settings) if use_llm else None),
            evidence_log=EvidenceLog(settings.evidence_path),
        )
        self._checkpointer = checkpointer
        self._stack = AsyncExitStack()
        self.graph: Any = None

    @property
    def llm_enabled(self) -> bool:
        return self.kit.llm is not None

    async def start(self) -> None:
        if self._checkpointer is None:
            self.settings.conversation_db_path.parent.mkdir(parents=True, exist_ok=True)
            self._checkpointer = await self._stack.enter_async_context(
                AsyncSqliteSaver.from_conn_string(str(self.settings.conversation_db_path))
            )
        self.graph = build_analysis_graph(self.kit, self._checkpointer)

    async def stream(
        self, request: ChatRequest, *, user_id: str, run_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        if self.graph is None:
            await self.start()
        trace_id = uuid4()
        tracing = bool(
            self.settings.langsmith_tracing and secret_value(self.settings.langsmith_api_key)
        )
        langsmith_run_id = str(trace_id) if tracing else None
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
        asset = request.asset.model_dump()
        inputs: dict[str, Any] = {
            "messages": [
                HumanMessage(
                    content=f"[{asset['symbol']}] {request.prompt}", id=f"{request.message_id}-u"
                )
            ],
            "run_id": run_id,
            "message_id": request.message_id,
            "thread_id": request.thread_id,
            "langsmith_run_id": langsmith_run_id,
            "user_prompt": request.prompt,
            "asset": asset,
            **{key: None for key in PER_RUN_KEYS},
        }
        config = {
            "run_name": "stoploss-analysis",
            "run_id": trace_id,
            "tags": ["analysis", f"asset:{asset['symbol']}"],
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
        async for chunk in self.graph.astream(inputs, config, stream_mode="custom"):
            if isinstance(chunk, dict):
                yield chunk

    async def aclose(self) -> None:
        await self.kit.yahoo.aclose()
        await self.kit.news.aclose()
        await self.kit.weather.aclose()
        await self._stack.aclose()
