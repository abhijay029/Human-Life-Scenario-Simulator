import os
import json
from statistics import mean
from typing import List, Dict, Any
from backend.core.llm import get_evaluator
from langchain_core.messages import HumanMessage, SystemMessage
import re

EVALUATION_SYSTEM_PROMPT = """You are an expert evaluator assessing whether AI-simulated human conversations are \
psychologically believable, emotionally coherent, and socially plausible.

You must evaluate the following metrics from 1 to 10:

1. persona_consistency
- Does each character behave according to their defined personality,
  values, emotional tendencies, and communication style?

2. emotional_realism
- Are emotional reactions believable and gradual?
- Do emotional transitions make sense?

3. conversational_coherence
- Does the conversation logically flow?
- Do responses address previous statements appropriately?

4. goal_alignment
- Are the character decisions aligned with their goals and motivations?

5. conflict_realism
- Does the conflict escalation/de-escalation feel natural?
- Is the tension progression believable?

6. social_plausibility
- Would real humans likely behave like this in real life?

7. overall_realism
- Overall realism and believability of the interaction.

IMPORTANT:
- Return ONLY valid JSON.
- Do not include markdown.
- Do not include explanations outside JSON.

Expected format:

{
  "persona_consistency": 8.4,
  "emotional_realism": 7.9,
  "conversational_coherence": 8.2,
  "goal_alignment": 8.8,
  "conflict_realism": 7.5,
  "social_plausibility": 8.1,
  "overall_realism": 8.0,
  "summary": "Brief explanation"
}
"""

SCORE_KEYS = [
    "persona_consistency",
    "emotional_realism",
    "conversational_coherence",
    "goal_alignment",
    "conflict_realism",
    "social_plausibility",
    "overall_realism",
]


def format_dialogue(dialogue_history: List[Dict[str, Any]]) -> str:
    """
    Converts dialogue history into readable text.
    Handles both {"speaker", "message"} (engine format)
    and {"speaker", "content"} (legacy format).
    """
    formatted = []
    for turn in dialogue_history:
        speaker = turn.get("speaker", "Unknown")
        content = turn.get("message") or turn.get("content", "")
        formatted.append(f"{speaker}: {content}")
    return "\n\n".join(formatted)


def evaluate_branch(
    branch_name: str,
    scenario: str,
    personas: List[Dict[str, Any]],
    dialogue_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluates one multiverse branch.
    Returns a dict with score keys + branch_name + summary.
    """
    llm = get_evaluator()

    personas_text = json.dumps(personas, indent=2)
    dialogue_text = format_dialogue(dialogue_history)

    user_prompt = f"""
SCENARIO:
{scenario}

PERSONAS:
{personas_text}

DIALOGUE:
{dialogue_text}

Evaluate the realism and behavioral accuracy of this conversation.
"""

    messages = [
        SystemMessage(content=EVALUATION_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()

        # Strip markdown fences if present
        content = re.sub(r"```json|```", "", content).strip()

        scores = json.loads(content)
        scores["branch_name"] = branch_name
        return scores

    except Exception as e:
        print(f"[Evaluation Error] {branch_name}: {e}")
        return {
            "branch_name": branch_name,
            "persona_consistency": 0,
            "emotional_realism": 0,
            "conversational_coherence": 0,
            "goal_alignment": 0,
            "conflict_realism": 0,
            "social_plausibility": 0,
            "overall_realism": 0,
            "summary": f"Evaluation failed: {str(e)}",
        }


def evaluate_multiverse(
    multiverse_results: List[Dict[str, Any]],
    scenario: str = "",
    personas: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates all branches from run_multiverse() output and computes averaged scores.

    Parameters
    ----------
    multiverse_results : output of run_multiverse()
        Each item has keys: "decision_point", "dialogue_log", "analysis"
    scenario : the shared scenario string that was passed to run_multiverse()
    personas : list of persona dicts that was passed to run_multiverse()

    Returns
    -------
    {
        "branch_results": [ {...scores, branch_name}, ... ],
        "averaged_scores": { metric: float, ... }
    }
    """
    if personas is None:
        personas = []

    branch_scores = []

    for branch in multiverse_results:
        # Normalise keys — run_multiverse() uses "decision_point" and "dialogue_log"
        # but legacy/direct callers may use "branch_name" and "dialogue_history"
        branch_name     = branch.get("decision_point") or branch.get("branch_name", "Unnamed Branch")
        branch_scenario = branch.get("scenario") or scenario
        branch_personas = branch.get("personas") or personas
        branch_dialogue = branch.get("dialogue_log") or branch.get("dialogue_history", [])

        print(f"\n[Evaluating Branch] {branch_name[:80]}...")

        scores = evaluate_branch(
            branch_name=branch_name,
            scenario=branch_scenario,
            personas=branch_personas,
            dialogue_history=branch_dialogue,
        )

        branch_scores.append(scores)

    # averaged_scores is computed AFTER the loop, not inside it
    averaged_scores = {
        key: round(mean(b.get(key, 0) for b in branch_scores), 2)
        for key in SCORE_KEYS
    }

    return {
        "branch_results": branch_scores,
        "averaged_scores": averaged_scores,
    }


if __name__ == "__main__":
    sample_multiverse = [
        {
            "branch_name": "Honest Conversation",
            "scenario": "A son tells his father he wants to pursue music instead of engineering.",
            "personas": [
                {
                    "name": "Rahul Sharma",
                    "traits": ["traditional", "protective", "emotionally restrained"],
                    "goals": ["secure son's future", "maintain family stability"],
                },
                {
                    "name": "Arjun Sharma",
                    "traits": ["creative", "independent", "emotionally expressive"],
                    "goals": ["pursue passion", "earn father's approval"],
                },
            ],
            "dialogue_history": [
                {"speaker": "Arjun Sharma", "content": "Dad, I need to talk about my future plans."},
                {"speaker": "Rahul Sharma", "content": "You sound serious. What's going on?"},
            ],
        }
    ]

    results = evaluate_multiverse(sample_multiverse)

    print("\nAVERAGED MULTIVERSE SCORES")
    print(json.dumps(results["averaged_scores"], indent=2))
    print("\nPER BRANCH RESULTS")
    print(json.dumps(results["branch_results"], indent=2))