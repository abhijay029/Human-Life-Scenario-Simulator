import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

def _observer_invoke(messages):
    import time
    time.sleep(20)  # always pause before Observer call
    return _llm.invoke(messages)

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    google_api_key=os.getenv("GEMINI_API_KEY"),
    max_output_tokens=1200,
)

OBSERVER_SYSTEM_PROMPT = """You are a psychology analyst AI. Analyse the dialogue and return ONLY valid JSON. No markdown, no explanation, just the raw JSON object.

Return this exact structure:
{
  "turn_sentiments": [{"turn": 1, "speaker": "name", "sentiment": "positive", "score": 0.5, "note": "reason"}],
  "relationship_trajectory": "improving",
  "trajectory_explanation": "one sentence",
  "persona_goal_success": [{"persona": "name", "goal_summary": "brief", "success_probability": 0.6, "reasoning": "one sentence"}],
  "outcome_category": "Most Likely",
  "outcome_summary": "two sentences max",
  "key_turning_points": ["point 1"],
  "recommendations": ["advice 1", "advice 2"]
}

Rules:
- sentiment must be exactly: positive, neutral, or negative
- relationship_trajectory must be exactly: improving, stable, or deteriorating  
- outcome_category must be exactly: Best Case, Most Likely, or Worst Case
- Keep all strings SHORT — max 20 words each
- Return the complete JSON in one response"""

import time

def analyse_dialogue(dialogue_log, scenario, decision_point, personas) -> dict:
    if not dialogue_log:
        return {}

    # Extra pause before Observer call — it always follows simulation turns closely
    print("[Observer] Pausing 20s before analysis to respect rate limits...")
    time.sleep(20)

    persona_goals = "; ".join(
        f"{p['name']}: {', '.join(p.get('goals', []))}" for p in personas
    )
    dialogue_text = "\n".join(
        f"[{i+1}] {e['speaker']}: {e['message'][:200]}"
        for i, e in enumerate(dialogue_log)
    )

    user_content = (
        f"Scenario: {scenario[:200]}\n"
        f"Decision: {decision_point[:150]}\n"
        f"Goals: {persona_goals[:300]}\n"
        f"Dialogue:\n{dialogue_text}\n\nReturn JSON now."
    )

    messages = [
        SystemMessage(content=OBSERVER_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    response = _observer_invoke(messages)

    content = response.content
    if isinstance(content, list):
        raw = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    else:
        raw = content.strip()

    print(f"[Observer RAW RESPONSE]\n{raw}\n[END RAW]")

    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # Extract JSON object robustly
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        print(f"[Observer] Could not find JSON in response. Raw: {raw[:200]}")
        return _fallback_analysis(dialogue_log, personas)

    raw = raw[start:end]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[Observer] JSON parse error: {e}. Attempting repair...")
        return _repair_and_parse(raw, dialogue_log, personas)


def _repair_and_parse(raw: str, dialogue_log: list, personas: list) -> dict:
    """Try to salvage a broken JSON response."""
    import re

    # Fix common issues: trailing commas before } or ]
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)

    # Fix unquoted property names
    raw = re.sub(r'(?<!["\w])(\w+)(?=\s*:)', r'"\1"', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("[Observer] Repair failed — returning fallback analysis.")
        return _fallback_analysis(dialogue_log, personas)


def _fallback_analysis(dialogue_log: list, personas: list) -> dict:
    """Return a minimal valid analysis when parsing completely fails."""
    return {
        "turn_sentiments": [
            {
                "turn": i + 1,
                "speaker": e["speaker"],
                "sentiment": "neutral",
                "score": 0.0,
                "note": "Auto-fallback — observer parsing failed."
            }
            for i, e in enumerate(dialogue_log)
        ],
        "relationship_trajectory": "stable",
        "trajectory_explanation": "Observer analysis unavailable for this branch.",
        "persona_goal_success": [
            {
                "persona": p["name"],
                "goal_summary": ", ".join(p.get("goals", [])),
                "success_probability": 0.5,
                "reasoning": "Default fallback value."
            }
            for p in personas
        ],
        "outcome_category": "Most Likely",
        "outcome_summary": "Simulation completed but observer analysis could not be parsed.",
        "key_turning_points": [],
        "recommendations": []
    }