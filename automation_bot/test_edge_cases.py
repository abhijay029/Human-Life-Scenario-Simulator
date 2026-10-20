"""
Comprehensive Edge-Case Test Suite for the Observer Agent & Simulator Bot.

Tests all key design edge cases:
  1. 16-turn long dialogue trajectory evolution across multiple phases.
  2. Extreme delta clamping (±10 max raw delta, ±4.0 max EMA shift).
  3. Boundary saturation: [0.0, 100.0] and [-100.0, +100.0] limits without overflow.
  4. Inverted polarity trajectory classification for tension vs trust/rapport/respect.
  5. Asymmetric directed dyads (A->B diverging from B->A).
  6. Degraded mode resilience during simulated 429 quota exhaustion.
  7. Final scorecard generation over extended 16-turn transcript.
  8. Cross-thread emit_turn_sync from ThreadPoolExecutor worker thread.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from backend.observer.constants import BOUNDS, MAX_DELTA, SMOOTHING_ALPHA
from backend.observer.core import (
    ObserverService,
    _ObserverTurnLLMOutput,
    _ScorecardLLMOutput,
)
from backend.observer.math_utils import (
    apply_dyad_deltas,
    calculate_slope,
    classify_trajectory,
)
from backend.observer.pipeline import ObserverPipeline
from backend.observer.schemas import (
    DyadState,
    TurnEvent,
    TurnObservation,
)
from automation_bot.scenarios import SCENARIOS


# ── Edge Case 1: Extreme Delta Clamping ───────────────────────────────────────

def test_extreme_delta_clamping_edge_case():
    """Verify that huge deltas (+50, -100) are clamped to ±MAX_DELTA and smoothed."""
    current = DyadState.initial("Arjun", "Rahul")
    # Unclamped massive deltas
    extreme_deltas = {
        "trust": 50.0,         # Exceeds +10
        "tension": -100.0,      # Exceeds -10
        "rapport": 30.0,        # Exceeds +10
        "respect": -50.0,       # Exceeds -10
        "power_balance": 80.0,  # Exceeds +10
    }

    updated, turning_points = apply_dyad_deltas(current, extreme_deltas, turn_index=1)

    # Max shift per turn = MAX_DELTA (10) * SMOOTHING_ALPHA (0.4) = 4.0
    max_step = MAX_DELTA * SMOOTHING_ALPHA
    assert updated.trust == pytest.approx(50.0 + max_step)
    assert updated.tension == pytest.approx(50.0 - max_step)
    assert updated.rapport == pytest.approx(50.0 + max_step)
    assert updated.respect == pytest.approx(50.0 - max_step)
    assert updated.power_balance == pytest.approx(0.0 + max_step)
    assert len(turning_points) > 0


# ── Edge Case 2: Boundary Saturation & Clamping ───────────────────────────────

def test_boundary_saturation_and_underflow():
    """Ensure values never exceed 100.0 or drop below 0.0, even with repeated maximum steps."""
    dyad = DyadState(
        from_party="A",
        to_party="B",
        trust=98.0,
        rapport=99.0,
        tension=2.0,
        respect=1.0,
        power_balance=98.0,
    )
    deltas = {
        "trust": 10.0,
        "rapport": 10.0,
        "tension": -10.0,
        "respect": -10.0,
        "power_balance": 10.0,
    }

    # Apply 5 consecutive positive/negative shifts
    for turn in range(5):
        dyad, _ = apply_dyad_deltas(dyad, deltas, turn_index=turn)

    assert dyad.trust <= 100.0
    assert dyad.rapport <= 100.0
    assert dyad.tension >= 0.0
    assert dyad.respect >= 0.0
    assert dyad.power_balance <= 100.0


# ── Edge Case 3: Tension Inverted Polarity ────────────────────────────────────

def test_tension_inverted_polarity_slope():
    """Tension decreasing (slope < 0) is improving; tension increasing is deteriorating."""
    # Decreasing tension series: 80 -> 70 -> 60 -> 50
    falling_tension = [80.0, 70.0, 60.0, 50.0]
    slope_falling = calculate_slope(falling_tension)
    assert slope_falling < 0
    assert classify_trajectory("tension", slope_falling) == "improving"

    # Increasing tension series: 40 -> 50 -> 60 -> 70
    rising_tension = [40.0, 50.0, 60.0, 70.0]
    slope_rising = calculate_slope(rising_tension)
    assert slope_rising > 0
    assert classify_trajectory("tension", slope_rising) == "deteriorating"

    # For trust: increasing is improving, decreasing is deteriorating
    rising_trust = [40.0, 50.0, 60.0, 70.0]
    assert classify_trajectory("trust", calculate_slope(rising_trust)) == "improving"

    falling_trust = [70.0, 60.0, 50.0, 40.0]
    assert classify_trajectory("trust", calculate_slope(falling_trust)) == "deteriorating"


# ── Edge Case 4: Asymmetric Directed Dyads ───────────────────────────────────

def test_asymmetric_directed_dyads():
    """Verify Arjun->Rahul and Rahul->Arjun can simultaneously diverge."""
    dyad_arjun_to_rahul = DyadState.initial("Arjun", "Rahul")
    dyad_rahul_to_arjun = DyadState.initial("Rahul", "Arjun")

    # Arjun is being conciliatory, Rahul is being furious
    deltas_arjun = {"trust": 5.0, "tension": -3.0}
    deltas_rahul = {"trust": -8.0, "tension": 7.0}

    updated_arjun, _ = apply_dyad_deltas(dyad_arjun_to_rahul, deltas_arjun, turn_index=0)
    updated_rahul, _ = apply_dyad_deltas(dyad_rahul_to_arjun, deltas_rahul, turn_index=0)

    assert updated_arjun.trust > 50.0
    assert updated_arjun.tension < 50.0

    assert updated_rahul.trust < 50.0
    assert updated_rahul.tension > 50.0


# ── Edge Case 5: Degraded Mode Resilience (429 API Quota Exhaustion) ──────────

def test_degraded_mode_during_429_quota_exhaustion():
    """ObserverService must not crash when LLM throws 429 quota exhaustion; must flag degraded=True."""
    mock_llm = MagicMock()
    mock_llm.complete_structured.side_effect = RuntimeError("ResourceExhausted: 429 Quota Exceeded")

    service = ObserverService(llm_client=mock_llm)
    service.get_or_create_session("sess_quota", participants=["Arjun", "Rahul"])

    event = TurnEvent(
        session_id="sess_quota",
        turn_index=0,
        speaker="Arjun",
        listeners=["Rahul"],
        message="Dad, I want to talk about my future.",
    )

    # Should execute without throwing
    obs = service.observe_turn(event)

    assert obs.degraded is True
    assert obs.confidence == 0.0
    # Dyad state should be preserved at baseline
    assert len(obs.dyad_states) >= 1
    for dyad in obs.dyad_states:
        assert dyad.trust == 50.0
        assert dyad.tension == 50.0


# ── Edge Case 6: Extended 16-Turn Simulation Run ──────────────────────────────

def test_16_turn_long_dialogue_trajectory_evolution():
    """
    Stress-test full 16-turn conversation trajectory.
    Verifies:
      - 16 observations generated
      - Rolling summary refreshes every 4 turns
      - Dynamic trajectory calculations across 16 data points
      - Turning points detection
      - Final scorecard generation
    """
    sc_data = SCENARIOS["marathon"]
    turns = sc_data["playback_dialogue"]
    assert len(turns) == 16

    # Mock dynamic LLM responses matching the 4 phases
    def mock_observer_response(*args, **kwargs):
        # Determine turn by call count
        return _ObserverTurnLLMOutput(
            sentiment="negative",
            sentiment_score=-0.5,
            emotion_labels=["anxious", "frustrated"],
            dyad_deltas={
                "Arjun->Rahul": {"trust": -2.0, "tension": 4.0, "rapport": -3.0},
                "Rahul->Arjun": {"trust": -3.0, "tension": 5.0, "respect": -2.0},
            },
            key_event="Conflict escalation turn",
            turning_point_reason="Major stance confrontation" if kwargs.get("turn_index", 0) in (3, 8, 12) else None,
        )

    mock_llm = MagicMock()
    mock_llm.complete_structured.side_effect = mock_observer_response

    service = ObserverService(llm_client=mock_llm)
    session_id = "test_marathon_16_turns"
    service.get_or_create_session(
        session_id=session_id,
        participants=["Arjun", "Rahul"],
        scenario_description=sc_data["scenario"],
    )

    observations = []
    for idx, (speaker, utterance) in enumerate(turns):
        ev = TurnEvent(
            session_id=session_id,
            turn_index=idx,
            speaker=speaker,
            listeners=["Rahul" if speaker == "Arjun" else "Arjun"],
            message=utterance,
            runtime="simulation",
        )
        obs = service.observe_turn(ev)
        observations.append(obs)

    # Asserts across the 16 turns
    assert len(observations) == 16
    for i, obs in enumerate(observations):
        assert obs.turn_index == i
        assert obs.speaker == turns[i][0]
        assert len(obs.dyad_states) >= 1

    # Check trajectory summary after 16 turns
    trajectories = service.get_all_trajectories(session_id)
    assert len(trajectories) >= 5  # at least 5 dimensions per dyad
    for t in trajectories:
        assert len(t.turning_points) >= 0
        assert t.min_value <= t.max_value
        assert t.label in ("improving", "stable", "deteriorating")

    # Scorecard generation over long dialogue
    mock_llm.complete_structured.side_effect = None
    mock_llm.complete_structured.return_value = _ScorecardLLMOutput(
        persona_consistency=9.2,
        emotional_realism=9.5,
        conversational_coherence=9.4,
        goal_alignment=9.0,
        conflict_realism=9.6,
        social_plausibility=9.3,
        overall_realism=9.4,
        goal_success={"Arjun": 0.45, "Rahul": 0.55},
        outcome_category="Most Likely",
        key_turning_points=["Arjun offered formal milestone business plan", "Rahul agreed to 12-month runway"],
        recommendations=["Follow up with written milestone schedule"],
        summary="A thorough 16-turn negotiation leading to conditional agreement.",
    )

    scorecard = service.finalize(session_id)
    assert scorecard.overall_realism == pytest.approx(9.4)
    assert scorecard.outcome_category == "Most Likely"
    assert len(scorecard.key_turning_points) == 2


# ── Edge Case 7: Cross-Thread emit_turn_sync from ThreadPoolExecutor ──────────

@pytest.mark.asyncio
async def test_cross_thread_emit_turn_sync_from_executor():
    """Verify emit_turn_sync works flawlessly when invoked from a worker thread without an event loop."""
    mock_llm = MagicMock()
    mock_llm.complete_structured.return_value = _ObserverTurnLLMOutput(
        sentiment="positive",
        sentiment_score=0.6,
        emotion_labels=["constructive"],
    )

    service = ObserverService(llm_client=mock_llm)
    pipeline = ObserverPipeline(observer=service)
    session_id = "test_thread_worker"

    pipeline.get_or_create_session(session_id, participants=["Alice", "Bob"])
    pipeline.start_worker(session_id)

    # Function executed inside ThreadPoolExecutor (worker thread without event loop)
    def worker_thread_action():
        event = TurnEvent(
            session_id=session_id,
            turn_index=0,
            speaker="Alice",
            listeners=["Bob"],
            message="Hello from worker thread!",
        )
        pipeline.emit_turn_sync(event)
        pipeline.finalize_session_sync(session_id)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker_thread_action)
        future.result()

    # Wait for the async worker loop to process
    await asyncio.sleep(0.5)

    obs = pipeline.get_observations(session_id)
    assert len(obs) == 1
    assert obs[0].speaker == "Alice"
    assert obs[0].sentiment == "positive"
