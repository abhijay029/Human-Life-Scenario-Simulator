import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
import time

load_dotenv(".env")

model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

llm = ChatGoogleGenerativeAI(
    model=model_name,
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=300,
    max_retries=3,
    temperature=0.7,
    max_output_tokens=256   # IMPORTANT
)
# ── State that flows through the graph ──────────────────────────────────────
class SimulationState(TypedDict):
    scenario: str
    personas: list[dict]          # serialised Persona dicts
    dialogue_log: list[dict]      # {"speaker": name, "message": text}
    current_turn: int
    max_turns: int
    decision_point: str           # the user's injected decision
    active_speaker_index: int

# ── Helper: build prompt for one agent turn ──────────────────────────────────
def build_agent_prompt(persona: Persona, memory: PersonaMemory,
                       dialogue_log: list[dict], scenario: str,
                       decision_point: str) -> list:
    # Recall relevant memories for this moment
    recall_query = f"{scenario} {decision_point} {dialogue_log[-1]['message'] if dialogue_log else ''}"
    memories = memory.recall(recall_query, n_results=2)
    memory_context = "\n".join(
        f"- {m[:150]}"   # limit memory length
        for m in memories
    )

    system = SystemMessage(content=f"""
{persona.to_system_prompt()}

RELEVANT MEMORIES ABOUT YOURSELF:
{memory_context}

SCENARIO: {scenario}
DECISION POINT: {decision_point}
""")

    # Build conversation history
    history = []
    for entry in dialogue_log[-4:]:   # last 6 turns for context window efficiency
        if entry["speaker"] == persona.name:
            history.append(AIMessage(content=entry["message"]))
        else:
            history.append(HumanMessage(content=f"{entry['speaker']}: {entry['message']}"))

    if not history:
        history.append(HumanMessage(content=f"The situation begins. {scenario}. {decision_point}"))

    return [system] + history

def safe_llm_invoke(prompt, retries=3):
    for i in range(retries):
        try:
            return llm.invoke(prompt)

        except Exception as e:
            print(f"[Retry {i+1}] LLM error:", e)

            wait_time = 15 * (i + 1)
            print(f"[Waiting {wait_time}s before retry]")

            time.sleep(wait_time)

    raise RuntimeError("LLM failed after retries")

# ── Node: one persona speaks ─────────────────────────────────────────────────
def agent_turn(state: SimulationState) -> SimulationState:
    personas_data = state["personas"]
    idx = state["active_speaker_index"]
    persona_dict = personas_data[idx]
    persona = Persona(**persona_dict)
    memory = PersonaMemory(persona.name)

    prompt = build_agent_prompt(
        persona, memory,
        state["dialogue_log"],
        state["scenario"],
        state["decision_point"]
    )

    total_chars = sum(len(msg.content) for msg in prompt)
    print(f"[DEBUG] Prompt size: {total_chars} chars")
    
    response = safe_llm_invoke(prompt)
    reply = response.content.strip()

    # Store this exchange as a new memory for the persona
    if state["dialogue_log"]:
        last = state["dialogue_log"][-1]
        memory.store_memories_batch(
            [f"During simulation, {last['speaker']} said: '{last['message']}'. "
             f"{persona.name} responded: '{reply[:120]}'"],
            id_prefix=f"{persona.name}_turn_{state['current_turn']}"
        )

    updated_log = state["dialogue_log"] + [{"speaker": persona.name, "message": reply}]
    next_speaker = (idx + 1) % len(personas_data)

    return {
        **state,
        "dialogue_log": updated_log,
        "current_turn": state["current_turn"] + 1,
        "active_speaker_index": next_speaker
    }

# ── Edge condition: keep going or end ────────────────────────────────────────
def should_continue(state: SimulationState) -> str:
    if state["current_turn"] >= state["max_turns"]:
        return "end"
    return "continue"

# ── Build the LangGraph ───────────────────────────────────────────────────────
def build_simulation_graph():
    graph = StateGraph(SimulationState)
    graph.add_node("agent_turn", agent_turn)
    graph.set_entry_point("agent_turn")
    graph.add_conditional_edges(
        "agent_turn",
        should_continue,
        {"continue": "agent_turn", "end": END}
    )
    return graph.compile()

# ── Public entry point ────────────────────────────────────────────────────────
def run_simulation(personas: list[Persona], scenario: str,
                   decision_point: str, max_turns: int = 6) -> list[dict]:
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