"""Runs streamed as typed node lifecycle events (`AnalysisService.stream_events`).

Reuses RunRegistry's buffering, subscription and cancellation; each event is also persisted
to the RunStore before it is published, so GET /runs/{id} can replay any run."""

import asyncio
import logging
import time

from stop_loss.agents.models import ChatRequest
from stop_loss.agents.reporting import now_iso
from stop_loss.agents.run_events import FinalAnswer, RunEvent, RunStatus
from stop_loss.agents.service import AnalysisService
from stop_loss.api.run_store import RunStore
from stop_loss.api.runs import Run, RunRegistry
from stop_loss.settings import TerminalSettings

logger = logging.getLogger("stop_loss.api")
RUN_STATUS: dict[str, RunStatus] = {
    "ok": "completed",
    "no_result": "no_result",
    "failed": "failed",
    "cancelled": "cancelled",
}


class GraphRunRegistry(RunRegistry):
    def __init__(
        self, service: AnalysisService, settings: TerminalSettings, store: RunStore
    ) -> None:
        super().__init__(service, settings)
        self.store = store

    async def _record(self, run: Run, event: RunEvent) -> None:
        payload = event.model_copy(update={"seq": len(run.events)}).model_dump(mode="json")
        try:
            await asyncio.to_thread(self.store.append, run.run_id, payload)
        except Exception:  # noqa: BLE001 - persistence must never break a live stream
            logger.exception("run %s: event persist failed", run.run_id)
        self._push(run, payload)

    def _final(self, run: Run, status: str, error: str) -> FinalAnswer:
        return FinalAnswer(run_id=run.run_id, ts=now_iso(), status=status, error=error)

    async def _execute(self, run: Run, request: ChatRequest) -> None:
        label = "PORTFOLIO" if request.mode == "portfolio" else request.asset.symbol
        await asyncio.to_thread(
            self.store.create,
            run_id=run.run_id,
            user_id=run.user_id,
            mode=request.mode,
            thread_id=run.thread_id,
            message_id=run.message_id,
            label=label,
            started_at=now_iso(),
        )
        final: FinalAnswer | None = None
        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                async for event in self.service.stream_events(
                    request, user_id=run.user_id, run_id=run.run_id
                ):
                    await self._record(run, event)
                    if isinstance(event, FinalAnswer):
                        final = event
        except TimeoutError:
            final = self._final(run, "failed", "timeout")
            await self._record(run, final)
        except asyncio.CancelledError:
            final = self._final(run, "cancelled", "cancelled")
            await self._record(run, final)
        except Exception as exc:  # noqa: BLE001 - surface any engine fault to the client
            logger.exception("run %s failed", run.run_id)
            final = self._final(run, "failed", type(exc).__name__)
            await self._record(run, final)
        finally:
            if final is None:
                final = self._final(run, "failed", "ended_without_result")
                await self._record(run, final)
            try:
                await asyncio.to_thread(
                    self.store.finish, run.run_id, RUN_STATUS[final.status], now_iso()
                )
            except Exception:  # noqa: BLE001
                logger.exception("run %s: status persist failed", run.run_id)
            run.done = True
            run.finished_at = time.monotonic()
            run.changed.set()
