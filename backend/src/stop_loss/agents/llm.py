"""Per-agent Groq reasoning. Each returns None when no model is configured or it fails,
so callers fall back to deterministic logic rather than inventing content."""

import json
import logging
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from fin_terminal.config import secret_value
from fin_terminal.grounding import GROUNDING_PROMPT
from stop_loss.agents.models import AGENTS, AgentId, EvidenceItem
from stop_loss.analytics.models import NewsItem, Sentiment
from stop_loss.settings import TerminalSettings

logger = logging.getLogger("stop_loss.agents")


def build_chat_model(
    settings: TerminalSettings, agent: AgentId = "coordinator"
) -> BaseChatModel | None:
    key = (
        getattr(settings, f"groq_{agent}_api_key")
        if settings.llm_provider == "groq"
        else settings.openai_api_key
    )
    api_key = secret_value(key)
    if not api_key:
        return None
    if settings.llm_provider == "groq":
        from stop_loss.agents.groq import GroqChatModel

        return GroqChatModel(
            api_key=api_key,
            model=settings.groq_chat_model,
            timeout_seconds=settings.llm_timeout_seconds,
            name=f"groq-{agent}",
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.groq_chat_model
        if settings.llm_provider == "groq"
        else settings.openai_chat_model,
        base_url="https://api.groq.com/openai/v1" if settings.llm_provider == "groq" else None,
        api_key=api_key,
        temperature=0.2,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
        use_responses_api=False,
        name=f"{settings.llm_provider}-{agent}",
    )


def build_agent_models(settings: TerminalSettings) -> dict[AgentId, BaseChatModel | None]:
    # Missing or exhausted keys never fall through to another agent's credentials.
    return {agent: build_chat_model(settings, agent) for agent, _, _ in AGENTS}


class QueryPlan(BaseModel):
    mode: Literal["analysis", "reply"] = Field(
        description="'analysis' for a full sectioned report on the asset; 'reply' for a "
        "focused follow-up answer (what-if, clarification, comparison, explanation)."
    )
    intent: str = Field(description="One short phrase describing what the user wants.")
    horizon: str | None = Field(default=None, description="Investment horizon if stated.")
    position: Literal["long", "short", "none", "unknown"] = "unknown"


class HeadlineSentiment(BaseModel):
    id: str
    sentiment: Sentiment


class HeadlineSentiments(BaseModel):
    items: list[HeadlineSentiment]


class SuggestionDraft(BaseModel):
    action: str = Field(description="Imperative, specific action (<= 12 words).")
    rationale: str = Field(description="1-2 sentences citing evidence ids like [E3].")
    horizon: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]


class NarrativeDraft(BaseModel):
    executive_answer: str = ""
    snapshot_summary: str
    sources_summary: str
    historical_summary: str
    suggestions: list[SuggestionDraft] = Field(min_length=1, max_length=4)


class ReplyDraft(BaseModel):
    markdown: str
    evidence_ids: list[str]


RULES = """
Rules:
- Use ONLY figures that appear in EVIDENCE.
- Citation format: Always cite evidence individually as [E1], [E2]. NEVER combine as [E1, E2] or [E1, 10] or E1.
- Copy figures as shown in each item's `display` (rounding to fewer decimals is fine).
- Never compute or invent new figures (no projected prices, no invented percentages or targets).
- If the user asks for something not covered by EVIDENCE, explicitly state: "Info not known from verified sources."
- Historical analog returns (e.g. "5d forward return on asset") show the actual historical impact on the asset during similar events. You MUST use these to answer how an event affects the asset.
- Do not promise returns. Recommendations are informational, not investment advice.
"""


def _evidence_json(evidence: list[EvidenceItem]) -> str:
    rows = [
        {
            "id": e.id,
            "agent": e.agent,
            "label": e.label,
            "display": e.display,
            "observed_at": e.observed_at,
        }
        for e in evidence
    ]
    return json.dumps(rows, ensure_ascii=False)


async def plan_query(
    model: BaseChatModel | None, prompt: str, asset: dict[str, Any], history: list[str]
) -> QueryPlan | None:
    if model is None:
        return None
    try:
        return await model.with_structured_output(QueryPlan).ainvoke(
            [
                SystemMessage(
                    "You are the Query Coordinator of a multi-agent financial terminal. Decide "
                    "whether the latest message needs a full asset analysis report or a focused "
                    "follow-up reply, and extract horizon and position if stated."
                ),
                HumanMessage(
                    json.dumps(
                        {
                            "asset": asset,
                            "latest_message": prompt,
                            "recent_conversation": history[-6:],
                        },
                        ensure_ascii=False,
                    )
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001 - degrade to deterministic routing
        logger.warning("plan_query failed: %s", type(exc).__name__)
        return None


async def classify_headlines(
    model: BaseChatModel | None, asset_name: str, items: list[NewsItem]
) -> dict[str, Sentiment] | None:
    if model is None or not items:
        return None
    try:
        result = await model.with_structured_output(HeadlineSentiments).ainvoke(
            [
                SystemMessage(
                    f"Classify each headline's likely near-term price impact on {asset_name} as "
                    "positive, neutral or negative. Use neutral when unrelated or unclear. "
                    "Return one entry per id."
                ),
                HumanMessage(
                    json.dumps(
                        [{"id": i.id, "headline": i.title} for i in items], ensure_ascii=False
                    )
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("classify_headlines failed: %s", type(exc).__name__)
        return None
    known = {i.id for i in items}
    return {row.id: row.sentiment for row in result.items if row.id in known}


async def write_narrative(
    model: BaseChatModel | None,
    *,
    prompt: str,
    asset: dict[str, Any],
    plan: dict[str, Any],
    history: list[str],
    evidence: list[EvidenceItem],
) -> NarrativeDraft | None:
    if model is None:
        return None
    try:
        return await model.with_structured_output(NarrativeDraft).ainvoke(
            [
                SystemMessage(
                    "You are the Hedging Strategy Agent of StopLoss, a multi-agent financial "
                    "intelligence terminal. Write a concise, sectioned analysis.\n"
                    f"{GROUNDING_PROMPT}\n{RULES}\n"
                    "executive_answer: 2-4 sentences directly answering the user's exact question based strictly on evidence. If no verifiable sources mention the information, explicitly state 'Info not known. Answer with care'.\n"
                    "snapshot_summary: 2-3 sentences on what the asset is and where it "
                    "trades now.\n"
                    "sources_summary: 2-3 sentences on what live news/macro/weather say.\n"
                    "historical_summary: 2-4 sentences on trend, volatility, drawdowns, tail risk "
                    "and seasonality.\n"
                    "suggestions: 2-4 actions tailored to the user's question, position and "
                    "horizon (e.g. hold/trim/add, stop-loss discipline, protective put, collar, "
                    "pair or index hedge, monitor a catalyst). confidence in [0,1] should reflect "
                    "evidence strength. Plain text only, no markdown."
                ),
                HumanMessage(
                    json.dumps(
                        {
                            "user_question": prompt,
                            "asset": asset,
                            "plan": plan,
                            "recent_conversation": history[-6:],
                        },
                        ensure_ascii=False,
                    )
                    + "\nEVIDENCE:\n"
                    + _evidence_json(evidence)
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("write_narrative failed: %s", type(exc).__name__)
        return None


async def write_reply(
    model: BaseChatModel | None,
    *,
    prompt: str,
    asset: dict[str, Any],
    history: list[str],
    evidence: list[EvidenceItem],
) -> ReplyDraft | None:
    if model is None:
        return None
    try:
        return await model.with_structured_output(ReplyDraft).ainvoke(
            [
                SystemMessage(
                    "You are the Hedging Strategy Agent of StopLoss answering a follow-up in an "
                    "ongoing analysis thread. Answer directly in concise GitHub-flavored markdown "
                    "(short paragraphs or bullets, max ~180 words).\n"
                    f"{GROUNDING_PROMPT}\n{RULES}"
                ),
                HumanMessage(
                    json.dumps(
                        {
                            "user_question": prompt,
                            "asset": asset,
                            "conversation": history[-10:],
                        },
                        ensure_ascii=False,
                    )
                    + "\nEVIDENCE:\n"
                    + _evidence_json(evidence)
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("write_reply failed: %s", type(exc).__name__)
        return None
