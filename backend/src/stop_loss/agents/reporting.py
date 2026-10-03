"""Live agent status events, emitted through LangGraph's custom stream channel."""

from datetime import UTC, datetime
from typing import Any

from langgraph.config import get_stream_writer

from stop_loss.agents.models import AGENTS, AgentId, AgentStatus

NAMES = {agent_id: name for agent_id, name, _ in AGENTS}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AgentReporter:
    def __init__(self, agent_id: AgentId) -> None:
        self.agent_id = agent_id
        self.started_at: str | None = None
        self._writer = get_stream_writer()

    def emit(self, event: dict[str, Any]) -> None:
        self._writer(event)

    def _update(self, status: AgentStatus, message: str, **extra: Any) -> None:
        self.emit(
            {
                "type": "agent_update",
                "agent_id": self.agent_id,
                "name": NAMES[self.agent_id],
                "status": status,
                "message": message,
                "started_at": self.started_at,
                "ended_at": now_iso() if status in ("done", "error") else None,
                **extra,
            }
        )

    def start(self, message: str) -> None:
        self.started_at = now_iso()
        self._update("running", message)

    def progress(self, message: str) -> None:
        self._update("running", message)

    def done(self, message: str, *, quality: str = "good") -> None:
        self._update("done", message, data_quality=quality)

    def error(self, message: str) -> None:
        self._update("error", message, data_quality="degraded")

    def section(self, section: str, data: dict[str, Any]) -> None:
        self.emit({"type": "section", "section": section, "data": data})
