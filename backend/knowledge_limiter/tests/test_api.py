"""
Tests for Knowledge Limiter FastAPI endpoints.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.knowledge_limiter.api.routes import router as kl_router
from backend.knowledge_limiter.schemas.models import (
    KLPersona,
    PersonalityProfile,
    BoundaryBehavior,
    Level,
    Tone,
    ResponseMode,
    Topic,
    Concept,
    KnowledgeConfig,
    ConceptLexiconEntry,
)
from backend.knowledge_limiter.topic_generation.generator import TopicGenerationOutput
from backend.knowledge_limiter.generation.persona_generator import PersonaGenerationResult

test_app = FastAPI()
test_app.include_router(kl_router)


@pytest.fixture
def client():
    return TestClient(test_app)


def test_save_config_endpoint(client):
    doctor = KLPersona(
        id="doc",
        name="Dr. Chen",
        profession="Cardiologist",
        personality=PersonalityProfile(
            traits=["precise"],
            speech_style="medical",
            boundary_behavior=BoundaryBehavior.ask_back,
        ),
        default_level=Level.layperson,
        own_domain="medicine",
        background_summary="Cardiologist",
    )
    topic = Topic(
        id="top_1",
        name="Heart Health",
        domain="medicine",
        concepts=[Concept(term="echocardiogram", min_level=Level.basic)],
        levels={"doc": Level.expert},
    )

    payload = {
        "scenario_id": "sc1",
        "personas": [doctor.model_dump()],
        "topics": [topic.model_dump()],
    }

    res = client.post("/kl/config/save", json=payload)
    assert res.status_code == 200
    data = res.json()
    cfg = data["knowledge_config"]
    assert cfg["scenario_id"] == "sc1"
    assert cfg["per_persona"]["doc"]["medicine"] == "expert"
    assert "echocardiogram" in cfg["concept_lexicon"]


def test_generate_topics_endpoint(client):
    with patch("backend.knowledge_limiter.api.routes._topic_generator") as mock_gen:
        mock_gen.generate.return_value = TopicGenerationOutput(
            topics=[
                Topic(
                    id="t1",
                    name="Diagnostics",
                    domain="medicine",
                    concepts=[Concept(term="ecg", min_level=Level.basic)],
                    levels={"p1": Level.expert},
                )
            ]
        )
        payload = {
            "scenario_description": "Doctor talks to engineer",
            "tone": "discussion",
            "personas": [
                {
                    "name": "Dr. Sarah",
                    "profession": "Doctor",
                    "background_summary": "10 years experience",
                }
            ],
        }
        res = client.post("/kl/topics/generate", json=payload)
        assert res.status_code == 200
        assert len(res.json()["topics"]) == 1


def test_chat_endpoint(client):
    doctor = KLPersona(
        id="doc",
        name="Dr. Chen",
        profession="Cardiologist",
        personality=PersonalityProfile(
            traits=["precise"],
            speech_style="medical",
            boundary_behavior=BoundaryBehavior.ask_back,
        ),
        default_level=Level.layperson,
        own_domain="medicine",
        background_summary="Cardiologist",
    )
    config = KnowledgeConfig(
        scenario_id="sc1",
        per_persona={"doc": {"medicine": Level.expert, "ai": Level.layperson}},
        concept_lexicon={"echocardiogram": ConceptLexiconEntry(domain="medicine", min_level=Level.basic)},
    )

    with patch("backend.knowledge_limiter.api.routes._generator") as mock_gen:
        mock_gen.generate.return_value = PersonaGenerationResult(
            reply="The echocardiogram showed regular valve functioning.",
            prompt_used="prompt",
            latency_ms=120.0,
        )

        payload = {
            "message": "How is the patient's heart?",
            "scenario_description": "Cardiology clinic",
            "tone": "discussion",
            "knowledge_config": config.model_dump(),
            "target_persona": doctor.model_dump(),
            "history": [],
        }

        res = client.post("/kl/chat/doc", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["reply"] == "The echocardiogram showed regular valve functioning."
        assert data["target_persona_id"] == "doc"
        assert "latency_breakdown_ms" in data
