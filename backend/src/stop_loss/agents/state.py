"""LangGraph state. Conversation keys persist per thread; per-run keys are reset each run."""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

PER_RUN_KEYS = (
    "plan",
    "market",
    "news",
    "macro",
    "weather",
    "analogs",
    "quant",
    "narrative",
    "result",
    "holdings",
)


class AgentOutput(TypedDict, total=False):
    status: str  # ok | unavailable | not_applicable | not_found
    error: str | None
    data: Any


class AnalysisState(TypedDict, total=False):
    # Persisted conversation memory (checkpointed per user+thread).
    messages: Annotated[list[AnyMessage], add_messages]
    active_asset: dict[str, Any] | None
    analyzed_symbols: list[str]
    # Per-run inputs.
    run_id: str
    message_id: str
    thread_id: str
    langsmith_run_id: str | None
    user_prompt: str
    asset: dict[str, Any] | None
    # Portfolio mode: [{symbol, quantity, avg_price, name}] for this run.
    scope_mode: str
    holdings: list[dict[str, Any]] | None
    # Per-run agent outputs (JSON-safe dicts so checkpoints stay serializable).
    plan: dict[str, Any] | None
    market: AgentOutput | None
    news: AgentOutput | None
    macro: AgentOutput | None
    weather: AgentOutput | None
    analogs: AgentOutput | None
    quant: AgentOutput | None
    narrative: dict[str, Any] | None
    result: dict[str, Any] | None
