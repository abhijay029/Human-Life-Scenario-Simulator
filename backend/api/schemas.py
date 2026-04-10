"""
API Schemas
===========
Pydantic models for FastAPI request bodies and response shapes.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Persona ──────────────────────────────────────────────────────────────────

class PersonaSchema(BaseModel):
    name: str
    age: int
    occupation: str
    personality_traits: list[str]
    values: list[str]
    communication_style: str
    emotional_triggers: list[str]
    background: str
    goals: list[str]


# ── Simulation ────────────────────────────────────────────────────────────────

class RunSimulationRequest(BaseModel):
    personas: list[PersonaSchema] = Field(..., min_length=2)
    scenario: str
    decision_point: str
    max_turns: int = Field(default=6, ge=2, le=20)
    store_memories: bool = Field(
        default=True,
        description="Pre-load persona facts into ChromaDB before running."
    )


class DialogueTurn(BaseModel):
    speaker: str
    message: str


class TurnSentiment(BaseModel):
    turn: int
    speaker: str
    sentiment: str
    score: float
    note: str


class PersonaGoalSuccess(BaseModel):
    persona: str
    goal_summary: str
    success_probability: float
    reasoning: str


class ObserverAnalysis(BaseModel):
    turn_sentiments: list[TurnSentiment]
    relationship_trajectory: str
    trajectory_explanation: str
    persona_goal_success: list[PersonaGoalSuccess]
    outcome_category: str
    outcome_summary: str
    key_turning_points: list[str]
    recommendations: list[str]


class SimulationResponse(BaseModel):
    scenario: str
    decision_point: str
    dialogue_log: list[DialogueTurn]
    analysis: Optional[ObserverAnalysis] = None


# ── Multiverse ────────────────────────────────────────────────────────────────

class RunMultiverseRequest(BaseModel):
    personas: list[PersonaSchema] = Field(..., min_length=2)
    scenario: str
    decision_branches: list[str] = Field(..., min_length=2, max_length=6)
    max_turns: int = Field(default=6, ge=2, le=20)
    store_memories: bool = True


class BranchSummary(BaseModel):
    decision_point: str
    outcome_category: Optional[str] = None
    avg_success_probability: float


class ComparisonReport(BaseModel):
    best_case: dict
    worst_case: dict
    most_likely: dict
    all_branches_ranked: list[BranchSummary]


class MultiverseResponse(BaseModel):
    scenario: str
    branches: list[SimulationResponse]
    comparison_report: ComparisonReport


# ── Character Builder ─────────────────────────────────────────────────────────

class BuildPersonaRequest(BaseModel):
    """
    Accepts a free-text description and returns a structured Persona.
    The /characters/build endpoint uses the LLM to extract structured fields.
    """
    description: str = Field(
        ...,
        description="Natural language description of the person, e.g. "
                    "'My boss, 50s, very formal, hates being challenged…'"
    )


class BuildPersonaResponse(BaseModel):
    persona: PersonaSchema
    system_prompt_preview: str
