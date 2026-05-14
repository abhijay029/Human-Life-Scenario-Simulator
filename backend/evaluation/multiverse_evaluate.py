import os
import json
from statistics import mean
from typing import List, Dict, Any
from backend.core.llm import get_evaluator
from langchain_core.messages import HumanMessage, SystemMessage
import re
import json

EVALUATION_SYSTEM_PROMPT = """
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

def format_dialogue(dialogue_history: List[Dict[str, Any]]) -> str:
    """
    Converts dialogue history into readable text.
    """

    formatted = []

    for turn in dialogue_history:
        speaker = turn.get("speaker", "Unknown")
        content = turn.get("content", "")

        formatted.append(f"{speaker}: {content}")

    return "\n\n".join(formatted)

def evaluate_branch(
    branch_name: str,
    scenario: str,
    personas: List[Dict[str, Any]],
    dialogue_history: List[Dict[str, Any]],
):
    """
    Evaluates one multiverse branch.
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

        content = re.sub(
            r"```json|```",
            "",
            content
        ).strip()

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

def evaluate_multiverse(multiverse_results: List[Dict[str, Any]]):
    """
    Evaluates all branches and computes averaged scores.
    """

    branch_scores = []

    for branch in multiverse_results:
        branch_name = branch.get("branch_name", "Unnamed Branch")

        print(f"\n[Evaluating Branch] {branch_name}")

        scores = evaluate_branch(
            branch_name=branch_name,
            scenario=branch["scenario"],
            personas=branch["personas"],
            dialogue_history=branch["dialogue_history"],
        )

        branch_scores.append(scores)

        averaged_scores = {
        "persona_consistency": round(mean([
            b["persona_consistency"] for b in branch_scores
        ]), 2),

        "emotional_realism": round(mean([
            b["emotional_realism"] for b in branch_scores
        ]), 2),

        "conversational_coherence": round(mean([
            b["conversational_coherence"] for b in branch_scores
        ]), 2),

        "goal_alignment": round(mean([
            b["goal_alignment"] for b in branch_scores
        ]), 2),

        "conflict_realism": round(mean([
            b["conflict_realism"] for b in branch_scores
        ]), 2),

        "social_plausibility": round(mean([
            b["social_plausibility"] for b in branch_scores
        ]), 2),

        "overall_realism": round(mean([
            b["overall_realism"] for b in branch_scores
        ]), 2),
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
                    "traits": [
                        "traditional",
                        "protective",
                        "emotionally restrained"
                    ],
                    "goals": [
                        "secure son's future",
                        "maintain family stability"
                    ]
                },
                {
                    "name": "Arjun Sharma",
                    "traits": [
                        "creative",
                        "independent",
                        "emotionally expressive"
                    ],
                    "goals": [
                        "pursue passion",
                        "earn father's approval"
                    ]
                }
            ],
            "dialogue_history": [
                {
                    "speaker": "Arjun Sharma",
                    "content": "Dad, I need to talk about my future plans."
                },
                {
                    "speaker": "Rahul Sharma",
                    "content": "You sound serious. What's going on?"
                }
            ]
        }
    ]

    results = evaluate_multiverse(sample_multiverse)

    
    print("AVERAGED MULTIVERSE SCORES")

    print(json.dumps(results["averaged_scores"], indent=2))

    print("PER BRANCH RESULTS")

    print(json.dumps(results["branch_results"], indent=2))
        