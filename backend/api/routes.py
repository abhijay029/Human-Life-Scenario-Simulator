"""
API Routes
==========
All FastAPI route handlers.
"""

import os
import json
import uuid
import asyncio
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
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
    max_retries=0,
)


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
    loop = asyncio.get_running_loop()
    lock_released = threading.Event()

    def _release_sim_lock():
        # The worker normally releases the lock. If dispatch fails before the
        # worker starts, the request handler releases it instead. Keep this
        # idempotent because an exception from the worker also reaches the
        # handler's except block.
        if not lock_released.is_set():
            lock_released.set()
            _sim_lock.release()

    # Pre-register observer session and start async worker directly on main event loop
    try:
        from backend.observer.pipeline import get_pipeline
        pipeline = get_pipeline()
        pipeline.set_loop(loop)
        participant_names = [p.name for p in req.personas]
        pipeline.get_or_create_session(
            session_id,
            participants=participant_names,
            scenario_description=req.scenario,
        )
        pipeline.start_worker(session_id)
    except Exception as _obs_init_exc:
        logger.warning("Observer startup failed: %s", _obs_init_exc)

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

            analysis_raw = None
            analysis_err_msg = None
            try:
                analysis_raw = analyse_dialogue(
                    dialogue_log=dialogue_log,
                    scenario=req.scenario,
                    decision_point=req.decision_point,
                    personas=[p.model_dump() for p in personas],
                )
            except Exception as exc:
                analysis_err_msg = str(exc)
                logger.error("[Observer Error] Scenario: '%s', Error: %s", req.scenario[:60], exc)

            return SimulationResponse(
                scenario=req.scenario,
                decision_point=req.decision_point,
                dialogue_log=dialogue_log,
                analysis=analysis_raw,
                analysis_error=analysis_err_msg,
                session_id=session_id,
            )
        finally:
            _release_sim_lock()
            # del mem

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run)
        return result
    except Exception as exc:
        _release_sim_lock()
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}")


# ── Multiverse ────────────────────────────────────────────────────────────────

@router.post("/multiverse", response_model=MultiverseResponse)
async def multiverse(req: RunMultiverseRequest):
    if not _sim_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="A simulation is already running. Please wait for it to finish."
        )

    lock_released = threading.Event()

    def _release_sim_lock():
        if not lock_released.is_set():
            lock_released.set()
            _sim_lock.release()

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
            _release_sim_lock()

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run)
        return result
    except Exception as exc:
        _release_sim_lock()
        raise HTTPException(status_code=500, detail=f"Multiverse failed: {exc}")


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
        persona_data = None
        try:
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
        except Exception:
            import re
            desc = req.description
            name_match = re.search(r"(?:(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)|(?:named?\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?))", desc)
            name = name_match.group(0).replace("named", "").replace("name is", "").strip() if name_match else ""
            if not name:
                first_token = desc.split(",")[0].split(".")[0].strip()
                name = first_token if len(first_token) < 25 else "Persona"

            age_match = re.search(r"\b(\d{2})(?:-year-old|yo|\s+years?\s+old|s)?\b", desc)
            age = int(age_match.group(1)) if age_match else 35

            occ = "Professional"
            for candidate in [
                "Cardiologist",
                "Senior ML Engineer",
                "Machine Learning Engineer",
                "AI Researcher",
                "Doctor",
                "Software Engineer",
                "Senior Manager",
                "Student",
                "Music Producer",
                "Musician",
                "Physician",
            ]:
                if candidate.lower() in desc.lower():
                    occ = candidate
                    break

            traits: list[str] = []
            trait_pool = ["analytical", "methodical", "skeptical", "enthusiastic", "technical", "patient", "protective", "passionate", "creative", "direct"]
            for t in trait_pool:
                if t in desc.lower():
                    traits.append(t)
            if not traits:
                traits = ["analytical", "methodical", "pragmatic"]

            persona_data = {
                "name": name,
                "age": age,
                "occupation": occ,
                "personality_traits": traits[:4],
                "values": ["evidence", "safety", "professional excellence"],
                "communication_style": "direct and clear, sometimes technical",
                "emotional_triggers": ["unsupported claims", "feeling dismissed"],
                "background": desc[:250],
                "goals": ["validate claims rigorously", "reach a safe and productive decision"],
            }

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