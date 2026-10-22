"""
Unit tests for the Observer Pipeline (async queue worker + SSE) and Storage (SQLite).
All LLM calls are mocked.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.observer.schemas import (
    TurnEvent,
    TurnObservation,
    DyadState,
    ConversationScorecard,
)
from backend.observer.pipeline import ObserverPipeline, _sse_event
from backend.observer.storage import ObserverStorage, init_db
from backend.observer.core import ObserverService, _ObserverTurnLLMOutput, _ScorecardLLMOutput
from pydantic import Field


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_service() -> ObserverService:
    mock_llm = MagicMock()
    mock_llm.complete_structured.return_value = _ObserverTurnLLMOutput(
        sentiment="positive",
        sentiment_score=0.5,
        emotion_labels=["hopeful"],
        dyad_deltas={"Arjun->Rahul": {"trust": 5.0, "rapport": 3.0, "tension": -2.0, "respect": 2.0, "power_balance": 1.0}},
        key_event="Opening statement",
        turning_point_reason=None,
    )
    return ObserverService(llm_client=mock_llm)


def make_turn_event(session_id="sess_test", turn_index=0) -> TurnEvent:
    return TurnEvent(
        session_id=session_id,
        turn_index=turn_index,
        speaker="Arjun",
        listeners=["Rahul"],
        message="Dad, I want to pursue music.",
    )


# ── Pipeline tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_emit_and_worker_processes_turn():
    service = make_mock_service()
    pipeline = ObserverPipeline(observer=service)

    pipeline.get_or_create_session("s1", participants=["Arjun", "Rahul"], scenario_description="Test")
    pipeline.start_worker("s1")

    event = make_turn_event("s1", 0)
    await pipeline.emit_turn(event)

    # Wait for the worker to process
    await asyncio.sleep(0.5)

    obs = pipeline.get_observations("s1")
    assert len(obs) == 1
    assert obs[0].speaker == "Arjun"
    assert obs[0].sentiment == "positive"


@pytest.mark.asyncio
async def test_pipeline_finalize_marks_done():
    service = make_mock_service()
    # Also mock finalize
    mock_scorecard = ConversationScorecard(
        session_id="s2",
        overall_realism=8.0,
        outcome_category="Best Case",
    )
    service._llm.complete_structured.side_effect = [
        _ObserverTurnLLMOutput(sentiment="neutral", sentiment_score=0.0, emotion_labels=[]),
        _ScorecardLLMOutput(overall_realism=8.0, outcome_category="Best Case"),
    ]

    pipeline = ObserverPipeline(observer=service)
    pipeline.get_or_create_session("s2", participants=["Arjun", "Rahul"])
    pipeline.start_worker("s2")

    await pipeline.emit_turn(make_turn_event("s2", 0))
    await pipeline.finalize_session("s2")

    # Wait for worker to drain + finalize
    await asyncio.sleep(1.0)

    pipe = pipeline._sessions["s2"]
    assert pipe.finalized is True


@pytest.mark.asyncio
async def test_pipeline_sse_stream_receives_turn_and_observation():
    service = make_mock_service()
    pipeline = ObserverPipeline(observer=service)

    pipeline.get_or_create_session("s3", participants=["Arjun", "Rahul"])
    pipeline.start_worker("s3")

    received = []

    async def collect():
        async for chunk in pipeline.sse_stream("s3"):
            received.append(chunk)
            if len(received) >= 3:  # turn + observation + trajectory
                break

    collect_task = asyncio.ensure_future(collect())
    await asyncio.sleep(0.1)

    await pipeline.emit_turn(make_turn_event("s3", 0))
    await asyncio.sleep(0.5)

    collect_task.cancel()
    try:
        await collect_task
    except asyncio.CancelledError:
        pass

    event_types = [chunk.split("\n")[0].replace("event: ", "") for chunk in received if chunk.startswith("event:")]
    assert "turn" in event_types
    assert "observation" in event_types


def test_sse_event_format():
    data = {"key": "value", "number": 42}
    result = _sse_event("test_event", data)
    assert result.startswith("event: test_event\n")
    assert "data: " in result
    assert result.endswith("\n\n")
    payload = json.loads(result.split("data: ")[1].strip())
    assert payload["key"] == "value"
    assert payload["number"] == 42


# ── Storage tests ─────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test_observer.db"
    init_db(db_path)
    return ObserverStorage(db_path=db_path)


def test_storage_upsert_and_list_session(tmp_db):
    tmp_db.upsert_session("sess_abc", scenario="Test scenario", participants=["Alice", "Bob"])
    sessions = tmp_db.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "sess_abc"
    assert sessions[0]["scenario"] == "Test scenario"


def test_storage_mark_finalized(tmp_db):
    tmp_db.upsert_session("sess_fin")
    tmp_db.mark_finalized("sess_fin")
    sessions = tmp_db.list_sessions()
    assert sessions[0]["finalized_at"] is not None


def test_storage_save_and_get_observation(tmp_db):
    tmp_db.upsert_session("sess_obs")
    obs = TurnObservation(
        session_id="sess_obs",
        turn_index=0,
        speaker="Alice",
        sentiment="positive",
        sentiment_score=0.7,
        emotion_labels=["excited"],
        dyad_states=[DyadState.initial("Alice", "Bob")],
    )
    tmp_db.save_observation(obs)

    loaded = tmp_db.get_observations("sess_obs")
    assert len(loaded) == 1
    assert loaded[0].speaker == "Alice"
    assert loaded[0].sentiment == "positive"


def test_storage_save_and_get_scorecard(tmp_db):
    tmp_db.upsert_session("sess_sc")
    sc = ConversationScorecard(
        session_id="sess_sc",
        overall_realism=9.0,
        outcome_category="Best Case",
        summary="Great conversation.",
    )
    tmp_db.save_scorecard(sc)

    loaded = tmp_db.get_scorecard("sess_sc")
    assert loaded is not None
    assert loaded.overall_realism == 9.0
    assert loaded.outcome_category == "Best Case"


def test_storage_get_nonexistent_scorecard_returns_none(tmp_db):
    result = tmp_db.get_scorecard("nonexistent_session")
    assert result is None
