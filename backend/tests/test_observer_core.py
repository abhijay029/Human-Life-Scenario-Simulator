"""
Unit tests for the Observer Agent core module and pure mathematical logic.
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.observer.constants import MAX_DELTA, SMOOTHING_ALPHA
from backend.observer.schemas import DyadState, TurnEvent, TurnObservation, ConversationScorecard
from backend.observer.math_utils import (
    apply_dyad_deltas,
    calculate_slope,
    classify_trajectory,
)
from backend.observer.core import (
    ObserverService,
    _ObserverTurnLLMOutput,
    _ScorecardLLMOutput,
)


def test_apply_dyad_deltas_clamping_and_smoothing():
    initial = DyadState.initial("Arjun", "Rahul")
    assert initial.trust == 50.0

    # Raw delta +15.0 exceeds MAX_DELTA (10.0) -> clamped to 10.0
    # EMA smoothing: 0.4 * 10.0 = +4.0
    deltas = {"trust": 15.0, "tension": -25.0}
    new_state, tps = apply_dyad_deltas(
        initial,
        deltas,
        clamp_limit=MAX_DELTA,
        alpha=SMOOTHING_ALPHA,
        reason="Heartfelt confession",
        turn_index=1,
    )

    assert new_state.trust == 54.0
    # tension raw -25.0 -> clamped to -10.0 -> 0.4 * -10.0 = -4.0 -> 50 - 4 = 46.0
    assert new_state.tension == 46.0

    # Both clamped deltas had magnitude 10.0 >= 5.0, so both generate turning points
    assert len(tps) == 2
    trust_tp = next(tp for tp in tps if tp.dimension == "trust")
    assert trust_tp.delta == 4.0
    assert trust_tp.value_after == 54.0
    assert trust_tp.reason == "Heartfelt confession"


def test_apply_dyad_deltas_bounds_clamping():
    state = DyadState(
        from_party="A",
        to_party="B",
        trust=98.0,
        rapport=2.0,
        tension=99.0,
        respect=50.0,
        power_balance=-98.0,
    )

    deltas = {
        "trust": 10.0,        # would be 98 + 4 = 102 -> clamp to 100
        "rapport": -10.0,     # would be 2 - 4 = -2 -> clamp to 0
        "tension": 10.0,      # would be 99 + 4 = 103 -> clamp to 100
        "power_balance": -10.0 # would be -98 - 4 = -102 -> clamp to -100
    }

    new_state, _ = apply_dyad_deltas(state, deltas, clamp_limit=10.0, alpha=0.4)
    assert new_state.trust == 100.0
    assert new_state.rapport == 0.0
    assert new_state.tension == 100.0
    assert new_state.power_balance == -100.0


def test_calculate_slope():
    # Empty or single value
    assert calculate_slope([]) == 0.0
    assert calculate_slope([50.0]) == 0.0

    # Flat line
    assert calculate_slope([50.0, 50.0, 50.0]) == 0.0

    # Linear increase
    assert calculate_slope([10.0, 20.0, 30.0]) == 10.0

    # Linear decrease
    assert calculate_slope([30.0, 20.0, 10.0]) == -10.0


def test_classify_trajectory():
    # Polarity for trust, rapport, respect: positive slope = improving
    assert classify_trajectory("trust", 1.2) == "improving"
    assert classify_trajectory("trust", -1.2) == "deteriorating"
    assert classify_trajectory("trust", 0.2) == "stable"

    # Polarity for tension: inverted (positive slope = deteriorating)
    assert classify_trajectory("tension", 1.2) == "deteriorating"
    assert classify_trajectory("tension", -1.2) == "improving"
    assert classify_trajectory("tension", 0.5) == "stable"


def test_observer_service_observe_turn_mocked():
    mock_llm = MagicMock()
    mock_llm.complete_structured.return_value = _ObserverTurnLLMOutput(
        sentiment="positive",
        sentiment_score=0.8,
        emotion_labels=["sincere", "optimistic"],
        dyad_deltas={
            "Arjun->Rahul": {
                "trust": 8.0,
                "rapport": 6.0,
                "tension": -5.0,
                "respect": 4.0,
                "power_balance": 2.0,
            }
        },
        key_event="Arjun explains his career dream transparently",
        turning_point_reason="Clear statement of passion",
    )

    service = ObserverService(llm_client=mock_llm)
    event = TurnEvent(
        session_id="session_123",
        turn_index=0,
        speaker="Arjun",
        listeners=["Rahul"],
        message="Dad, I want to pursue music. I have a genuine offer.",
    )

    obs = service.observe_turn(event)

    assert obs.session_id == "session_123"
    assert obs.turn_index == 0
    assert obs.sentiment == "positive"
    assert obs.sentiment_score == 0.8
    assert "sincere" in obs.emotion_labels
    assert obs.degraded is False
    assert obs.confidence == 1.0

    # Verify updated dyad state
    session = service.get_or_create_session("session_123")
    assert "Arjun->Rahul" in session.dyads
    dyad = session.dyads["Arjun->Rahul"]
    # 50 + (0.4 * 8.0) = 53.2
    assert dyad.trust == 53.2
    # 50 + (0.4 * -5.0) = 48.0
    assert dyad.tension == 48.0


def test_observer_service_degraded_fallback():
    mock_llm = MagicMock()
    # LLM raises an error (e.g. 429 quota exhaustion)
    mock_llm.complete_structured.side_effect = RuntimeError("ResourceExhausted 429")

    service = ObserverService(llm_client=mock_llm)
    event = TurnEvent(
        session_id="session_degraded",
        turn_index=1,
        speaker="SpeakerA",
        listeners=["SpeakerB"],
        message="Hello there.",
    )

    obs = service.observe_turn(event)

    assert obs.degraded is True
    assert obs.confidence == 0.0
    assert obs.sentiment == "neutral"
    # State preserved without crash
    session = service.get_or_create_session("session_degraded")
    assert "SpeakerA->SpeakerB" in session.dyads
    assert session.dyads["SpeakerA->SpeakerB"].trust == 50.0


def test_observer_service_finalize():
    mock_llm = MagicMock()
    mock_llm.complete_structured.return_value = _ScorecardLLMOutput(
        persona_consistency=8.5,
        emotional_realism=9.0,
        conversational_coherence=8.8,
        goal_alignment=8.0,
        conflict_realism=9.2,
        social_plausibility=8.7,
        overall_realism=8.9,
        goal_success={"Arjun": 0.75, "Rahul": 0.6},
        outcome_category="Best Case",
        key_turning_points=["Honest revelation of contract", "Father's gradual acceptance"],
        recommendations=["Continue exploring shared creative compromise"],
        summary="Constructive intergenerational resolution.",
    )

    service = ObserverService(llm_client=mock_llm)
    session = service.get_or_create_session("session_final", participants=["Arjun", "Rahul"])

    scorecard = service.finalize("session_final")

    assert isinstance(scorecard, ConversationScorecard)
    assert scorecard.overall_realism == 8.9
    assert scorecard.outcome_category == "Best Case"
    assert scorecard.goal_success["Arjun"] == 0.75
    assert len(scorecard.key_turning_points) == 2
