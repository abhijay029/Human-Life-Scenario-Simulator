"""
Observer Agent FastAPI Router — REST + SSE endpoints.

Routes:
  POST   /observer/sessions                    — create/register a session
  GET    /observer/sessions                    — list all sessions
  GET    /observer/sessions/{id}/stream        — SSE stream (final scorecard)
  GET    /observer/sessions/{id}/observations  — past observations
  GET    /observer/sessions/{id}/scorecard     — final scorecard (once finalized)
  POST   /observer/sessions/{id}/turn          — manually submit a turn event (for testing)
  POST   /observer/sessions/{id}/finalize      — trigger finalization
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .pipeline import get_pipeline
from .storage import ObserverStorage
from .schemas import TurnEvent, ConversationScorecard, TurnObservation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observer", tags=["Observer Agent"])
_storage = ObserverStorage()


# ── Request/Response schemas ──────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    session_id: str
    scenario_description: str = ""
    participants: list[str] = []


class CreateSessionResponse(BaseModel):
    session_id: str
    message: str


class SessionListItem(BaseModel):
    session_id: str
    scenario: str
    participants: list[str]
    created_at: float
    finalized_at: Optional[float] = None


class SubmitTurnRequest(BaseModel):
    speaker: str
    listeners: list[str] = []
    message: str
    turn_index: Optional[int] = None
    runtime: str = "simulation"


class ObservationsResponse(BaseModel):
    session_id: str
    observations: list[TurnObservation]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest):
    """Register a session and start its background observer worker."""
    pipeline = get_pipeline()
    pipeline.get_or_create_session(
        req.session_id,
        participants=req.participants,
        scenario_description=req.scenario_description,
    )
    _storage.upsert_session(
        req.session_id,
        scenario=req.scenario_description,
        participants=req.participants,
    )
    pipeline.start_worker(req.session_id)
    return CreateSessionResponse(
        session_id=req.session_id,
        message=f"Session '{req.session_id}' registered with {len(req.participants)} participants.",
    )


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions():
    """List all known sessions from SQLite."""
    rows = _storage.list_sessions()
    result = []
    for r in rows:
        import json as _json
        try:
            participants = _json.loads(r.get("participants", "[]"))
        except Exception:
            participants = []
        result.append(SessionListItem(
            session_id=r["session_id"],
            scenario=r.get("scenario", ""),
            participants=participants,
            created_at=r.get("created_at", 0.0),
            finalized_at=r.get("finalized_at"),
        ))
    return result


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    """
    SSE stream for a session.
    Events: final | heartbeat
    """
    pipeline = get_pipeline()

    async def generator():
        async for chunk in pipeline.sse_stream(session_id):
            yield chunk

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/observations", response_model=ObservationsResponse)
async def get_observations(session_id: str):
    """Retrieve all stored turn observations for a session."""
    pipeline = get_pipeline()
    # Prefer in-memory (faster), fall back to SQLite
    observations = pipeline.get_observations(session_id)
    if not observations:
        observations = _storage.get_observations(session_id)
    return ObservationsResponse(session_id=session_id, observations=observations)


@router.get("/sessions/{session_id}/scorecard", response_model=ConversationScorecard)
async def get_scorecard(session_id: str):
    """Return the final scorecard once the session is finalized."""
    pipeline = get_pipeline()
    scorecard = pipeline.get_scorecard(session_id)
    if scorecard is None:
        # Try SQLite fallback
        scorecard = _storage.get_scorecard(session_id)
    if scorecard is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scorecard not yet available for session '{session_id}'. "
                   "The session may still be running or not finalized.",
        )
    return scorecard


@router.post("/sessions/{session_id}/turn", status_code=202)
async def submit_turn(session_id: str, req: SubmitTurnRequest):
    """
    Manually submit a turn event for testing or integration.
    Returns 202 Accepted immediately — observer processes asynchronously.
    """
    pipeline = get_pipeline()
    pipe = pipeline._sessions.get(session_id)
    if pipe is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Create it first via POST /observer/sessions.",
        )

    # Compute turn_index from existing observations if not provided
    turn_index = req.turn_index if req.turn_index is not None else len(pipe.observations)

    event = TurnEvent(
        session_id=session_id,
        turn_index=turn_index,
        speaker=req.speaker,
        listeners=req.listeners,
        message=req.message,
        runtime=req.runtime,
    )
    await pipeline.emit_turn(event)
    return {"accepted": True, "turn_index": turn_index}


@router.post("/sessions/{session_id}/finalize", status_code=202)
async def finalize_session(session_id: str):
    """Trigger finalization: drains queue, runs scorecard, broadcasts 'final' SSE event."""
    pipeline = get_pipeline()
    pipe = pipeline._sessions.get(session_id)
    if pipe is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )
    if pipe.finalized:
        return {"already_finalized": True, "session_id": session_id}

    await pipeline.finalize_session(session_id)
    return {"accepted": True, "session_id": session_id, "message": "Finalization enqueued."}
