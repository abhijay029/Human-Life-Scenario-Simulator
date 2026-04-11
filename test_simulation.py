<<<<<<< HEAD
import sys
sys.path.append(".")

from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.simulation.engine import run_simulation

# ── Define two personas ───────────────────────────────────────────────────────
rahul = Persona(
    name="Rahul Sharma",
    age=45,
    occupation="Senior Manager at a private firm",
    personality_traits=["authoritative", "traditional", "protective", "stubborn"],
    values=["family honour", "financial stability", "respect for elders"],
    communication_style="direct and assertive, sometimes dismissive",
    emotional_triggers=["feeling disrespected", "loss of control", "public embarrassment"],
    background="Rahul grew up in a middle-class family in Nagpur. He worked hard to reach his position and believes discipline and sacrifice are the keys to success. He wants the best for his family but struggles to express it without being controlling.",
    goals=["ensure his child makes a safe career choice", "maintain family harmony on his terms"]
)

arjun = Persona(
    name="Arjun Sharma",
    age=21,
    occupation="Final year engineering student",
    personality_traits=["passionate", "idealistic", "conflict-averse", "creative"],
    values=["self-expression", "following his passion", "independence"],
    communication_style="hesitant but earnest, avoids direct confrontation",
    emotional_triggers=["being dismissed", "feeling unheard", "comparisons to others"],
    background="Arjun has always loved music and secretly produces tracks. He is about to graduate and wants to pursue music full time, but fears his father's reaction deeply.",
    goals=["convince his father to support his music career", "avoid a major family conflict"]
)

# ── Pre-load memories for both ────────────────────────────────────────────────
print("Loading persona memories...")
PersonaMemory(rahul.name).store_persona_facts(rahul)
PersonaMemory(arjun.name).store_persona_facts(arjun)

# ── Run the simulation ────────────────────────────────────────────────────────
scenario = "Arjun has just told his father Rahul that he wants to drop his engineering career and pursue music full time after graduation."
decision_point = "Arjun decides to be honest and direct: he tells Rahul he has already been offered a music production deal."

print("\nRunning simulation...\n")
print("=" * 60)
print(f"SCENARIO: {scenario}")
print(f"DECISION: {decision_point}")
print("=" * 60 + "\n")

dialogue = run_simulation(
    personas=[rahul, arjun],
    scenario=scenario,
    decision_point=decision_point,
    max_turns=3
)

for entry in dialogue:
    print(f"[{entry['speaker']}]")
    print(f"{entry['message']}")
=======
import sys
sys.path.append(".")

from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.simulation.engine import run_simulation

# ── Define two personas ───────────────────────────────────────────────────────
rahul = Persona(
    name="Rahul Sharma",
    age=45,
    occupation="Senior Manager at a private firm",
    personality_traits=["authoritative", "traditional", "protective", "stubborn"],
    values=["family honour", "financial stability", "respect for elders"],
    communication_style="direct and assertive, sometimes dismissive",
    emotional_triggers=["feeling disrespected", "loss of control", "public embarrassment"],
    background="Rahul grew up in a middle-class family in Nagpur. He worked hard to reach his position and believes discipline and sacrifice are the keys to success. He wants the best for his family but struggles to express it without being controlling.",
    goals=["ensure his child makes a safe career choice", "maintain family harmony on his terms"]
)

arjun = Persona(
    name="Arjun Sharma",
    age=21,
    occupation="Final year engineering student",
    personality_traits=["passionate", "idealistic", "conflict-averse", "creative"],
    values=["self-expression", "following his passion", "independence"],
    communication_style="hesitant but earnest, avoids direct confrontation",
    emotional_triggers=["being dismissed", "feeling unheard", "comparisons to others"],
    background="Arjun has always loved music and secretly produces tracks. He is about to graduate and wants to pursue music full time, but fears his father's reaction deeply.",
    goals=["convince his father to support his music career", "avoid a major family conflict"]
)

# ── Pre-load memories for both ────────────────────────────────────────────────
print("Loading persona memories...")
PersonaMemory(rahul.name).store_persona_facts(rahul)
PersonaMemory(arjun.name).store_persona_facts(arjun)

# ── Run the simulation ────────────────────────────────────────────────────────
scenario = "Arjun has just told his father Rahul that he wants to drop his engineering career and pursue music full time after graduation."
decision_point = "Arjun decides to be honest and direct: he tells Rahul he has already been offered a music production deal."

print("\nRunning simulation...\n")
print("=" * 60)
print(f"SCENARIO: {scenario}")
print(f"DECISION: {decision_point}")
print("=" * 60 + "\n")

dialogue = run_simulation(
    personas=[rahul, arjun],
    scenario=scenario,
    decision_point=decision_point,
    max_turns=3
)

for entry in dialogue:
    print(f"[{entry['speaker']}]")
    print(f"{entry['message']}")
>>>>>>> 8c6c095954759458197faed706f7478cb7d9f0df
    print()