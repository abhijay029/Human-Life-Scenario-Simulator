"""
Observer Agent core service.
Executes real-time turn-by-turn observation, directed dyad updates, trajectory calculations,
and comprehensive conversation scorecards.
"""
from __future__ import annotations

import logging
import pathlib
import time
from typing import Optional, Literal
from pydantic import BaseModel, Field

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..knowledge_limiter.llm_client import LLMClient
from ..knowledge_limiter.config import settings
from .constants import (
    DIMENSIONS,
    MAX_DELTA,
    SMOOTHING_ALPHA,
    OBSERVER_HISTORY_WINDOW,
    SUMMARY_REFRESH_INTERVAL,
    REALISM_METRIC_KEYS,
)
from .schemas import (
    TurnEvent,
    DyadState,
    TurningPoint,
    TurnObservation,
    TrajectorySummary,
    ConversationScorecard,
)
from .math_utils import apply_dyad_deltas, calculate_slope, classify_trajectory

logger = logging.getLogger(__name__)

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class _ObserverTurnLLMOutput(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    emotion_labels: list[str] = Field(default_factory=list)
    dyad_deltas: dict[str, dict[str, float]] = Field(default_factory=dict)
    key_event: Optional[str] = None
    turning_point_reason: Optional[str] = None


class _ScorecardLLMOutput(BaseModel):
    persona_consistency: float = 7.0
    emotional_realism: float = 7.0
    conversational_coherence: float = 7.0
    goal_alignment: float = 7.0
    conflict_realism: float = 7.0
    social_plausibility: float = 7.0
    overall_realism: float = 7.0
    goal_success: dict[str, float] = Field(default_factory=dict)
    outcome_category: Literal["Best Case", "Most Likely", "Worst Case"] = "Most Likely"
    key_turning_points: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""


class SessionState:
    """In-memory state tracker for an ongoing observed session."""

    def __init__(self, session_id: str, scenario_description: str = "") -> None:
        self.session_id: str = session_id
        self.scenario_description: str = scenario_description
        self.participants: set[str] = set()
        self.dyads: dict[str, DyadState] = {}
        self.turns: list[TurnEvent] = []
        self.observations: list[TurnObservation] = []
        self.history_values: dict[str, dict[str, list[float]]] = {}
        self.turning_points: list[TurningPoint] = []
        self.rolling_summary: str = ""


def _normalize_dyad_deltas(
    raw_deltas: dict[str, Any],
    session: SessionState,
    speaker: str,
    listeners: list[str],
) -> dict[str, dict[str, float]]:
    """
    Robustly maps raw LLM delta outputs onto the session's active dyad keys.
    Handles flat dimension maps, alternate casing/underscores, and single-party keys.
    """
    normalized: dict[str, dict[str, float]] = {}
    if not raw_deltas:
        return normalized

    effective_listeners = listeners or [p for p in session.participants if p != speaker]
    primary_listener = effective_listeners[0] if effective_listeners else ""
    primary_key = (
        f"{speaker}->{primary_listener}"
        if primary_listener
        else (list(session.dyads.keys())[0] if session.dyads else "")
    )

    # Check if raw_deltas is a flat dictionary of dimensions: e.g. {"tension": 1.0, "trust": -1.0}
    is_flat_dims = any(k in DIMENSIONS for k in raw_deltas.keys())
    if is_flat_dims:
        clean_deltas: dict[str, float] = {}
        for dim, val in raw_deltas.items():
            if dim in DIMENSIONS:
                if isinstance(val, (int, float)):
                    clean_deltas[dim] = float(val)
                elif isinstance(val, dict):
                    clean_deltas[dim] = float(val.get("delta", val.get("value", 0.0)))
        if clean_deltas and primary_key:
            normalized[primary_key] = clean_deltas
        return normalized

    # Otherwise, iterate through entries
    for raw_key, raw_val in raw_deltas.items():
        if not isinstance(raw_val, dict):
            continue
        clean_deltas = {}
        for dim, val in raw_val.items():
            if dim in DIMENSIONS:
                if isinstance(val, (int, float)):
                    clean_deltas[dim] = float(val)
                elif isinstance(val, dict):
                    clean_deltas[dim] = float(val.get("delta", val.get("value", 0.0)))

        if not clean_deltas:
            continue

        target_pair: Optional[str] = None
        if raw_key in session.dyads:
            target_pair = raw_key
        elif "->" in raw_key:
            parts = raw_key.split("->", 1)
            p1_norm = parts[0].replace("_", " ").strip().lower()
            p2_norm = parts[1].replace("_", " ").strip().lower()
            for existing_key in session.dyads:
                e_parts = existing_key.split("->", 1)
                if len(e_parts) == 2:
                    e1, e2 = e_parts[0].strip().lower(), e_parts[1].strip().lower()
                    if (p1_norm in e1 or e1 in p1_norm) and (p2_norm in e2 or e2 in p2_norm):
                        target_pair = existing_key
                        break
        else:
            p_norm = raw_key.replace("_", " ").strip().lower()
            for existing_key in session.dyads:
                e_parts = existing_key.split("->", 1)
                if len(e_parts) == 2:
                    e1 = e_parts[0].strip().lower()
                    if p_norm in e1 or e1 in p_norm:
                        target_pair = existing_key
                        break

        if not target_pair and primary_key:
            target_pair = primary_key

        if target_pair:
            if target_pair not in normalized:
                normalized[target_pair] = {}
            normalized[target_pair].update(clean_deltas)

    return normalized


class ObserverService:
    """
    Real-time socio-emotional dialogue observer.
    Analyzes turn events, computes relational dyad deltas, and derives trajectories.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self._llm = llm_client or LLMClient()
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),
        )
        self._sessions: dict[str, SessionState] = {}

    def get_or_create_session(
        self,
        session_id: str,
        participants: Optional[list[str]] = None,
        scenario_description: str = "",
    ) -> SessionState:
        if session_id not in self._sessions:
            session = SessionState(session_id=session_id, scenario_description=scenario_description)
            if participants:
                for p in participants:
                    session.participants.add(p)
                self._initialize_dyads(session)
            self._sessions[session_id] = session
        else:
            session = self._sessions[session_id]
            if scenario_description and not session.scenario_description:
                session.scenario_description = scenario_description
            if participants:
                for p in participants:
                    session.participants.add(p)
                self._initialize_dyads(session)
        return self._sessions[session_id]

    def _initialize_dyads(self, session: SessionState) -> None:
        plist = sorted(list(session.participants))
        for i, p1 in enumerate(plist):
            for j, p2 in enumerate(plist):
                if p1 != p2:
                    key = f"{p1}->{p2}"
                    if key not in session.dyads:
                        state = DyadState.initial(p1, p2)
                        session.dyads[key] = state
                        session.history_values[key] = {
                            dim: [getattr(state, dim)] for dim in DIMENSIONS
                        }

    def _ensure_dyads_for_parties(self, session: SessionState, speaker: str, listeners: list[str]) -> None:
        session.participants.add(speaker)
        for l in listeners:
            session.participants.add(l)

        effective_listeners = listeners
        if not effective_listeners:
            effective_listeners = [p for p in session.participants if p != speaker]

        for listener in effective_listeners:
            for p1, p2 in [(speaker, listener), (listener, speaker)]:
                key = f"{p1}->{p2}"
                if key not in session.dyads:
                    state = DyadState.initial(p1, p2)
                    session.dyads[key] = state
                    session.history_values[key] = {
                        dim: [getattr(state, dim)] for dim in DIMENSIONS
                    }

    def observe_turn(self, event: TurnEvent) -> TurnObservation:
        """
        Observes a single conversation turn and computes updated dyad states.
        Guaranteed to return a valid TurnObservation (applies degraded mode fallback on error).
        """
        session = self.get_or_create_session(event.session_id)
        session.turns.append(event)

        listeners = event.listeners or [p for p in session.participants if p != event.speaker]
        self._ensure_dyads_for_parties(session, event.speaker, listeners)

        # Build prompt context
        recent_turns = session.turns[-OBSERVER_HISTORY_WINDOW:]
        current_dyads = list(session.dyads.values())

        template = self._jinja_env.get_template("observer_turn.jinja2")
        prompt = template.render(
            participants=sorted(list(session.participants)),
            rolling_summary=session.rolling_summary,
            recent_turns=recent_turns,
            current_turn=event,
            current_dyads=current_dyads,
        )

        messages = [
            {"role": "system", "content": "You are an expert socio-emotional behavioral observer analyzing real-time dialogues."},
            {"role": "user", "content": prompt},
        ]

        # LLM call with 1 retry, temperature 0.0
        parsed_llm: Optional[_ObserverTurnLLMOutput] = None
        for attempt in range(2):
            try:
                parsed_llm = self._llm.complete_structured(
                    messages=messages,
                    output_schema=_ObserverTurnLLMOutput,
                    model=settings.FAST_MODEL,
                    temperature=0.0,
                )
                break
            except Exception as exc:
                logger.warning(
                    "Observer LLM call failed for session %s turn %s (attempt %d/2): %s",
                    event.session_id,
                    event.turn_index,
                    attempt + 1,
                    exc,
                )

        # Degraded fallback if LLM failed
        if parsed_llm is None:
            logger.error(
                "Observer degraded mode activated for session %s turn %s",
                event.session_id,
                event.turn_index,
            )
            observation = TurnObservation(
                session_id=event.session_id,
                turn_index=event.turn_index,
                speaker=event.speaker,
                sentiment="neutral",
                sentiment_score=0.0,
                emotion_labels=[],
                dyad_deltas={},
                dyad_states=list(session.dyads.values()),
                key_event="Observer evaluation degraded (fallback applied)",
                confidence=0.0,
                degraded=True,
            )
            session.observations.append(observation)
            return observation

        # Normalize and map deltas to active dyads
        normalized_deltas = _normalize_dyad_deltas(
            parsed_llm.dyad_deltas,
            session=session,
            speaker=event.speaker,
            listeners=listeners,
        )

        turn_turning_points: list[TurningPoint] = []
        reason = parsed_llm.turning_point_reason or parsed_llm.key_event or ""

        for pair_key, deltas in normalized_deltas.items():
            if pair_key not in session.dyads:
                parts = pair_key.split("->")
                if len(parts) == 2:
                    p1, p2 = parts[0].strip(), parts[1].strip()
                    session.dyads[pair_key] = DyadState.initial(p1, p2)
                    session.history_values[pair_key] = {
                        dim: [getattr(session.dyads[pair_key], dim)] for dim in DIMENSIONS
                    }

            if pair_key in session.dyads:
                current_state = session.dyads[pair_key]
                new_state, tps = apply_dyad_deltas(
                    current=current_state,
                    deltas=deltas,
                    clamp_limit=MAX_DELTA,
                    alpha=SMOOTHING_ALPHA,
                    reason=reason,
                    turn_index=event.turn_index,
                )
                session.dyads[pair_key] = new_state
                turn_turning_points.extend(tps)
                session.turning_points.extend(tps)

        # Synchronize timeline history for ALL session dyads
        for pair_key, state in session.dyads.items():
            if pair_key not in session.history_values:
                session.history_values[pair_key] = {
                    dim: [getattr(state, dim)] for dim in DIMENSIONS
                }
            else:
                for dim in DIMENSIONS:
                    while len(session.history_values[pair_key][dim]) < len(session.turns):
                        session.history_values[pair_key][dim].append(getattr(state, dim))

        # Build turn observation
        observation = TurnObservation(
            session_id=event.session_id,
            turn_index=event.turn_index,
            speaker=event.speaker,
            sentiment=parsed_llm.sentiment,
            sentiment_score=parsed_llm.sentiment_score,
            emotion_labels=parsed_llm.emotion_labels,
            dyad_deltas=normalized_deltas if normalized_deltas else parsed_llm.dyad_deltas,
            dyad_states=list(session.dyads.values()),
            key_event=parsed_llm.key_event,
            confidence=1.0,
            degraded=False,
        )
        session.observations.append(observation)

        # Refresh rolling summary periodically
        if len(session.turns) % SUMMARY_REFRESH_INTERVAL == 0:
            self._update_rolling_summary(session)

        return observation

    def _update_rolling_summary(self, session: SessionState) -> None:
        """Periodically synthesizes a concise 2-sentence summary of the dialogue."""
        try:
            recent_turns_text = "\n".join(
                f"{t.speaker}: {t.message}" for t in session.turns[-8:]
            )
            prompt = (
                f"Summarize the relationship dynamic and current topic of this ongoing conversation in 2 concise sentences:\n\n"
                f"{recent_turns_text}\n\nSummary:"
            )
            summary = self._llm.complete(
                [{"role": "user", "content": prompt}],
                model=settings.FAST_MODEL,
                temperature=0.0,
            )
            session.rolling_summary = summary.strip()
        except Exception as exc:
            logger.warning("Rolling summary update failed for session %s: %s", session.session_id, exc)

    def get_trajectory_summary(
        self, session_id: str, pair_key: str, dimension: str
    ) -> Optional[TrajectorySummary]:
        session = self._sessions.get(session_id)
        if not session or pair_key not in session.history_values:
            return None

        dim_values = session.history_values[pair_key].get(dimension, [])
        if not dim_values:
            state = session.dyads.get(pair_key)
            if not state:
                return None
            val = getattr(state, dimension)
            dim_values = [val]

        start_val = dim_values[0]
        curr_val = dim_values[-1]
        min_val = min(dim_values)
        max_val = max(dim_values)
        slope = calculate_slope(dim_values)
        label = classify_trajectory(dimension, slope)

        tps = [
            tp
            for tp in session.turning_points
            if tp.dimension == dimension
        ]

        return TrajectorySummary(
            dyad_pair=pair_key,
            dimension=dimension,
            start=start_val,
            current=curr_val,
            min_value=min_val,
            max_value=max_val,
            slope=slope,
            label=label,
            turning_points=tps,
            history=list(dim_values),
        )

    def get_all_trajectories(self, session_id: str) -> list[TrajectorySummary]:
        session = self._sessions.get(session_id)
        if not session:
            return []

        summaries: list[TrajectorySummary] = []
        for pair_key in session.dyads.keys():
            for dim in DIMENSIONS:
                s = self.get_trajectory_summary(session_id, pair_key, dim)
                if s:
                    summaries.append(s)
        return summaries

    def finalize(self, session_id: str) -> ConversationScorecard:
        """
        Runs comprehensive post-conversation evaluation and generates scorecard.
        """
        session = self._sessions.get(session_id)
        if not session:
            return ConversationScorecard(
                session_id=session_id,
                summary="Session not found",
            )

        trajectories = self.get_all_trajectories(session_id)

        template = self._jinja_env.get_template("observer_scorecard.jinja2")
        prompt = template.render(
            scenario_description=session.scenario_description,
            participants=sorted(list(session.participants)),
            dialogue=session.turns,
            trajectory_summaries=trajectories,
        )

        messages = [
            {"role": "system", "content": "You are an expert conversation evaluator performing post-simulation realism analysis."},
            {"role": "user", "content": prompt},
        ]

        # LLM completion with fallback
        parsed: Optional[_ScorecardLLMOutput] = None
        for attempt in range(2):
            try:
                parsed = self._llm.complete_structured(
                    messages=messages,
                    output_schema=_ScorecardLLMOutput,
                    model=settings.FAST_MODEL,
                    temperature=0.0,
                )
                break
            except Exception as exc:
                logger.warning(
                    "Scorecard evaluation failed for session %s (attempt %d/2): %s",
                    session_id,
                    attempt + 1,
                    exc,
                )

        if parsed is None:
            # Fallback degraded scorecard
            return ConversationScorecard(
                session_id=session_id,
                persona_consistency=7.0,
                emotional_realism=7.0,
                conversational_coherence=7.0,
                goal_alignment=7.0,
                conflict_realism=7.0,
                social_plausibility=7.0,
                overall_realism=7.0,
                goal_success={p: 0.5 for p in session.participants},
                outcome_category="Most Likely",
                key_turning_points=[f"Turn {tp.turn_index}: {tp.dimension} ({tp.reason})" for tp in session.turning_points[:3]],
                recommendations=["Observer analysis completed with fallback scores due to LLM timeout."],
                summary="Simulation concluded. Degraded evaluation generated.",
            )

        return ConversationScorecard(
            session_id=session_id,
            persona_consistency=parsed.persona_consistency,
            emotional_realism=parsed.emotional_realism,
            conversational_coherence=parsed.conversational_coherence,
            goal_alignment=parsed.goal_alignment,
            conflict_realism=parsed.conflict_realism,
            social_plausibility=parsed.social_plausibility,
            overall_realism=parsed.overall_realism,
            goal_success=parsed.goal_success,
            outcome_category=parsed.outcome_category,
            key_turning_points=parsed.key_turning_points,
            recommendations=parsed.recommendations,
            summary=parsed.summary,
        )
