import sys
sys.path.append(".")

from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory

rahul = Persona(
    name="Rahul Sharma",
    age=45,
    occupation="Senior Manager at a private firm",
    personality_traits=["authoritative", "traditional", "protective", "stubborn"],
    values=["family honour", "financial stability", "respect for elders"],
    communication_style="direct and assertive, sometimes dismissive",
    emotional_triggers=["feeling disrespected", "loss of control", "public embarrassment"],
    background="Rahul grew up in a middle-class family in Nagpur. He worked hard to reach his position and believes discipline and sacrifice are the keys to success. He wants the best for his family but struggles to express it without being controlling.",
    goals=["ensure his child makes a 'safe' career choice", "maintain family harmony on his terms"]
)

memory = PersonaMemory(persona_name=rahul.name)

# Only store if collection is empty (avoids re-embedding on every test run)
if memory.collection.count() == 0:
    print("=== STORING PERSONA MEMORY (first time) ===")
    memory.store_persona_facts(rahul)
else:
    print(f"=== MEMORY ALREADY EXISTS ({memory.collection.count()} facts cached) — skipping store ===")

print("\n=== TESTING MEMORY RECALL ===")
query = "How does Rahul react when someone challenges his decisions?"
recalled = memory.recall(query)
print(f"Query: '{query}'")
for m in recalled:
    print(f"  - {m}")