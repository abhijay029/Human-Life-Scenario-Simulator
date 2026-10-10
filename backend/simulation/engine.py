import re
from typing import TypedDict, Optional

from pydantic import BaseModel, Field, field_validator
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda

from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.core import llm

# ── Tuning knobs ──────────────────────────────────────────────────────────────
SPEAK_THRESHOLD = 4.0             # best score below this -> nobody wants to talk -> simulation ends
ADDRESSED_BONUS = 3.0             # added when the last message mentions the persona by name
REPEAT_PENALTY = 0.5              # subtracted per turn the persona has already taken
ADDRESSED_URGENCY = 7             # urgency assigned (without an LLM call) when addressed by name
FALLBACK_URGENCY = 2              # urgency used if a bid still fails after all retries
FAILED_BID_REASON = "Bid failed"
HISTORY_WINDOW = 2                # how many recent messages each persona sees
MAX_PARALLEL_BIDS = 4             # cap concurrent bid calls to stay inside API quota
MAX_RETRIES = 3                   # attempts per LLM call (API errors and unparseable output)

_llm = llm.get_engine()


# ── Bid schema + parser ───────────────────────────────────────────────────────
class Bid(BaseModel):
    urgency: int = Field(description="0 = nothing to add, 10 = must speak immediately")
    reason: str = Field(description="One short sentence explaining the urgency")

    @field_validator("urgency")
    @classmethod
    def _clamp(cls, v: int) -> int:
        return max(0, min(10, v))


bid_parser = JsonOutputParser(pydantic_object=Bid)


# ── State ─────────────────────────────────────────────────────────────────────
class SimulationState(TypedDict):
    scenario: str
    personas: list[dict]
    dialogue_log: list[dict]
    current_turn: int
    max_turns: int
    decision_point: str
    next_speaker: Optional[str]      # None -> nobody wants to speak
    last_speaker: Optional[str]
    turn_counts: dict[str, int]


# ── Prompts (plain variables only — no expressions inside braces) ─────────────
speak_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are {name}, {age}yo {occupation}.\n"
     "Traits: {traits}.\n"
     "Values: {values}.\n"
     "Triggered by: {triggers}.\n"
     "Memory: {memory}\n"
     "Situation: {scenario}\n"
     "Decision: {decision_point}\n"
     "Stay in character. Speak OUT LOUD only — real spoken words, no actions, no stage "
     "directions, no text in brackets or parentheses. Reply in 2-3 complete sentences."),
    MessagesPlaceholder("history"),
])

bid_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are {name}, {age}yo {occupation}.\n"
     "Traits: {traits}.\n"
     "Values: {values}.\n"
     "Triggered by: {triggers}.\n"
     "Situation: {scenario}\n"
     "Decision: {decision_point}\n"
     "You are in a live group conversation and do NOT have to speak. Rate how strongly you "
     "want to speak next, 0-10. Rate high (7+) only if you are directly addressed, something "
     "touches your triggers or values, you strongly disagree, or you have a point that cannot "
     "wait. Rate low (0-3) if you have nothing new to add. Never speak just to fill silence.\n"
     "{format_instructions}"),
    ("human", "{recent}"),
]).partial(format_instructions=bid_parser.get_format_instructions())


# ── Chains ────────────────────────────────────────────────────────────────────
def _bid_fallback(inputs: dict) -> Bid:
    """Runs only after every retry failed. `inputs["error"]` is the last exception."""
    print(f"  [bid failed for {inputs.get('name')}] {str(inputs.get('error'))[:150]}")
    return Bid(urgency=FALLBACK_URGENCY, reason=FAILED_BID_REASON)


# prompt -> model -> JSON -> validated Bid. with_retry re-runs the whole chain on API errors
# AND on unparseable/invalid output; with_fallbacks catches whatever still fails.
bid_chain = (
    bid_prompt | _llm | bid_parser | RunnableLambda(Bid.model_validate)
).with_retry(stop_after_attempt=MAX_RETRIES).with_fallbacks(
    [RunnableLambda(_bid_fallback)], exception_key="error"
)

speak_chain = (
    speak_prompt | _llm | StrOutputParser()
).with_retry(stop_after_attempt=MAX_RETRIES)


# ── Helpers ───────────────────────────────────────────────────────────────────
def is_addressed(persona_name: str, message: str) -> bool:
    """True if the message mentions the persona by full name or first name."""
    if not message:
        return False
    first = persona_name.split()[0]
    for candidate in {persona_name, first}:
        if re.search(rf"\b{re.escape(candidate)}\b", message, re.IGNORECASE):
            return True
    return False


# ── Persona agent ─────────────────────────────────────────────────────────────
class PersonaAgent:
    """One agent per persona. Owns the persona's profile and its vector memory
    (created once, not rebuilt every turn). The shared dialogue_log stays the single
    source of truth for the conversation; each agent builds its own view from it."""

    def __init__(self, persona: Persona):
        self.persona = persona
        self.memory = PersonaMemory(persona.name)

    def _profile_vars(self, scenario: str, decision_point: str) -> dict:
        p = self.persona
        return {
            "name": p.name,
            "age": p.age,
            "occupation": p.occupation,
            "traits": ", ".join(p.personality_traits[:3]),
            "values": ", ".join(p.values[:2]),
            "triggers": ", ".join(p.emotional_triggers[:2]),
            "scenario": scenario[:200],
            "decision_point": decision_point[:150],
        }

    # ── Bidding ──
    def bid(self, dialogue_log: list[dict], scenario: str, decision_point: str) -> Bid:
        last_msg = dialogue_log[-1]["message"] if dialogue_log else ""

        # Cheap path: addressed by name -> skip the LLM call entirely
        if is_addressed(self.persona.name, last_msg):
            return Bid(urgency=ADDRESSED_URGENCY, reason="Addressed by name")

        if dialogue_log:
            recent = "\n".join(
                f"{e['speaker']}: {e['message'][:150]}" for e in dialogue_log[-HISTORY_WINDOW:]
            )
        else:
            recent = "The situation just began. Nobody has spoken yet."

        return bid_chain.invoke({**self._profile_vars(scenario, decision_point), "recent": recent})

    # ── Speaking ──
    def speak(self, dialogue_log: list[dict], scenario: str, decision_point: str,
              current_turn: int) -> str:
        # Only recall 1 memory to save tokens
        recall_query = f"{decision_point} {dialogue_log[-1]['message'][:80] if dialogue_log else ''}"
        memories = self.memory.recall(recall_query, n_results=1)
        memory_context = memories[0][:120] if memories else "None"

        history = []
        for entry in dialogue_log[-HISTORY_WINDOW:]:
            if entry["speaker"] == self.persona.name:
                history.append(AIMessage(content=entry["message"]))
            else:
                history.append(HumanMessage(content=f"{entry['speaker']}: {entry['message'][:150]}"))

        if not history:
            history.append(HumanMessage(content="The situation begins. Respond in character."))
        if isinstance(history[-1], AIMessage):
            history.append(HumanMessage(content="Continue the conversation. Respond in character."))

        inputs = {**self._profile_vars(scenario, decision_point),
                  "memory": memory_context, "history": history}
        print(f"[Turn {current_turn + 1}] {self.persona.name} | ~{len(speak_prompt.format(**inputs))} chars")

        reply = speak_chain.invoke(inputs).strip()

        # Store exchange as memory (skip embedding call if turn > 2 to save quota)
        if dialogue_log and current_turn <= 2:
            last = dialogue_log[-1]
            self.memory.store_memories_batch(
                [f"{last['speaker']}: '{last['message'][:80]}' → {self.persona.name}: '{reply[:80]}'"],
                id_prefix=f"{self.persona.name}_turn_{current_turn}",
            )
        return reply


def build_agents(personas: list[Persona]) -> dict[str, PersonaAgent]:
    """{persona_name: persona_agent}"""
    return {p.name: PersonaAgent(p) for p in personas}


# ── Scoring ───────────────────────────────────────────────────────────────────
def score_bid(bid: Bid, addressed: bool, times_spoken: int) -> float:
    return bid.urgency + (ADDRESSED_BONUS if addressed else 0.0) - REPEAT_PENALTY * times_spoken


# ── Routing ───────────────────────────────────────────────────────────────────
def should_continue(state: SimulationState) -> str:
    # No one wants to speak -> the conversation has naturally run its course
    if state.get("next_speaker") is None:
        return "end"
    if state["current_turn"] >= state["max_turns"]:
        return "end"
    return "continue"


# ── Graph ─────────────────────────────────────────────────────────────────────
def build_simulation_graph(agents: dict[str, PersonaAgent]):

    def select_speaker(state: SimulationState) -> dict:
        # Turn cap reached: skip bidding entirely instead of paying for a round we'd discard
        if state["current_turn"] >= state["max_turns"]:
            return {"next_speaker": None}

        log = state["dialogue_log"]
        last_msg = log[-1]["message"] if log else ""
        candidates = [name for name in agents if name != state["last_speaker"]]
        if not candidates:
            return {"next_speaker": None}

        # Parallel bids via the framework's batch(); max_concurrency caps simultaneous calls
        bid_list = RunnableLambda(
            lambda name: agents[name].bid(log, state["scenario"], state["decision_point"])
        ).batch(candidates, config={"max_concurrency": MAX_PARALLEL_BIDS})
        bids = dict(zip(candidates, bid_list))

        scores = {
            name: score_bid(
                bid,
                addressed=is_addressed(name, last_msg),
                times_spoken=state["turn_counts"].get(name, 0),
            )
            for name, bid in bids.items()
        }

        if all(b.reason == FAILED_BID_REASON for b in bids.values()):
            print("  [warning] every bid failed — check the model / bid output format")

        for name, s in sorted(scores.items(), key=lambda kv: -kv[1]):
            print(f"  bid {name}: urgency={bids[name].urgency} score={s:.1f} ({bids[name].reason})")

        best_name, best_score = max(scores.items(), key=lambda kv: kv[1])

        # The very first utterance is always made, so the simulation is never empty
        threshold = 0.0 if not log else SPEAK_THRESHOLD
        return {"next_speaker": best_name if best_score >= threshold else None}

    def speak(state: SimulationState) -> dict:
        name = state["next_speaker"]
        reply = agents[name].speak(
            state["dialogue_log"], state["scenario"],
            state["decision_point"], state["current_turn"],
        )
        counts = dict(state["turn_counts"])
        counts[name] = counts.get(name, 0) + 1
        return {
            "dialogue_log": state["dialogue_log"] + [{"speaker": name, "message": reply}],
            "current_turn": state["current_turn"] + 1,
            "last_speaker": name,
            "turn_counts": counts,
        }

    graph = StateGraph(SimulationState)
    graph.add_node("select_speaker", select_speaker)
    graph.add_node("speak", speak)
    graph.set_entry_point("select_speaker")
    graph.add_conditional_edges("select_speaker", should_continue,
                                {"continue": "speak", "end": END})
    graph.add_edge("speak", "select_speaker")
    return graph.compile()


def run_simulation(personas: list[Persona], scenario: str,
                   decision_point: str, max_turns: int = 4) -> list[dict]:
    agents = build_agents(personas)
    graph = build_simulation_graph(agents)
    initial_state: SimulationState = {
        "scenario": scenario,
        "personas": [p.model_dump() for p in personas],
        "dialogue_log": [],
        "current_turn": 0,
        "max_turns": max_turns,
        "decision_point": decision_point,
        "next_speaker": None,
        "last_speaker": None,
        "turn_counts": {},
    }
    final_state = graph.invoke(initial_state)
    return final_state["dialogue_log"]