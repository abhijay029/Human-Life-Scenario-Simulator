import os
import json
from statistics import mean
from typing import List, Dict, Any
from backend.core.llm import get_evaluator
from langchain_core.messages import HumanMessage, SystemMessage
import re
import time
import unicodedata

llm = get_evaluator()

EVALUATION_SYSTEM_PROMPT = """You are an expert evaluator assessing whether AI-simulated human conversations are \
psychologically believable, emotionally coherent, and socially plausible.

Evaluate these metrics from 1 to 10:
1. persona_consistency   - Do characters behave per their defined traits?
2. emotional_realism     - Are emotional reactions believable and gradual?
3. conversational_coherence - Does the conversation flow logically?
4. goal_alignment        - Are decisions aligned with character goals?
5. conflict_realism      - Does conflict escalation feel natural?
6. social_plausibility   - Would real humans behave this way?
7. overall_realism       - Overall believability.

Return ONLY a raw JSON object. No markdown. No code fences. No explanation.

STRICT OUTPUT RULES:
- Use only plain ASCII characters in all string values.
- No line breaks inside any string value.
- No trailing commas.

Required format:
{
  "persona_consistency": 8.4,
  "emotional_realism": 7.9,
  "conversational_coherence": 8.2,
  "goal_alignment": 8.8,
  "conflict_realism": 7.5,
  "social_plausibility": 8.1,
  "overall_realism": 8.0
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
            response = llm.invoke(messages)
            raw = response.content.strip()
            
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
    
    try:
        scores = _invoke_json(
            system=EVALUATION_SYSTEM_PROMPT,
            user=user_prompt,
            label=f"Eval:{branch_name[:40]}"
        )
        scores["branch_name"] = branch_name
        return scores

    except Exception as e:
        print(f"[Evaluation Error] {branch_name}: {e}")
        return {
            "branch_name": branch_name,
            "evaluation_failed": True,
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

    valid_scores = [b for b in branch_scores if not b.get("evaluation_failed", False)]
    failed_scores = [b for b in branch_scores if b.get("evaluation_failed", False)]

    if failed_scores:
        print(f"  [Warning] {len(failed_scores)}/{len(branch_scores)} branches failed "
              f"evaluation and were excluded from averaging.")

    if not valid_scores:
        print(f"  [Warning] All branches failed evaluation — averaged scores will be zeros.")
        valid_scores = branch_scores   # fall back to zeros rather than crash on mean([])

    averaged_scores = {
        key: round(mean(b.get(key, 0) for b in valid_scores), 2)
        for key in SCORE_KEYS
    }

    return {
        "branch_results": branch_scores,        # all results including failures, for the log
        "valid_branch_count": len(valid_scores),
        "failed_branch_count": len(failed_scores),
        "averaged_scores": averaged_scores,      # only over valid results
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