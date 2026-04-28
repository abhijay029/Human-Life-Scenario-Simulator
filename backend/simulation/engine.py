import os
import time
from dotenv import load_dotenv
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory

load_dotenv(".env")

model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

llm = ChatGoogleGenerativeAI(
    model=model_name,
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=60,
    max_retries=2,
    temperature=0.7,
    max_output_tokens=600    # tight cap — enough for natural dialogue
)

# Minimum seconds between any two LLM calls globally
# 5 RPM = 1 request per 12s minimum. We use 13s to be safe.
_INTER_REQUEST_DELAY = 15
_last_request_time = 0.0

def _rate_limited_invoke(prompt):
    global _last_request_time
    now = time.time()
    wait = _INTER_REQUEST_DELAY - (now - _last_request_time)
    if wait > 0:
        print(f"[RateLimit] Waiting {wait:.1f}s...")
        time.sleep(wait)
    _last_request_time = time.time()
    return llm.invoke(prompt)

def safe_llm_invoke(prompt, retries=5):
    """Retry Gemini with exponential backoff on any error."""
    for i in range(retries):
        try:
            return _rate_limited_invoke(prompt)
        except Exception as e:
            error_str = str(e).lower()
            
            if "503" in error_str or "unavailable" in error_str:
                wait = 30 * (i + 1)   # 30s, 60s, 90s, 120s, 150s
                print(f"[Gemini 503] Service unavailable. Waiting {wait}s before retry {i+1}/{retries}...")
                time.sleep(wait)

            elif any(k in error_str for k in ["quota", "429", "resource_exhausted", "rate limit"]):
                wait = 60 * (i + 1)   # quota needs longer wait
                print(f"[Gemini 429] Quota hit. Waiting {wait}s before retry {i+1}/{retries}...")
                time.sleep(wait)

            else:
                wait = 20 * (i + 1)
                print(f"[Retry {i+1}/{retries}] LLM error: {e} — waiting {wait}s")
                time.sleep(wait)

    raise RuntimeError("Gemini failed after all retries. Try again in a few minutes.")

# ── State ─────────────────────────────────────────────────────────────────────
class SimulationState(TypedDict):
    scenario: str
    personas: list[dict]
    dialogue_log: list[dict]
    current_turn: int
    max_turns: int
    decision_point: str
    active_speaker_index: int

# ── Prompt builder — lean and token-efficient ─────────────────────────────────
def build_agent_prompt(persona: Persona, memory: PersonaMemory,
                       dialogue_log: list[dict], scenario: str,
                       decision_point: str) -> list:

    # Only recall 1 memory to save tokens
    recall_query = f"{decision_point} {dialogue_log[-1]['message'][:80] if dialogue_log else ''}"
    memories = memory.recall(recall_query, n_results=1)
    memory_context = memories[0][:120] if memories else "None"

    # Compact system prompt — same info, fewer tokens
    system = SystemMessage(content=(
        f"You are {persona.name}, {persona.age}yo {persona.occupation}.\n"
        f"Traits: {', '.join(persona.personality_traits[:3])}.\n"
        f"Values: {', '.join(persona.values[:2])}.\n"
        f"Triggered by: {', '.join(persona.emotional_triggers[:2])}.\n"
        f"Memory: {memory_context}\n"
        f"Situation: {scenario[:200]}\n"
        f"Decision: {decision_point[:150]}\n"
        f"Stay in character. Speak OUT LOUD only — real spoken words, no actions, no stage directions, no text in brackets or parentheses. Reply in 2-3 complete sentences."
    ))

    # Only last 2 turns of history to save tokens
    history = []
    for entry in dialogue_log[-2:]:
        if entry["speaker"] == persona.name:
            history.append(AIMessage(content=entry["message"]))
        else:
            history.append(HumanMessage(content=f"{entry['speaker']}: {entry['message'][:150]}"))

    if not history:
        history.append(HumanMessage(content=f"The situation begins. Respond in character."))

    if isinstance(history[-1], AIMessage):
        history.append(HumanMessage(content="Continue the conversation. Respond in character."))

    return [system] + history

# ── Agent turn node ───────────────────────────────────────────────────────────
def agent_turn(state: SimulationState) -> SimulationState:
    idx = state["active_speaker_index"]
    persona = Persona(**state["personas"][idx])
    memory = PersonaMemory(persona.name)

    prompt = build_agent_prompt(
        persona, memory,
        state["dialogue_log"],
        state["scenario"],
        state["decision_point"]
    )

    total_chars = sum(len(msg.content) for msg in prompt)
    print(f"[Turn {state['current_turn']+1}] {persona.name} | ~{total_chars} chars")

    response = safe_llm_invoke(prompt)

    # Handle both string and list content
    content = response.content
    if isinstance(content, list):
        reply = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    else:
        reply = content.strip()

    # Store exchange as memory (skip embedding call if turn > 2 to save quota)
    if state["dialogue_log"] and state["current_turn"] <= 2:
        last = state["dialogue_log"][-1]
        memory.store_memories_batch(
            [f"{last['speaker']}: '{last['message'][:80]}' → {persona.name}: '{reply[:80]}'"],
            id_prefix=f"{persona.name}_turn_{state['current_turn']}"
        )

    updated_log = state["dialogue_log"] + [{"speaker": persona.name, "message": reply}]
    next_speaker = (idx + 1) % len(state["personas"])

    return {
        **state,
        "dialogue_log": updated_log,
        "current_turn": state["current_turn"] + 1,
        "active_speaker_index": next_speaker
    }

# ── Graph ─────────────────────────────────────────────────────────────────────
def should_continue(state: SimulationState) -> str:
    return "end" if state["current_turn"] >= state["max_turns"] else "continue"

def build_simulation_graph():
    graph = StateGraph(SimulationState)
    graph.add_node("agent_turn", agent_turn)
    graph.set_entry_point("agent_turn")
    graph.add_conditional_edges("agent_turn", should_continue,
                                {"continue": "agent_turn", "end": END})
    return graph.compile()

def run_simulation(personas: list[Persona], scenario: str,
                   decision_point: str, max_turns: int = 4) -> list[dict]:
    graph = build_simulation_graph()
    initial_state: SimulationState = {
        "scenario": scenario,
        "personas": [p.model_dump() for p in personas],
        "dialogue_log": [],
        "current_turn": 0,
        "max_turns": max_turns,
        "decision_point": decision_point,
        "active_speaker_index": 0
    }
    final_state = graph.invoke(initial_state)
    return final_state["dialogue_log"]