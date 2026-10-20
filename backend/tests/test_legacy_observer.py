"""
Automated pytest tests for legacy observer.py with mocked LLM.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import pytest

from backend.agents.observer import analyse_dialogue, Observation


@pytest.fixture
def mock_observation_dict():
    return {
        "turn_sentiments": [
            {
                "turn": 1,
                "speaker": "Rahul",
                "sentiment": "negative",
                "score": 0.8,
                "note": "Firm disapproval of music career",
            },
            {
                "turn": 2,
                "speaker": "Arjun",
                "sentiment": "neutral",
                "score": 0.6,
                "note": "Tentative explanation of contract",
            },
        ],
        "relationship_trajectory": "deteriorating",
        "trajectory_explanation": "Growing tension over career choices",
        "persona_goal_success": [
            {
                "persona": "Rahul",
                "goal_summary": "Prevent impulsive decisions",
                "success_probability": 0.75,
                "reasoning": "Maintained authoritative stance",
            },
            {
                "persona": "Arjun",
                "goal_summary": "Secure approval for music",
                "success_probability": 0.25,
                "reasoning": "Father remains resistant",
            },
        ],
        "outcome_category": "Most Likely",
        "outcome_summary": "Dialogue ended in a stalemate with unresolved career tension.",
        "key_turning_points": ["Arjun revealed the contract offer"],
        "recommendations": ["Acknowledge father's financial security concerns"],
    }


def test_analyse_dialogue_empty_log_returns_empty():
    res = analyse_dialogue(
        dialogue_log=[],
        scenario="Test scenario",
        decision_point="Test decision",
        personas=[{"name": "Rahul", "goals": ["safe job"]}],
    )
    assert res == {}


def test_analyse_dialogue_success(mock_observation_dict):
    with patch("backend.agents.observer._chain") as mock_chain:
        mock_chain.invoke.return_value = mock_observation_dict

        dialogue = [
            {"speaker": "Rahul", "message": "Engineering is a stable career."},
            {"speaker": "Arjun", "message": "I want to produce music full time."},
        ]
        personas = [
            {"name": "Rahul", "goals": ["ensure safe career"]},
            {"name": "Arjun", "goals": ["pursue music"]},
        ]

        result = analyse_dialogue(
            dialogue_log=dialogue,
            scenario="Career conversation",
            decision_point="Arjun tells Rahul",
            personas=personas,
        )

        assert result["outcome_category"] == "Most Likely"
        assert result["relationship_trajectory"] == "deteriorating"
        assert len(result["turn_sentiments"]) == 2
        mock_chain.invoke.assert_called_once()


def test_observation_schema_validates_aligned_categories():
    data = {
        "turn_sentiments": [],
        "relationship_trajectory": "improving",
        "trajectory_explanation": "Constructive listening",
        "persona_goal_success": [],
        "outcome_category": "Best Case",
        "outcome_summary": "Mutual agreement reached.",
        "key_turning_points": [],
        "recommendations": [],
    }
    obs = Observation(**data)
    assert obs.outcome_category == "Best Case"
