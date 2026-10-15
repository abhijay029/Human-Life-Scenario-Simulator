from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.core import llm

_llm = llm.get_observer()

class TurnSentiment(BaseModel):
    turn: int = Field(description="Index number of the turn. Example: 1 for the first turn, 2 for second turn and so on.")
    speaker: str = Field(description="Name of the speaker that spoke in this turn.")
    sentiment: Literal["positive", "negative", "neutral"] = Field(description="Predicted sentiment of this turn's dialogue. This can be 'positive', 'negative' or 'neutral'.")
    score: float = Field(description="This is the confidence score of this turn's prediction.")
    note: str = Field(description="Reason for this prediction of sentiments in one line.")


class PersonaGoalSuccess(BaseModel):
    persona: str = Field(description="Name of the persona.")
    goal_summary: str = Field(description="Explanation of the goal of the persona in one line.")
    success_probability: float = Field(description="Estimated likelihood of the persona's goal being achieved or fulfilled.")
    reasoning: str = Field(description="Explanation for the estimated value of the persona's goal success probability in one line.")


class Observation(BaseModel):
    turn_sentiments: list[TurnSentiment] = Field(description="Sentiment analysis details per turn of this branch.")
    relationship_trajectory: Literal["improving", "stable", "deteriorating"] = Field(description="The current status and direction of the relationship between the speakers. This value can be 'improving', 'stable', or 'deteriorating'")
    trajectory_explanation: str = Field(description="Explanation for the predicted relationship trajectory in one line.")
    persona_goal_success: list[PersonaGoalSuccess]
    outcome_category: Literal["In favor", "disfavor"] = Field(
        description="The category of the branch. It can have the following values: "
        "'In favor': Means the outcome is in favor of the user. "
        "'disfavor': Means the outcome is not in favor of the user."
    )
    outcome_summary: str = Field(description="Summary of the outcome of this branch in maximum of 2 sentences.")
    key_turning_points: list[str] = Field(
        description="What in the conversation changed the status of the situation significantly. "
        "If nothing in particular then give empty list '[]'.",
        min_length=0, max_length=2,
    )
    recommendations: list[str] = Field(
        description="Advice to the user that will help them better handle the situation. "
        "Maximum 2 items allowed.",
        min_length=0, max_length=2,
    )

_parser = JsonOutputParser(pydantic_object=Observation)

OBSERVER_SYSTEM_PROMPT = """You are a psychology analyst AI. Analyse the dialogue and return ONLY valid JSON. No markdown, no explanation, just the raw JSON object.

{format_instructions}

Rules:
- Keep ALL strings under 12 words. Be extremely concise.
- turn_sentiments: max 2 per speaker, combine if needed
- Return the complete JSON in one response"""

OBSERVER_HUMAN_PROMPT = """Scenario: {scenario}
Decision: {decision_point}
Goals: {persona_goals}
Dialogue:
{dialogue_text}

Return JSON now."""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", OBSERVER_SYSTEM_PROMPT),
        ("human", OBSERVER_HUMAN_PROMPT),
    ]
).partial(format_instructions=_parser.get_format_instructions())

_chain = _prompt | _llm | _parser

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

    return _chain.invoke(
        {
            "scenario": scenario,
            "decision_point": decision_point,
            "persona_goals": persona_goals,
            "dialogue_text": dialogue_text,
        }
    )