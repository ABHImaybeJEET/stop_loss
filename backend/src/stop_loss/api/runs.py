"""Runs execute independently of any HTTP connection and buffer their events, so a
dropped stream can resume (`after=<seq>`), and a reloaded thread can re-attach."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from stop_loss.agents.models import ChatRequest
from stop_loss.agents.service import AnalysisService
from stop_loss.settings import TerminalSettings

logger = logging.getLogger("stop_loss.api")
TERMINAL_EVENTS = {"final", "reply", "error", "cancelled"}


@dataclass
class Run:
    run_id: str
    user_id: str
    thread_id: str
    message_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    finished_at: float | None = None
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


class ThreadBusyError(Exception):
    def __init__(self, run: Run) -> None:
        super().__init__("thread_busy")
        self.run = run


class RunRegistry:
    def __init__(self, service: AnalysisService, settings: TerminalSettings) -> None:
        self.service = service
        self.settings = settings
        self._runs: dict[str, Run] = {}

    def get(self, run_id: str, user_id: str) -> Run | None:
        run = self._runs.get(run_id)
        return run if run and run.user_id == user_id else None

    def active_for_thread(self, user_id: str, thread_id: str) -> Run | None:
        for run in self._runs.values():
            if run.user_id == user_id and run.thread_id == thread_id and not run.done:
                return run
        return None

    def start(self, request: ChatRequest, user_id: str) -> Run:
        self._evict()
        if busy := self.active_for_thread(user_id, request.thread_id):
            raise ThreadBusyError(busy)
        run = Run(
            run_id=uuid4().hex,
            user_id=user_id,
            thread_id=request.thread_id,
            message_id=request.message_id,
        )
        self._runs[run.run_id] = run
        run.task = asyncio.create_task(self._execute(run, request), name=f"run-{run.run_id}")
        return run

    def _push(self, run: Run, event: dict[str, Any]) -> None:
        run.events.append({**event, "seq": len(run.events)})
        run.changed.set()

    async def _execute(self, run: Run, request: ChatRequest) -> None:
        terminal = False
        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                async for event in self.service.stream(
                    request, user_id=run.user_id, run_id=run.run_id
                ):
                    self._push(run, event)
                    terminal = terminal or event.get("type") in TERMINAL_EVENTS
        except TimeoutError:
            self._push(
                run,
                {
                    "type": "error",
                    "recoverable": True,
                    "message": "The analysis timed out. Retry to run it again.",
                },
            )
            terminal = True
        except asyncio.CancelledError:
            self._push(run, {"type": "cancelled", "message": "Run stopped."})
            terminal = True
        except Exception as exc:  # noqa: BLE001 - surface any engine fault to the client
            logger.exception("run %s failed", run.run_id)
            self._push(
                run,
                {
                    "type": "error",
                    "recoverable": True,
                    "message": f"The analysis failed ({type(exc).__name__}). Retry.",
                },
            )
            terminal = True
        finally:
            if not terminal:
                self._push(
                    run,
                    {
                        "type": "error",
                        "recoverable": True,
                        "message": "The run ended without a result. Retry.",
                    },
                )
            run.done = True
            run.finished_at = time.monotonic()
            run.changed.set()

    async def subscribe(
        self, run: Run, after: int = -1, heartbeat: float = 15.0
    ) -> AsyncIterator[dict[str, Any] | None]:
        """Yields buffered + live events with seq > after; None means 'send a heartbeat'."""
        cursor = after + 1
        while True:
            while cursor < len(run.events):
                yield run.events[cursor]
                cursor += 1
            if run.done:
                return
            run.changed.clear()
            if cursor < len(run.events):
                continue
            try:
                await asyncio.wait_for(run.changed.wait(), timeout=heartbeat)
            except TimeoutError:
                yield None

    async def cancel(self, run: Run) -> None:
        if run.task and not run.done:
            run.task.cancel()
            try:
                await run.task
            except asyncio.CancelledError:
                pass

    def _evict(self) -> None:
        cutoff = time.monotonic() - self.settings.run_retention_seconds
        for run_id in [
            r.run_id
            for r in self._runs.values()
            if r.done and r.finished_at is not None and r.finished_at < cutoff
        ]:
            del self._runs[run_id]

    async def aclose(self) -> None:
        for run in list(self._runs.values()):
            await self.cancel(run)
