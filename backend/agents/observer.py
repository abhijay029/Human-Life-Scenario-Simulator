"""
Observer Agent
==============
Analyses a completed dialogue log and returns structured outcome metrics:
  - per-turn sentiment  (positive / neutral / negative + score −1→+1)
  - overall relationship trajectory
  - success probability for each persona's goals
  - outcome category: Best Case / Most Likely / Worst Case
  - a brief narrative summary of what happened and why
"""

import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

OBSERVER_SYSTEM_PROMPT = """You are an expert psychologist and conflict-analysis AI called the Observer Agent.
Your job is to read a simulated dialogue between personas and produce a structured JSON report.

You must return ONLY valid JSON — no markdown, no explanation outside the JSON.

The JSON schema is:
{
  "turn_sentiments": [
    {
      "turn": <int, 1-based>,
      "speaker": "<name>",
      "sentiment": "positive" | "neutral" | "negative",
      "score": <float, -1.0 to 1.0>,
      "note": "<one-sentence reason>"
    }
  ],
  "relationship_trajectory": "improving" | "stable" | "deteriorating",
  "trajectory_explanation": "<2 sentences>",
  "persona_goal_success": [
    {
      "persona": "<name>",
      "goal_summary": "<their goals condensed>",
      "success_probability": <float, 0.0 to 1.0>,
      "reasoning": "<2 sentences>"
    }
  ],
  "outcome_category": "Best Case" | "Most Likely" | "Worst Case",
  "outcome_summary": "<3–5 sentence narrative of what happened, why, and what the likely real-world result is>",
  "key_turning_points": ["<moment 1>", "<moment 2>"],
  "recommendations": ["<actionable advice 1>", "<actionable advice 2>", "<actionable advice 3>"]
}
"""


def analyse_dialogue(
    dialogue_log: list[dict],
    scenario: str,
    decision_point: str,
    personas: list[dict],
) -> dict:
    """
    Runs the Observer Agent over a completed dialogue log.

    Parameters
    ----------
    dialogue_log   : list of {"speaker": str, "message": str}
    scenario       : the scenario description string
    decision_point : the injected decision string
    personas       : list of serialised Persona dicts (for goal context)

    Returns
    -------
    dict matching the schema above
    """
    persona_goals = "\n".join(
        f"- {p['name']}: {', '.join(p.get('goals', []))}"
        for p in personas
    )

    dialogue_text = "\n".join(
        f"[Turn {i+1}] {entry['speaker']}: {entry['message']}"
        for i, entry in enumerate(dialogue_log)
    )

    user_content = f"""SCENARIO: {scenario}

DECISION POINT: {decision_point}

PERSONA GOALS:
{persona_goals}

DIALOGUE LOG:
{dialogue_text}

Please analyse the above and return your JSON report now."""

    messages = [
        SystemMessage(content=OBSERVER_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    response = _llm.invoke(messages)
    raw = response.content.strip()

    # Strip markdown fences if the model wrapped it anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
