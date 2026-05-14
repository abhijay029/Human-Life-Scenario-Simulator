import os
import time
from dotenv import load_dotenv
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.core import llm

_llm = llm.get_engine() 

def safe_llm_invoke(prompt):
    try:
        return _llm.invoke(prompt)
    except Exception as e:
        error_str = str(e).lower()
        print(f"[Engine: {_llm.model}] Exception: \n{error_str}\n")

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