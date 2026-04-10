"""
test_multiverse.py
==================
Tests the full Multiverse pipeline:
  - Three decision branches for the same scenario
  - Observer Agent analysis per branch
  - Comparison report (Best / Worst / Most Likely)

Run from the project root:
    python test_multiverse.py
"""

import sys
import json
sys.path.append(".")

from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.simulation.multiverse import run_multiverse, generate_comparison_report

# ── Personas ──────────────────────────────────────────────────────────────────

rahul = Persona(
    name="Rahul Sharma",
    age=45,
    occupation="Senior Manager at a private firm",
    personality_traits=["authoritative", "traditional", "protective", "stubborn"],
    values=["family honour", "financial stability", "respect for elders"],
    communication_style="direct and assertive, sometimes dismissive",
    emotional_triggers=["feeling disrespected", "loss of control", "public embarrassment"],
    background=(
        "Rahul grew up in a middle-class family in Nagpur. He worked hard to reach his "
        "position and believes discipline and sacrifice are the keys to success. He wants "
        "the best for his family but struggles to express it without being controlling."
    ),
    goals=["ensure his child makes a safe career choice", "maintain family harmony on his terms"],
)

arjun = Persona(
    name="Arjun Sharma",
    age=21,
    occupation="Final year engineering student",
    personality_traits=["passionate", "idealistic", "conflict-averse", "creative"],
    values=["self-expression", "following his passion", "independence"],
    communication_style="hesitant but earnest, avoids direct confrontation",
    emotional_triggers=["being dismissed", "feeling unheard", "comparisons to others"],
    background=(
        "Arjun has always loved music and secretly produces tracks. He is about to graduate "
        "and wants to pursue music full time, but fears his father's reaction deeply."
    ),
    goals=["convince his father to support his music career", "avoid a major family conflict"],
)

# ── Pre-load memories ─────────────────────────────────────────────────────────

print("Loading persona memories...")
for persona in [rahul, arjun]:
    mem = PersonaMemory(persona.name)
    if mem.count() == 0:
        mem.store_persona_facts(persona)
        print(f"  Stored memories for {persona.name}")
    else:
        print(f"  {persona.name} memories already cached ({mem.count()} facts)")

# ── Scenario & Branches ───────────────────────────────────────────────────────

scenario = (
    "Arjun has just told his father Rahul that he wants to drop his engineering "
    "career and pursue music full time after graduation."
)

decision_branches = [
    "Arjun is fully honest: he reveals he already has a music production deal worth ₹3 lakh.",
    "Arjun is evasive: he says he 'just wants to explore options' without committing to anything.",
    "Arjun brings a mediator: he asks his mother to be present and starts the conversation gently.",
]

# ── Run Multiverse ────────────────────────────────────────────────────────────

print(f"\nRunning multiverse with {len(decision_branches)} branches...\n")
print("=" * 60)

results = run_multiverse(
    personas=[rahul, arjun],
    scenario=scenario,
    decision_branches=decision_branches,
    max_turns=3,
    max_workers=3,
)

# ── Print Results ─────────────────────────────────────────────────────────────

for i, result in enumerate(results, 1):
    print(f"\n{'='*60}")
    print(f"BRANCH {i}: {result['decision_point']}")
    print("=" * 60)
    print("\nDIALOGUE:")
    for entry in result["dialogue_log"]:
        print(f"  [{entry['speaker']}]: {entry['message'][:200]}...")
    
    analysis = result.get("analysis", {})
    print(f"\nOUTCOME CATEGORY : {analysis.get('outcome_category', 'N/A')}")
    print(f"TRAJECTORY       : {analysis.get('relationship_trajectory', 'N/A')}")
    print(f"OUTCOME SUMMARY  : {analysis.get('outcome_summary', 'N/A')[:300]}")
    
    pgs = analysis.get("persona_goal_success", [])
    if pgs:
        print("\nGOAL SUCCESS PROBABILITIES:")
        for pg in pgs:
            prob = pg.get("success_probability", 0)
            print(f"  {pg['persona']}: {prob:.0%}")
    
    recs = analysis.get("recommendations", [])
    if recs:
        print("\nRECOMMENDATIONS:")
        for r in recs:
            print(f"  • {r}")

# ── Comparison Report ─────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("FINAL COMPARISON REPORT")
print("=" * 60)

report = generate_comparison_report(results)
print(json.dumps(report, indent=2))
