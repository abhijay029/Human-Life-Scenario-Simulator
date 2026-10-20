"""
Observer Event Pipeline — non-blocking async queue worker per session.

Architecture:
  - Each session gets one asyncio.Queue and one background worker task.
  - `emit_turn(event)` puts the event into the queue and returns immediately.
  - `emit_turn_sync(event)` safely schedules `put_nowait` onto the server's main event loop
    even when called from a ThreadPoolExecutor worker thread (fixing Python 3.12 thread-loop issue).
  - The worker consumes events one-at-a-time, calling ObserverService.observe_turn().
  - On `finalize_session()`, a sentinel (None) is enqueued; the worker drains,
    calls ObserverService.finalize(), then broadcasts the scorecard via SSE and persists to SQLite.
  - SSE subscribers per session receive: "turn", "observation", "trajectory", "final" events.
  - SSE stream includes catch-up: replays already-processed observations, trajectories, and scorecard.

Privacy rule: only public dialogue (speaker name + message) reaches the observer.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, Any

from .core import ObserverService
from .schemas import TurnEvent, TurnObservation, ConversationScorecard

logger = logging.getLogger(__name__)

_SENTINEL = None  # signals the worker to finalize


@dataclass
class _SessionPipeline:
    session_id: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=512))
    worker_task: Optional[asyncio.Task] = None
    # SSE subscriber queues (one per connected client)
    sse_queues: list[asyncio.Queue] = field(default_factory=list)
    observations: list[TurnObservation] = field(default_factory=list)
    scorecard: Optional[ConversationScorecard] = None
    finalized: bool = False


class ObserverPipeline:
    """
    Manages one background worker per active session.
    Thread-safe for emit_turn (puts to asyncio.Queue from sync context via loop.call_soon_threadsafe).
    """

    def __init__(
        self,
        observer: Optional[ObserverService] = None,
        storage: Optional[Any] = None,
    ):
        self._observer = observer or ObserverService()
        self._storage = storage
        self._sessions: dict[str, _SessionPipeline] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_target_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Safely find a running event loop to schedule cross-thread calls."""
        if self._loop is not None and not self._loop.is_closed() and self._loop.is_running():
            return self._loop
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                self._loop = loop
                return loop
        except RuntimeError:
            pass
        return None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Explicitly register the server's main running event loop."""
        self._loop = loop

    # ── Session lifecycle ────────────────────────────────────────────────────

    def get_or_create_session(
        self,
        session_id: str,
        participants: Optional[list[str]] = None,
        scenario_description: str = "",
    ) -> _SessionPipeline:
        # Capture running loop if currently in an async context
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if session_id not in self._sessions:
            pipe = _SessionPipeline(session_id=session_id)
            self._sessions[session_id] = pipe
            self._observer.get_or_create_session(
                session_id,
                participants=participants,
                scenario_description=scenario_description,
            )
            if self._storage:
                try:
                    self._storage.upsert_session(
                        session_id=session_id,
                        scenario=scenario_description,
                        participants=participants or [],
                    )
                except Exception as _st_exc:
                    logger.warning("Failed to upsert session in storage: %s", _st_exc)
        return self._sessions[session_id]

    def start_worker(self, session_id: str) -> None:
        """Launch the background async worker for this session if not already running."""
        pipe = self._sessions.get(session_id)
        if pipe is None or (pipe.worker_task and not pipe.worker_task.done()):
            return

        loop = self._get_target_loop()
        if loop is None:
            logger.warning("Observer start_worker: no event loop available for session %s", session_id)
            return

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is loop:
            pipe.worker_task = loop.create_task(self._worker(pipe))
        else:
            # Called from a worker thread (e.g. ThreadPoolExecutor)
            pipe.worker_task = asyncio.run_coroutine_threadsafe(self._worker(pipe), loop)  # type: ignore

        logger.info("Observer worker started for session %s", session_id)

    # ── Emit (call from sync OR async context) ──────────────────────────────

    def emit_turn_sync(self, event: TurnEvent) -> None:
        """
        Fire-and-forget from synchronous code (e.g. LangGraph speak node in ThreadPoolExecutor).
        Schedules the put on the running event loop without blocking the caller.
        """
        pipe = self._sessions.get(event.session_id)
        if pipe is None:
            logger.warning("emit_turn_sync: unknown session %s", event.session_id)
            return

        loop = self._get_target_loop()
        if loop is not None:
            loop.call_soon_threadsafe(pipe.queue.put_nowait, event)
        else:
            try:
                pipe.queue.put_nowait(event)
            except Exception as exc:
                logger.warning("emit_turn_sync fallback put_nowait failed: %s", exc)

    async def emit_turn(self, event: TurnEvent) -> None:
        """Fire-and-forget from async context."""
        pipe = self._sessions.get(event.session_id)
        if pipe is None:
            logger.warning("emit_turn: unknown session %s", event.session_id)
            return
        await pipe.queue.put(event)

    # ── Finalize ────────────────────────────────────────────────────────────

    async def finalize_session(self, session_id: str) -> None:
        """Enqueue sentinel so worker drains, evaluates scorecard, and broadcasts 'final'."""
        pipe = self._sessions.get(session_id)
        if pipe and not pipe.finalized:
            await pipe.queue.put(_SENTINEL)

    def finalize_session_sync(self, session_id: str) -> None:
        """Fire-and-forget sentinel from synchronous code."""
        pipe = self._sessions.get(session_id)
        if pipe and not pipe.finalized:
            loop = self._get_target_loop()
            if loop is not None:
                loop.call_soon_threadsafe(pipe.queue.put_nowait, _SENTINEL)
            else:
                try:
                    pipe.queue.put_nowait(_SENTINEL)
                except Exception as exc:
                    logger.warning("finalize_session_sync put_nowait failed: %s", exc)

    # ── SSE subscription ─────────────────────────────────────────────────────

    def subscribe_sse(self, session_id: str) -> asyncio.Queue:
        """Register a new SSE client queue for this session. Returns the queue."""
        pipe = self.get_or_create_session(session_id)
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        pipe.sse_queues.append(q)
        return q

    def unsubscribe_sse(self, session_id: str, q: asyncio.Queue) -> None:
        pipe = self._sessions.get(session_id)
        if pipe and q in pipe.sse_queues:
            pipe.sse_queues.remove(q)

    async def sse_stream(self, session_id: str) -> AsyncIterator[str]:
        """
        Async generator yielding SSE-formatted strings.
        Yields past observations immediately (catch-up), then streams new ones.
        """
        pipe = self.get_or_create_session(session_id)

        # Catch-up: replay already-processed observations
        for obs in pipe.observations:
            yield _sse_event("observation", obs.model_dump())

        # Also yield latest trajectory if available
        trajectories = self._observer.get_all_trajectories(session_id)
        if trajectories:
            traj_data = [t.model_dump() for t in trajectories]
            yield _sse_event("trajectory", {"trajectories": traj_data})

        # If already finalized, yield scorecard and close
        if pipe.finalized and pipe.scorecard:
            yield _sse_event("final", pipe.scorecard.model_dump())
            return

        q = self.subscribe_sse(session_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield _sse_event("heartbeat", {"ts": time.time()})
                    continue

                if msg is None:  # stream closed
                    break
                yield msg
        finally:
            self.unsubscribe_sse(session_id, q)

    # ── Worker ───────────────────────────────────────────────────────────────

    async def _worker(self, pipe: _SessionPipeline) -> None:
        """Background worker: processes TurnEvents one-at-a-time, broadcasts to SSE."""
        logger.info("Observer worker running for session %s", pipe.session_id)
        try:
            while True:
                item = await pipe.queue.get()
                if item is _SENTINEL:
                    break

                event: TurnEvent = item
                # Broadcast raw turn event so SSE clients see the dialogue immediately
                _broadcast(pipe, _sse_event("turn", event.model_dump()))

                # Observe (runs in thread pool to avoid blocking the asyncio event loop)
                try:
                    loop = asyncio.get_running_loop()
                    obs = await loop.run_in_executor(
                        None, self._observer.observe_turn, event
                    )
                    pipe.observations.append(obs)

                    if self._storage:
                        try:
                            self._storage.save_observation(obs)
                        except Exception as _st_exc:
                            logger.warning("Failed to persist observation: %s", _st_exc)

                    _broadcast(pipe, _sse_event("observation", obs.model_dump()))

                    # Trajectory snapshot after each turn
                    trajectories = self._observer.get_all_trajectories(pipe.session_id)
                    traj_data = [t.model_dump() for t in trajectories]
                    _broadcast(pipe, _sse_event("trajectory", {"trajectories": traj_data}))

                except Exception as exc:
                    logger.error("Worker observe_turn failed: %s", exc)

                pipe.queue.task_done()

            # Drain remaining items
            while not pipe.queue.empty():
                try:
                    pipe.queue.get_nowait()
                    pipe.queue.task_done()
                except asyncio.QueueEmpty:
                    break

            # Finalize scorecard
            try:
                loop = asyncio.get_running_loop()
                scorecard = await loop.run_in_executor(
                    None, self._observer.finalize, pipe.session_id
                )
                pipe.scorecard = scorecard

                if self._storage:
                    try:
                        self._storage.save_scorecard(scorecard)
                        self._storage.mark_finalized(pipe.session_id)
                    except Exception as _st_exc:
                        logger.warning("Failed to persist scorecard: %s", _st_exc)

                _broadcast(pipe, _sse_event("final", scorecard.model_dump()))
            except Exception as exc:
                logger.error("Worker finalize failed: %s", exc)
            finally:
                pipe.finalized = True
                _broadcast(pipe, None)

        except asyncio.CancelledError:
            logger.info("Observer worker cancelled for session %s", pipe.session_id)
        except Exception as exc:
            logger.exception("Observer worker crashed for session %s: %s", pipe.session_id, exc)

    # ── Accessors ────────────────────────────────────────────────────────────

    def get_observations(self, session_id: str) -> list[TurnObservation]:
        pipe = self._sessions.get(session_id)
        if pipe and pipe.observations:
            return pipe.observations
        if self._storage:
            return self._storage.get_observations(session_id)
        return []

    def get_trajectories(self, session_id: str):
        return self._observer.get_all_trajectories(session_id)

    def get_scorecard(self, session_id: str) -> Optional[ConversationScorecard]:
        pipe = self._sessions.get(session_id)
        if pipe and pipe.scorecard:
            return pipe.scorecard
        if self._storage:
            return self._storage.get_scorecard(session_id)
        return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _broadcast(pipe: _SessionPipeline, msg: Optional[str]) -> None:
    """Put a message into all SSE subscriber queues (drop if full)."""
    dead: list[asyncio.Queue] = []
    for q in pipe.sse_queues:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            pipe.sse_queues.remove(q)
        except ValueError:
            pass


# ── Singleton used by the API layer ──────────────────────────────────────────
_pipeline: Optional[ObserverPipeline] = None


def get_pipeline() -> ObserverPipeline:
    global _pipeline
    if _pipeline is None:
        from .storage import ObserverStorage
        _pipeline = ObserverPipeline(storage=ObserverStorage())
    return _pipeline
