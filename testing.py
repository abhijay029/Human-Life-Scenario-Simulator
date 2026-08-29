"""
testing.py
===================================
End-to-end test that:
  1. Runs a full multiverse simulation (3 branches)
  2. Prints Observer Agent analysis per branch
  3. Generates a comparison report (Best / Worst / Most Likely)
  4. Passes the results to multiverse_evaluate.py for LLM-based scoring
  5. Prints averaged + per-branch evaluation scores

Run from the project root:
    python test_multiverse_with_evaluation.py
"""

import sys
import json

sys.path.append(".")

from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.simulation.multiverse import run_multiverse, generate_comparison_report
from backend.evaluation.multiverse_evaluate import evaluate_multiverse

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

personas = [rahul, arjun]

# ── Pre-load memories ─────────────────────────────────────────────────────────

print("=" * 60)
print("STEP 1: Loading persona memories")
print("=" * 60)

for persona in personas:
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

print(f"\n{'=' * 60}")
print(f"STEP 2: Running multiverse ({len(decision_branches)} branches)")
print("=" * 60)

multiverse_results = run_multiverse(
    personas=personas,
    scenario=scenario,
    decision_branches=decision_branches,
    max_turns=5,
)

# ── Print Simulation Results ──────────────────────────────────────────────────

print(f"\n{'=' * 60}")
print("STEP 3: Simulation results (sorted best → worst by goal success)")
print("=" * 60)

for i, result in enumerate(multiverse_results, 1):
    print(f"\n{'─' * 60}")
    print(f"BRANCH {i}: {result['decision_point']}")
    print("─" * 60)

    print("\nDIALOGUE:")
    if result["dialogue_log"]:
        for entry in result["dialogue_log"]:
            print(f"  [{entry['speaker']}]: {entry['message'][:200]}...")
    else:
        print("  (no dialogue — branch failed)")

    analysis = result.get("analysis", {})
    if "error" in analysis:
        print(f"\n  [Analysis Error]: {analysis['error']}")
    else:
        print(f"\n  OUTCOME CATEGORY : {analysis.get('outcome_category', 'N/A')}")
        print(f"  TRAJECTORY       : {analysis.get('relationship_trajectory', 'N/A')}")
        print(f"  OUTCOME SUMMARY  : {analysis.get('outcome_summary', 'N/A')[:300]}")

        pgs = analysis.get("persona_goal_success", [])
        if pgs:
            print("\n  GOAL SUCCESS PROBABILITIES:")
            for pg in pgs:
                prob = pg.get("success_probability", 0)
                print(f"    {pg['persona']}: {prob:.0%}")

        recs = analysis.get("recommendations", [])
        if recs:
            print("\n  RECOMMENDATIONS:")
            for rec in recs:
                print(f"    • {rec}")

# ── Comparison Report ─────────────────────────────────────────────────────────

print(f"\n{'=' * 60}")
print("STEP 4: Comparison report")
print("=" * 60)

comparison = generate_comparison_report(multiverse_results)
print(json.dumps(comparison, indent=2, ensure_ascii=False))

# ── Evaluate with multiverse_evaluate ────────────────────────────────────────

print(f"\n{'=' * 60}")
print("STEP 5: LLM-based realism evaluation")
print("=" * 60)

# Convert personas to plain dicts for the evaluator
personas_dicts = [p.model_dump() for p in personas]

evaluation = evaluate_multiverse(
    multiverse_results=multiverse_results,   # already has "decision_point" + "dialogue_log"
    scenario=scenario,                        # shared fallback for branches missing "scenario"
    personas=personas_dicts,                  # shared fallback for branches missing "personas"
)

# ── Print Evaluation Results ──────────────────────────────────────────────────

print(f"\n{'─' * 60}")
print("PER-BRANCH EVALUATION SCORES")
print("─" * 60)

score_labels = {
    "persona_consistency":      "Persona Consistency",
    "emotional_realism":        "Emotional Realism",
    "conversational_coherence": "Conversational Coherence",
    "goal_alignment":           "Goal Alignment",
    "conflict_realism":         "Conflict Realism",
    "social_plausibility":      "Social Plausibility",
    "overall_realism":          "Overall Realism",
}

for branch_eval in evaluation["branch_results"]:
    print(f"\n  Branch : {branch_eval['branch_name'][:80]}")
    for key, label in score_labels.items():
        score = branch_eval.get(key, "N/A")
        bar = "█" * int(score) if isinstance(score, (int, float)) else ""
        print(f"    {label:<28}: {score:>4}  {bar}")
    summary = branch_eval.get("summary", "")
    if summary:
        print(f"    Summary: {summary}")

print(f"\n{'─' * 60}")
print("AVERAGED SCORES ACROSS ALL BRANCHES")
print("─" * 60)

avg = evaluation["averaged_scores"]
for key, label in score_labels.items():
    score = avg.get(key, 0)
    bar = "█" * int(score)
    print(f"  {label:<28}: {score:>4}  {bar}")

print(f"\n{'=' * 60}")
print("TEST COMPLETE")
print("=" * 60)