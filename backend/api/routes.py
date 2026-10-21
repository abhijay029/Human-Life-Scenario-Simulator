"""
API Routes
==========
All FastAPI route handlers.
"""

import os
import json
import asyncio
import threading
import uuid
from queue import Empty, Queue
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.persona import Persona
from backend.agents.observer import analyse_dialogue
from backend.memory.memory_manager import PersonaMemory
from backend.simulation.engine import run_simulation
from backend.simulation.multiverse import run_multiverse, generate_comparison_report
from backend.api.schemas import (
    RunSimulationRequest,
    SimulationResponse,
    RunMultiverseRequest,
    MultiverseResponse,
    BuildPersonaRequest,
    BuildPersonaResponse,
    PersonaSchema,
)

load_dotenv()

router = APIRouter()

# Thread pool for running blocking simulation code without blocking the event loop
_executor = ThreadPoolExecutor(max_workers=1)

# Only one simulation at a time
_sim_lock = threading.Lock()

_llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    google_api_key=os.getenv("GEMINI_API_KEY"),
)


def _sse(event: dict) -> str:
    """Encode one JSON event using the SSE wire format."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _event_stream(events: Queue):
    """Read blocking worker events without blocking FastAPI's event loop."""
    while True:
        def get_event():
            try:
                return events.get(timeout=15)
            except Empty:
                return {"type": "heartbeat"}

        event = await asyncio.to_thread(get_event)
        if event is None:
            break
        if event.get("type") == "heartbeat":
            # Keep proxies and browsers from closing an otherwise healthy stream.
            yield ": keep-alive\n\n"
            continue

        yield _sse(event)


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "service": "HumanSimulator API"}


# ── Simulate ──────────────────────────────────────────────────────────────────

@router.post("/simulate", response_model=SimulationResponse)
async def simulate(req: RunSimulationRequest):
    if not _sim_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="A simulation is already running. Please wait for it to finish."
        )

    session_id = req.session_id or f"sim_{uuid.uuid4().hex[:12]}"

    def _run():
        try:
            personas = [Persona(**p.model_dump()) for p in req.personas]
            if req.store_memories:
                for p in personas:
                    mem = PersonaMemory(p.name)
                    if mem.count() == 0:
                        mem.store_persona_facts(p)

            dialogue_log = run_simulation(
                personas=personas,
                scenario=req.scenario,
                decision_point=req.decision_point,
                max_turns=req.max_turns,
                session_id=session_id,
            )

            try:
                analysis_raw = analyse_dialogue(
                    dialogue_log=dialogue_log,
                    scenario=req.scenario,
                    decision_point=req.decision_point,
                    personas=[p.model_dump() for p in personas],
                )
            except Exception:
                analysis_raw = None

            return SimulationResponse(
                scenario=req.scenario,
                decision_point=req.decision_point,
                dialogue_log=dialogue_log,
                analysis=analysis_raw,
                session_id=session_id,
            )
        finally:
            _sim_lock.release()
            # del mem

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run)
        return result
    except Exception as exc:
        _sim_lock.release()
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}")


# ── Multiverse ────────────────────────────────────────────────────────────────

@router.post("/multiverse", response_model=MultiverseResponse)
async def multiverse(req: RunMultiverseRequest):
    if not _sim_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="A simulation is already running. Please wait for it to finish."
        )

    def _run():
        try:
            personas = [Persona(**p.model_dump()) for p in req.personas]

            if req.store_memories:
                for p in personas:
                    mem = PersonaMemory(p.name)
                    if mem.count() == 0:
                        mem.store_persona_facts(p)

            results = run_multiverse(
                personas=personas,
                scenario=req.scenario,
                decision_branches=req.decision_branches,
                max_turns=req.max_turns,
            )

            comparison = generate_comparison_report(results)

            branches = [
                SimulationResponse(
                    scenario=req.scenario,
                    decision_point=r["decision_point"],
                    dialogue_log=r["dialogue_log"],
                    analysis=r.get("analysis"),
                )
                for r in results
            ]

            return MultiverseResponse(
                scenario=req.scenario,
                branches=branches,
                comparison_report=comparison,
            )
        finally:
            _sim_lock.release()

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run)
        return result
    except Exception as exc:
        _sim_lock.release()
        raise HTTPException(status_code=500, detail=f"Multiverse failed: {exc}")


# ── Streaming simulation endpoints ──────────────────────────────────────────

@router.post("/simulate/stream")
async def simulate_stream(req: RunSimulationRequest):
    """Stream completed persona turns while a single simulation is running."""
    if not _sim_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A simulation is already running. Please wait for it to finish.")

    session_id = req.session_id or f"sim_{uuid.uuid4().hex[:12]}"
    events = Queue()
    personas = [Persona(**p.model_dump()) for p in req.personas]

    # Register the observer before starting the simulation so its worker can
    # evaluate each completed dialogue turn as soon as it is emitted.
    from backend.observer.pipeline import get_pipeline
    from backend.observer.schemas import TurnEvent

    pipeline = get_pipeline()
    pipeline.get_or_create_session(
        session_id,
        participants=[persona.name for persona in personas],
        scenario_description=req.scenario,
    )
    pipeline.start_worker(session_id)

    def on_turn(turn: dict) -> None:
        events.put(turn)
        pipeline.emit_turn_sync(TurnEvent(
            session_id=session_id,
            turn_index=turn["turn"] - 1,
            speaker=turn["speaker"],
            listeners=[persona.name for persona in personas if persona.name != turn["speaker"]],
            message=turn["message"],
        ))

    def worker():
        try:
            events.put({"type": "simulation_started"})
            if req.store_memories:
                for persona in personas:
                    mem = PersonaMemory(persona.name)
                    if mem.count() == 0:
                        mem.store_persona_facts(persona)

            dialogue_log = run_simulation(
                personas=personas,
                scenario=req.scenario,
                decision_point=req.decision_point,
                max_turns=req.max_turns,
                on_event=on_turn,
                session_id=session_id,
            )

            events.put({"type": "status", "message": "Observer analysing outcomes"})
            try:
                analysis = analyse_dialogue(
                    dialogue_log=dialogue_log,
                    scenario=req.scenario,
                    decision_point=req.decision_point,
                    personas=[p.model_dump() for p in personas],
                )
            except Exception:
                analysis = None

            result = SimulationResponse(
                scenario=req.scenario,
                decision_point=req.decision_point,
                dialogue_log=dialogue_log,
                analysis=analysis,
                session_id=session_id,
            )
            events.put({"type": "completed", "result": result.model_dump()})
        except Exception as exc:
            events.put({"type": "error", "message": str(exc)})
        finally:
            pipeline.finalize_session_sync(session_id)
            _sim_lock.release()
            events.put(None)

    try:
        _executor.submit(worker)
    except Exception:
        _sim_lock.release()
        raise

    return StreamingResponse(
        _event_stream(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/multiverse/stream")
async def multiverse_stream(req: RunMultiverseRequest):
    """Stream turns and lifecycle events for each sequential multiverse branch."""
    if not _sim_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A simulation is already running. Please wait for it to finish.")

    events = Queue()
    personas = [Persona(**p.model_dump()) for p in req.personas]

    def worker():
        try:
            events.put({"type": "simulation_started"})
            if req.store_memories:
                for persona in personas:
                    mem = PersonaMemory(persona.name)
                    if mem.count() == 0:
                        mem.store_persona_facts(persona)

            results = run_multiverse(
                personas=personas,
                scenario=req.scenario,
                decision_branches=req.decision_branches,
                max_turns=req.max_turns,
                on_event=events.put,
            )
            events.put({"type": "status", "message": "Generating comparison report"})

            branches = [
                SimulationResponse(
                    scenario=req.scenario,
                    decision_point=result["decision_point"],
                    dialogue_log=result["dialogue_log"],
                    analysis=result.get("analysis"),
                )
                for result in results
            ]
            response = MultiverseResponse(
                scenario=req.scenario,
                branches=branches,
                comparison_report=generate_comparison_report(results),
            )
            events.put({"type": "completed", "result": response.model_dump()})
        except Exception as exc:
            events.put({"type": "error", "message": str(exc)})
        finally:
            _sim_lock.release()
            events.put(None)

    try:
        _executor.submit(worker)
    except Exception:
        _sim_lock.release()
        raise

    return StreamingResponse(
        _event_stream(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Character Builder ─────────────────────────────────────────────────────────

_BUILD_SYSTEM = """You are a character-analysis AI. The user will describe a real person in natural language.
Extract and return a structured JSON persona with EXACTLY these fields:
{
  "name": "<full name or placeholder like 'The Boss'>",
  "age": <integer>,
  "occupation": "<job title>",
  "personality_traits": ["<trait1>", "<trait2>", "<trait3>"],
  "values": ["<value1>", "<value2>"],
  "communication_style": "<one phrase>",
  "emotional_triggers": ["<trigger1>", "<trigger2>"],
  "background": "<2-3 sentences>",
  "goals": ["<goal1>", "<goal2>"]
}
Return ONLY the JSON. No markdown. No explanation."""


@router.post("/characters/build", response_model=BuildPersonaResponse)
async def build_persona(req: BuildPersonaRequest):
    def _run():
        messages = [
            SystemMessage(content=_BUILD_SYSTEM),
            HumanMessage(content=req.description),
        ]
        response = _llm.invoke(messages)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        persona_data = json.loads(raw)
        persona_schema = PersonaSchema(**persona_data)
        persona = Persona(**persona_data)
        return BuildPersonaResponse(
            persona=persona_schema,
            system_prompt_preview=persona.to_system_prompt(),
        )

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _run)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse persona from description: {exc}",
        )
