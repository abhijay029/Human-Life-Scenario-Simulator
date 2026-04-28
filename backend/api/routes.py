"""
API Routes
==========
All FastAPI route handlers.
"""

import os
import json
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
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
            )
        finally:
            _sim_lock.release()

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