"""
Data models and schemas for the Observer Agent.
"""
from __future__ import annotations

import time
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

from .constants import BOUNDS, NEUTRAL_VALUES, DIMENSIONS


class TurnEvent(BaseModel):
    """Payload emitted when any participant speaks a turn."""
    session_id: str
    turn_index: int
    speaker: str
    listeners: list[str] = Field(default_factory=list)
    message: str
    timestamp: float = Field(default_factory=time.time)
    runtime: Literal["simulation", "kl_chat"] = "simulation"


class DyadState(BaseModel):
    """Directed state of relationship from one party's perspective toward another."""
    from_party: str
    to_party: str
    trust: float = Field(default=50.0, ge=0.0, le=100.0)
    rapport: float = Field(default=50.0, ge=0.0, le=100.0)
    tension: float = Field(default=50.0, ge=0.0, le=100.0)
    respect: float = Field(default=50.0, ge=0.0, le=100.0)
    power_balance: float = Field(default=0.0, ge=-100.0, le=100.0)

    @classmethod
    def initial(cls, from_party: str, to_party: str) -> DyadState:
        return cls(
            from_party=from_party,
            to_party=to_party,
            trust=NEUTRAL_VALUES["trust"],
            rapport=NEUTRAL_VALUES["rapport"],
            tension=NEUTRAL_VALUES["tension"],
            respect=NEUTRAL_VALUES["respect"],
            power_balance=NEUTRAL_VALUES["power_balance"],
        )

    def pair_key(self) -> str:
        return f"{self.from_party}->{self.to_party}"


class TurningPoint(BaseModel):
    turn_index: int
    dimension: str
    delta: float
    value_after: float
    reason: str


class TurnObservation(BaseModel):
    """Quantitative scoring and state update produced for one conversation turn."""
    session_id: str
    turn_index: int
    speaker: str
    sentiment: Literal["positive", "neutral", "negative"]
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    emotion_labels: list[str] = Field(default_factory=list)
    # Directed pair key "A->B" -> {dimension: delta}
    dyad_deltas: dict[str, dict[str, float]] = Field(default_factory=dict)
    # States after applying deltas & smoothing
    dyad_states: list[DyadState] = Field(default_factory=list)
    key_event: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    degraded: bool = False
    timestamp: float = Field(default_factory=time.time)


class ConversationScorecard(BaseModel):
    """Final post-conversation evaluation scorecard."""
    session_id: str
    # 7 realism metrics (scale 1.0 - 10.0)
    persona_consistency: float = Field(default=7.0, ge=0.0, le=10.0)
    emotional_realism: float = Field(default=7.0, ge=0.0, le=10.0)
    conversational_coherence: float = Field(default=7.0, ge=0.0, le=10.0)
    goal_alignment: float = Field(default=7.0, ge=0.0, le=10.0)
    conflict_realism: float = Field(default=7.0, ge=0.0, le=10.0)
    social_plausibility: float = Field(default=7.0, ge=0.0, le=10.0)
    overall_realism: float = Field(default=7.0, ge=0.0, le=10.0)

    # Goal success probabilities per persona (scale 0.0 - 1.0)
    goal_success: dict[str, float] = Field(default_factory=dict)
    outcome_category: Literal["Best Case", "Most Likely", "Worst Case"] = "Most Likely"
    key_turning_points: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""
