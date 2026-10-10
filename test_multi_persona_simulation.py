import sys
sys.path.append(".")

from collections import Counter

from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.simulation.engine import run_simulation

# ── Define four personas ──────────────────────────────────────────────────────
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

meera = Persona(
    name="Meera Sharma",
    age=42,
    occupation="School teacher and homemaker",
    personality_traits=["empathetic", "diplomatic", "observant", "quietly firm"],
    values=["family unity", "her children's happiness", "open communication"],
    communication_style="soft-spoken and calming, steps in when tension rises",
    emotional_triggers=["family members shouting", "being caught between husband and son", "hearing her son is unhappy"],
    background="Meera has spent two decades keeping peace between Rahul's expectations and the children's dreams. She secretly knew about Arjun's music and has heard his tracks. She fears this conflict could damage the father-son bond permanently.",
    goals=["prevent a rift between Rahul and Arjun", "help both of them actually hear each other"]
)

kavya = Persona(
    name="Kavya Sharma",
    age=26,
    occupation="Software engineer in Pune",
    personality_traits=["blunt", "witty", "pragmatic", "protective of her brother"],
    values=["honesty", "fairness", "financial independence"],
    communication_style="sharp and sarcastic, says what others avoid saying",
    emotional_triggers=["double standards", "being used as the example of the 'good child'", "seeing Arjun bullied"],
    background="Kavya followed the safe engineering path her father wanted and is successful but quietly unfulfilled. She is tired of being held up as the model child and thinks Arjun deserves the choice she never felt she had.",
    goals=["back Arjun without escalating the fight", "make her father see the cost of controlling everyone's choices"]
)

personas = [rahul, arjun, meera, kavya]

# ── Pre-load memories for all four ────────────────────────────────────────────
print("Loading persona memories...")
for p in personas:
    PersonaMemory(p.name).store_persona_facts(p)

# ── Run the simulation ────────────────────────────────────────────────────────
scenario = (
    "At the Sharma family dinner table, Arjun has just told everyone that he wants to drop "
    "his engineering career and pursue music full time after graduation. Rahul, Meera and "
    "Kavya are all present."
)
decision_point = (
    "Arjun decides to be honest and direct: he tells the family he has already been offered "
    "a music production deal."
)

print("\nRunning simulation...\n")
print("=" * 60)
print(f"SCENARIO: {scenario}")
print(f"DECISION: {decision_point}")
print("=" * 60 + "\n")

dialogue = run_simulation(
    personas=personas,
    scenario=scenario,
    decision_point=decision_point,
    max_turns=10
)

print("\n" + "=" * 60)
print("DIALOGUE")
print("=" * 60 + "\n")

for entry in dialogue:
    print(f"[{entry['speaker']}]")
    print(f"{entry['message']}")
    print()

# ── Sanity checks on the bidding behaviour ────────────────────────────────────
print("=" * 60)
print("SPEAKING ORDER:", " -> ".join(e["speaker"].split()[0] for e in dialogue))
print("TURNS PER PERSONA:", dict(Counter(e["speaker"] for e in dialogue)))

speakers = [e["speaker"] for e in dialogue]
print("Consecutive repeats:", any(a == b for a, b in zip(speakers, speakers[1:])))
print("Ended early (before max_turns):", len(dialogue) < 10)
print("Order differs from round-robin:", speakers != [personas[i % 4].name for i in range(len(speakers))])