"""
test_metric_at_k.py
====================
Evaluation protocol:

  For 5 auto-generated scenarios:
    - Each scenario has 5 pre-generated branches
    - Round k  (k = 1..5): simulate only the first k branches (max_turns=5)
    - Score every branch with multiverse_evaluate → average across k branches
      → multiverse metric@k  for this scenario

  Final metric@k = average of multiverse metric@k across all 5 scenarios

Display:
  • Per-scenario: multiverse metric@k  (k=1..5)
  • Global:       final metric@k       (k=1..5)

Run from project root:
    python test_metric_at_k.py
"""

import sys
import json
import re
from statistics import mean

sys.path.append(".")

from langchain_core.messages import SystemMessage, HumanMessage
from backend.agents.persona import Persona
from backend.memory.memory_manager import PersonaMemory
from backend.simulation.multiverse import run_multiverse
from backend.evaluation.multiverse_evaluate import evaluate_multiverse
from backend.core.llm import get_evaluator          # reuse same Ollama model for generation
import os
from datetime import datetime
import unicodedata

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

NUM_SCENARIOS   = 5
NUM_BRANCHES    = 5
MAX_TURNS       = 5
K_VALUES        = list(range(1, NUM_BRANCHES + 1))   # [1, 2, 3, 4, 5]

SCORE_KEYS = [
    "persona_consistency",
    "emotional_realism",
    "conversational_coherence",
    "goal_alignment",
    "conflict_realism",
    "social_plausibility",
    "overall_realism",
]

SCORE_LABELS = {
    "persona_consistency":      "Persona Consistency",
    "emotional_realism":        "Emotional Realism",
    "conversational_coherence": "Conversational Coherence",
    "goal_alignment":           "Goal Alignment",
    "conflict_realism":         "Conflict Realism",
    "social_plausibility":      "Social Plausibility",
    "overall_realism":          "Overall Realism",
}

# ─────────────────────────────────────────────────────────────────────────────
# LLM helpers
# ─────────────────────────────────────────────────────────────────────────────

_gen_llm = get_evaluator()   # Ollama model — used for generation too


import time

def _repair_json(raw: str) -> str:
    # Normalise unicode punctuation to ASCII equivalents or remove
    raw = unicodedata.normalize("NFKD", raw)
    raw = raw.encode("ascii", errors="ignore").decode("ascii")

    # Trailing commas
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    # Literal newlines inside strings
    raw = re.sub(r'(?<=[^{[\n])\n(?=[^}\]\n])', r'\\n', raw)
    # All remaining control characters including tab
    raw = re.sub(r'[\x00-\x1f\x7f]', '', raw)
    return raw


def _invoke_json(system: str, user: str, label: str,
                 retries: int = 3, retry_delay: float = 4.0) -> dict | list:
    """
    Call the LLM, strip markdown fences, attempt JSON repair, parse.
    Retries up to `retries` times on any failure before raising.
    """
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            messages = [SystemMessage(content=system), HumanMessage(content=user)]
            response = _gen_llm.invoke(messages)
            raw = response.content.strip()

            # print(f"\n[DEBUG _invoke_json | {label} | attempt {attempt}]")
            # print(f"  type(response.content) = {type(response.content)}")
            # print(f"  raw (first 500 chars):\n{raw[:500]}")
            # print(f"[END DEBUG]\n")
            
            # Strip markdown code fences
            raw = re.sub(r"```json|```", "", raw).strip()

            # Locate the outermost JSON structure
            brace   = raw.find("{")
            bracket = raw.find("[")

            if brace == -1 and bracket == -1:
                raise ValueError(f"No JSON object or array found in response.")

            if brace == -1:
                start = bracket
            elif bracket == -1:
                start = brace
            else:
                start = min(brace, bracket)

            end_brace   = raw.rfind("}") + 1
            end_bracket = raw.rfind("]") + 1
            end = max(end_brace, end_bracket)

            if end == 0:
                raise ValueError("Could not find closing brace/bracket.")

            candidate = raw[start:end]

            # First attempt: parse as-is
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            # Second attempt: repair then parse
            repaired = _repair_json(candidate)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON parse failed after repair: {e}\n"
                                 f"Raw snippet: {candidate[:300]}")

        except Exception as e:
            last_error = e
            if attempt < retries:
                print(f"  [Warning] {label} attempt {attempt}/{retries} failed: {e}")
                print(f"  Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"  [Error] {label} failed after {retries} attempts: {e}")

    raise RuntimeError(
        f"[{label}] Could not obtain valid JSON after {retries} attempts. "
        f"Last error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario + branch generation
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO_GEN_SYSTEM = """You are a creative writer specialising in realistic human drama.
Generate exactly 5 distinct, emotionally charged human-life scenarios.
Each scenario must involve exactly 2 named personas in a tense interpersonal situation
(e.g. family conflict, workplace dispute, friendship breakdown, romantic tension,
moral dilemma between strangers).

Return ONLY a raw JSON array. No markdown. No code fences. No explanation.
The array must contain exactly 5 objects. Each object must have exactly these keys:

[
  {
    "scenario_description": "2-3 sentence setup string",
    "persona_a": {
      "name": "Full Name",
      "age": 35,
      "occupation": "Job title",
      "personality_traits": ["trait1", "trait2", "trait3", "trait4"],
      "values": ["value1", "value2", "value3"],
      "communication_style": "one descriptive phrase",
      "emotional_triggers": ["trigger1", "trigger2", "trigger3"],
      "background": "2-3 sentences of life context",
      "goals": ["goal1 in this situation", "goal2 in this situation"]
    },
    "persona_b": {
      "name": "Full Name",
      "age": 28,
      "occupation": "Job title",
      "personality_traits": ["trait1", "trait2", "trait3", "trait4"],
      "values": ["value1", "value2", "value3"],
      "communication_style": "one descriptive phrase",
      "emotional_triggers": ["trigger1", "trigger2", "trigger3"],
      "background": "2-3 sentences of life context",
      "goals": ["goal1 in this situation", "goal2 in this situation"]
    }
  }
]

STRICT RULES:
- All string values must use double quotes.
- No trailing commas.
- No comments inside the JSON.
- Keep every string value on a single line — no line breaks inside strings.
- Make scenarios diverse: vary relationship types, cultures, age gaps, conflict types.
"""

BRANCH_GEN_SYSTEM = """You are a narrative designer creating decision branches for a human-life simulation.
Given a scenario and two personas, generate exactly 5 distinct decision branches.
Each branch is a single sentence describing a concrete action or choice that Persona A makes
at the start of the interaction.

The 5 branches must vary meaningfully in strategy/tone:
  direct/honest, evasive/indirect, aggressive, conciliatory, creative/unexpected.

Return ONLY a raw JSON array of exactly 5 strings. No markdown. No code fences. No explanation.
Example format:
["Branch one sentence.", "Branch two sentence.", "Branch three sentence.", "Branch four sentence.", "Branch five sentence."]

STRICT RULES:
- Use double quotes for all strings.
- No trailing commas.
- The entire response must be a single JSON array on one or a few lines.
"""


def generate_scenarios() -> list[dict]:
    print("\n[Generator] Creating 5 scenarios...")
    data = _invoke_json(
        system=SCENARIO_GEN_SYSTEM,
        user="Generate 5 diverse human-life scenarios now.",
        label="ScenarioGen",
    )
    assert isinstance(data, list) and len(data) == 5, \
        f"Expected list of 5, got: {type(data)} len={len(data) if isinstance(data, list) else '?'}"
    print(f"  ✓ Generated {len(data)} scenarios")
    return data


def generate_branches(scenario_description: str, persona_a: dict, persona_b: dict) -> list[str]:
    user_prompt = (
        f"Scenario: {scenario_description}\n\n"
        f"Persona A ({persona_a['name']}): "
        f"traits={persona_a['personality_traits']}, goals={persona_a['goals']}\n\n"
        f"Persona B ({persona_b['name']}): "
        f"traits={persona_b['personality_traits']}, goals={persona_b['goals']}\n\n"
        "Generate 5 distinct decision branches for Persona A."
    )
    data = _invoke_json(system=BRANCH_GEN_SYSTEM, user=user_prompt, label="BranchGen")

    # ── Normalise whatever shape the model returned ───────────────────────────
    # Expected: ["str", "str", ...]
    # Seen:     [["str", "str", ...]]  or  [{"branch": "str"}, ...]

    # Unwrap a single-element outer list wrapping the real list
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
        data = data[0]

    # Convert list-of-dicts to list-of-strings (take the first string value found)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = [
            next((v for v in item.values() if isinstance(v, str)), str(item))
            for item in data
        ]

    # Final guard: ensure every element is a plain string
    data = [str(item) if not isinstance(item, str) else item for item in data]

    assert len(data) == 5, f"Expected 5 branches, got {len(data)}: {data}"
    return data


def build_persona(raw: dict) -> Persona:
    return Persona(
        name=raw["name"],
        age=int(raw["age"]),
        occupation=raw["occupation"],
        personality_traits=raw["personality_traits"],
        values=raw["values"],
        communication_style=raw["communication_style"],
        emotional_triggers=raw["emotional_triggers"],
        background=raw["background"],
        goals=raw["goals"],
    )


def preload_memories(personas: list[Persona]):
    for p in personas:
        mem = PersonaMemory(p.name)
        if mem.count() == 0:
            mem.store_persona_facts(p)


# ─────────────────────────────────────────────────────────────────────────────
# Metric helpers
# ─────────────────────────────────────────────────────────────────────────────

def average_metric(score_dicts: list[dict]) -> dict:
    valid = [d for d in score_dicts if not d.get("evaluation_failed", False)]
    if not valid:
        valid = score_dicts

    return {
        **{
            key: round(mean(d.get(key, 0) for d in valid), 2)
            for key in SCORE_KEYS
        },
        "valid_branch_count": len(valid),
        "failed_branch_count": len(score_dicts) - len(valid),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_metric(metric: dict, indent: int = 4):
    pad = " " * indent
    for key in SCORE_KEYS:
        label  = SCORE_LABELS[key]
        score  = metric.get(key, 0)
        bar    = "█" * int(score) + "░" * (10 - int(score))
        print(f"{pad}{label:<28}: {score:>4}  {bar}")


def print_section(title: str, width: int = 70):
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}")


def print_subsection(title: str, width: int = 70):
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}")

def save_json_log(data: dict | list, filename: str):
    """Write data as indented JSON to the project root. Overwrites on each run."""
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  [Log] Saved → {path}")

# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print_section("METRIC@K EVALUATION — Human Life Scenario Simulator")

    # ── Step 1: Generate all scenarios and branches ───────────────────────────
    raw_scenarios = generate_scenarios()

    scenario_data = []   # will hold enriched dicts with branches + personas
    for idx, raw in enumerate(raw_scenarios, 1):
        print(f"\n[Setup] Scenario {idx}: {raw['scenario_description'][:80]}...")
        branches = generate_branches(
            scenario_description=raw["scenario_description"],
            persona_a=raw["persona_a"],
            persona_b=raw["persona_b"],
        )
        print(f"   Generated {len(branches)} branches")
        persona_a = build_persona(raw["persona_a"])
        persona_b = build_persona(raw["persona_b"])
        preload_memories([persona_a, persona_b])
        print(f"   Memories loaded for {persona_a.name} & {persona_b.name}")

        scenario_data.append({
            "index":       idx,
            "description": raw["scenario_description"],
            "personas":    [persona_a, persona_b],
            "branches":    branches,         # list of 5 branch strings
        })

    # ── Save scenario + branch log ────────────────────────────────────────────
    scenario_log = [
        {
            "scenario_index":       s["index"],
            "scenario_description": s["description"],
            "persona_a":            s["personas"][0].model_dump(),
            "persona_b":            s["personas"][1].model_dump(),
            "branches":             s["branches"],
        }
        for s in scenario_data
    ]
    save_json_log(scenario_log, "test_scenario_log.json")

    # ── Step 2: Run simulations and evaluate ──────────────────────────────────
    #
    # Structure we build:
    #
    #   all_scenario_metric_at_k[scenario_idx][k] = multiverse metric@k dict
    #
    # where k ∈ {1,2,3,4,5}

    all_scenario_metric_at_k = []   # one entry per scenario; each entry: dict k→metric

    for s in scenario_data:
        sidx      = s["index"]
        personas  = s["personas"]
        branches  = s["branches"]          # 5 branch strings
        scenario  = s["description"]
        personas_dicts = [p.model_dump() for p in personas]

        print_subsection(f"Scenario {sidx} / {NUM_SCENARIOS}: {scenario[:60]}...")

        # Run the full multiverse once with all 5 branches (max_turns=5)
        # Then slice results for each k — avoids re-simulating the same branches
        print(f"  [Sim] Running multiverse with all {NUM_BRANCHES} branches "
              f"(max_turns={MAX_TURNS})...")

        all_branch_results = run_multiverse(
            personas=personas,
            scenario=scenario,
            decision_branches=branches,
            max_turns=MAX_TURNS,
        )

        # run_multiverse() sorts results by avg goal-success (best first).
        # For metric@k we need a stable order so k=1 always means branch 1, etc.
        # Restore the original branch order using the decision_point string.
        branch_order = {b: i for i, b in enumerate(branches)}
        all_branch_results_sorted = sorted(
            all_branch_results,
            key=lambda r: branch_order.get(r["decision_point"], 999),
        )

        scenario_metric_at_k = {}   # k → multiverse metric@k

        for k in K_VALUES:
            # Take the first k branches in original order
            k_branches = all_branch_results_sorted[:k]

            print(f"  [Eval] metric@{k} — evaluating {k} branch(es)...")

            eval_result = evaluate_multiverse(
                multiverse_results=k_branches,
                scenario=scenario,
                personas=personas_dicts,
            )

            # eval_result["branch_results"] is a list of k score dicts
            # Average across those k dicts → multiverse metric@k for this scenario
            branch_score_dicts = eval_result["branch_results"]
            multiverse_metric_at_k = average_metric(branch_score_dicts)

            scenario_metric_at_k[k] = multiverse_metric_at_k
            print(f"     overall_realism={multiverse_metric_at_k['overall_realism']}")

        all_scenario_metric_at_k.append({
            "scenario_index": sidx,
            "description":    scenario,
            "metric_at_k":    scenario_metric_at_k,   # {1: {...}, 2: {...}, ...}
        })

    # ── Step 3: Average multiverse metric@k across scenarios → final metric@k ─
    #
    #   final_metric_at_k[k] = average of all_scenario_metric_at_k[*]["metric_at_k"][k]

    final_metric_at_k = {}
    for k in K_VALUES:
        per_scenario_metrics = [
            s["metric_at_k"][k] for s in all_scenario_metric_at_k
        ]
        final_metric_at_k[k] = average_metric(per_scenario_metrics)

    # ═════════════════════════════════════════════════════════════════════════
    # DISPLAY RESULTS
    # ═════════════════════════════════════════════════════════════════════════

    print_section("RESULTS")

    # ── Per-scenario: multiverse metric@k for each k ─────────────────────────
    for s in all_scenario_metric_at_k:
        sidx = s["scenario_index"]
        print_subsection(
            f"Scenario {sidx}: {s['description'][:65]}..."
        )
        print(f"  Multiverse metric@k  (k = 1 → {NUM_BRANCHES} branches)\n")
        for k in K_VALUES:
            print(f"    ── metric@{k}  [{k} branch{'es' if k > 1 else ''} considered] ──")
            print_metric(s["metric_at_k"][k], indent=6)

    # ── Final metric@k across all scenarios ──────────────────────────────────
    print_section(
        f"FINAL metric@k  (averaged across all {NUM_SCENARIOS} scenarios)"
    )
    print(f"  k = number of branches considered per scenario\n")

    for k in K_VALUES:
        print(f"\n  ── Final metric@{k}  [{k} branch{'es' if k > 1 else ''} per scenario] ──")
        print_metric(final_metric_at_k[k], indent=4)

    # Also dump as JSON for easy logging / downstream use
    print_section("FINAL metric@k — JSON")
    output = {
        f"metric@{k}": final_metric_at_k[k]
        for k in K_VALUES
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))

    # ── Save scores log ───────────────────────────────────────────────────────
    system_score = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "num_scenarios": NUM_SCENARIOS,
        "num_branches":  NUM_BRANCHES,
        "max_turns":     MAX_TURNS,
        "multiverse_metric_at_k_per_scenario": [
            {
                "scenario_index":       s["scenario_index"],
                "scenario_description": s["description"],
                "metric_at_k": {
                    f"metric@{k}": s["metric_at_k"][k]
                    for k in K_VALUES
                },
            }
            for s in all_scenario_metric_at_k
        ],
        "final_metric_at_k": {
            f"metric@{k}": final_metric_at_k[k]
            for k in K_VALUES
        },
    }
    save_json_log(system_score, "system_score.json")

    print_section("EVALUATION COMPLETE")


if __name__ == "__main__":
    main()