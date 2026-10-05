import os
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from backend.core import llm
from pydantic import BaseModel, Field
from typing import Literal
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

_llm = llm.get_observer()

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
- Keep ALL strings under 12 words. Be extremely concise.
- turn_sentiments: max 2 per speaker, combine if needed
- key_turning_points: max 2 items, or 
- recommendations: max 2 items
- Return the complete JSON in one response"""

class TurnSentiment(BaseModel):
    turn: int = Field(description = "Index number of the turn. Example: 1 for the first turn, 2 for second turn and so on.")
    speaker: str = Field(descripeiton = "Name of the speaker that spoke in this turn.")
    sentiment: Literal["positive", "negative", "neutral"] = Field(description = "Predicted sentiment of this turn's dialogue. This can be 'positive', 'negative' or 'neutral'.")
    score: float = Field(description = "This is the confidence score of this turn's prediction.")
    note: str = Field(description = "Reason for this prediction of sentiments in one line.")

class PersonaGoalSuccess(BaseModel):
    persona: str = Field(description = "Name of the persona.")
    goal_summary: str = Field(description = "Explaination of the goal of the persna in one line.")
    success_probability: float = Field(description = "Estimated likelihood of the persona's goal being achieved or fulfilled.")
    reasoning: str = Field(description = "Explanation for the estimated value of the persona's goal success probability in one line.")

class Observation(BaseModel):
    turn_sentiments:list[TurnSentiment] = Field(description = "Sentiment analysis details per turn of this branch.")
    relationship_trajectory: Literal["improving", "stable", "deteriorating"] = Field(description = "The current status and direction of the relationship between the speakers. This value can be 'improving', 'stable', or 'deteriorating'")
    trajectory_explanation: str = Field(description = "Explanation fo the predicted relationship trajectory in one line.")
    persona_goal_success: list[PersonaGoalSuccess]
    outcome_category: Literal["In favor", "disfavor"] = Field(description = "The category of the branch. It can have the following values: " \
    "'In favor': Means the outcome is in favor of the user." \
    "'disfavor': Means the outcome is not in favor of the user.")
    outcome_summary: str = Field(description = "Summary of the outcome of this branch in maximum of 2 sentences.")
    key_turning_points: list[str] = Field(description = "What in the conversation changed the status of the situation significantly." \
    "If nothing in perticular then give empty list '[]'.", min_length = 0, max_length = 2)
    recommendations: list[str] = Field(description = "Advice to the user that will help them better handle the situation. " \
    "Maximum 2 items allowed.", min_length = 0, max_length = 2)

def _observer_invoke(messages):
        try:
            return _llm.invoke(messages)
        except Exception as e:
            error_str = str(e).lower()
            print(f"[Observer: {_llm.model}] Exception: \n{error_str}\n")


def analyse_dialogue(dialogue_log, scenario, decision_point, personas) -> dict:
    if not dialogue_log:
        return {}

    persona_goals = "; ".join(
        f"{p['name']}: {', '.join(p.get('goals', []))}" for p in personas
    )
    dialogue_text = "\n".join(
        f"[{i+1}] {e['speaker']}: {e['message']}"
        for i, e in enumerate(dialogue_log)
    )

    user_content = (
        f"Scenario: {scenario}\n"
        f"Decision: {decision_point}\n"
        f"Goals: {persona_goals}\n"
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

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        print(f"[Observer] Could not find JSON. Raw: {raw[:200]}")
        return _fallback_analysis(dialogue_log, personas)

    raw = raw[start:end]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[Observer] JSON parse error: {e}. Attempting repair...")
        return _repair_and_parse(raw, dialogue_log, personas)


def _repair_and_parse(raw: str, dialogue_log: list, personas: list) -> dict:
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("[Observer] Repair failed — returning fallback analysis.")
        return _fallback_analysis(dialogue_log, personas)


def _fallback_analysis(dialogue_log: list, personas: list) -> dict:
    """Return a minimal valid analysis when JSON parsing completely fails."""
    return {
        "turn_sentiments": [
            {
                "turn": i + 1,
                "speaker": e["speaker"],
                "sentiment": "neutral",
                "score": 0.0,
                "note": "Observer parsing failed — neutral assigned."
            }
            for i, e in enumerate(dialogue_log)
        ],
        "relationship_trajectory": "stable",
        "trajectory_explanation": "Observer analysis could not be parsed for this branch.",
        "persona_goal_success": [
            {
                "persona": p["name"],
                "goal_summary": ", ".join(p.get("goals", [])),
                "success_probability": 0.5,
                "reasoning": "Default value — observer parsing failed."
            }
            for p in personas
        ],
        "outcome_category": "Most Likely",
        "outcome_summary": "Simulation completed but observer analysis could not be parsed.",
        "key_turning_points": [],
        "recommendations": []
    }
