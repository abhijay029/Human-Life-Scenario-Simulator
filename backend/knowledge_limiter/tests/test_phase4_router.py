"""Phase 4 tests — MessageRouter and Classification.

All LLM calls are mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from pydantic import BaseModel

from backend.knowledge_limiter.schemas.models import (
    KLPersona,
    PersonalityProfile,
    BoundaryBehavior,
    Level,
    Tone,
    ResponseMode,
    KnowledgeConfig,
    ConceptLexiconEntry,
)
from backend.knowledge_limiter.router.classifier import (
    MessageRouter,
    ClassificationResult,
)


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def sample_config():
    return KnowledgeConfig(
        scenario_id="s1",
        per_persona={
            "doctor": {
                "medicine": Level.expert,
                "artificial_intelligence": Level.layperson,
            },
            "engineer": {
                "medicine": Level.layperson,
                "artificial_intelligence": Level.expert,
            },
        },
        concept_lexicon={
            "transformer": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
            "backpropagation": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
            "lora": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.expert),
            "neural network": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.basic),
            "echocardiogram": ConceptLexiconEntry(domain="medicine", min_level=Level.basic),
        },
    )


@pytest.fixture
def doctor_persona():
    return KLPersona(
        id="doctor",
        name="Dr. Sarah",
        profession="Cardiologist",
        personality=PersonalityProfile(
            traits=["analytical"],
            speech_style="formal",
            boundary_behavior=BoundaryBehavior.admit,
        ),
        default_level=Level.layperson,
        own_domain="medicine",
        background_summary="Experienced cardiologist.",
    )


class TestMessageRouter:
    def test_lexicon_prepass_hit_short_message(self, mock_llm, sample_config):
        router = MessageRouter(mock_llm)
        res = router.classify("Have you tried LoRA?", sample_config)
        assert res.via_lexicon is True
        assert res.primary_domain == "artificial_intelligence"
        assert res.required_level == Level.expert
        mock_llm.complete_structured.assert_not_called()

    def test_lexicon_prepass_miss_triggers_llm(self, mock_llm, sample_config):
        class Out(BaseModel):
            domains: list[str]
            required_level: Level
            primary_domain: str

        mock_llm.complete_structured.return_value = Out(
            domains=["ethics"],
            required_level=Level.basic,
            primary_domain="ethics",
        )
        router = MessageRouter(mock_llm)
        res = router.classify("We must consider moral culpability in autonomous systems.", sample_config)
        assert res.via_lexicon is False
        assert res.primary_domain == "ethics"
        assert res.required_level == Level.basic
        mock_llm.complete_structured.assert_called_once()

    def test_lexicon_highest_level_wins(self, mock_llm, sample_config):
        router = MessageRouter(mock_llm)
        # "neural network" (basic) and "transformer" (advanced)
        res = router.classify("A neural network with a transformer block", sample_config)
        assert res.required_level == Level.advanced

    def test_classify_falls_back_on_llm_failure(self, mock_llm, sample_config):
        mock_llm.complete_structured.side_effect = RuntimeError("API Down")
        router = MessageRouter(mock_llm)
        res = router.classify("Something totally unrelated and without lexicon hits", sample_config)
        assert res.primary_domain == "general"
        assert res.required_level == Level.layperson

    def test_route_understands_when_diff_gte_0(self, mock_llm, sample_config, doctor_persona):
        router = MessageRouter(mock_llm)
        # Echocardiogram is medicine / basic. Doctor is medicine / expert (diff = 3 - 1 = +2 >= 0)
        res = router.route("Can we check the echocardiogram?", doctor_persona, sample_config)
        assert res.response_mode == ResponseMode.understands
        assert res.diff >= 0

    def test_route_partial_when_diff_minus1(self, mock_llm, sample_config, doctor_persona):
        router = MessageRouter(mock_llm)
        # neural network is AI / basic. Doctor is AI / layperson. diff = 0 - 1 = -1
        res = router.route("We trained a neural network.", doctor_persona, sample_config)
        assert res.response_mode == ResponseMode.partial
        assert res.diff == -1

    def test_route_lost_when_diff_minus2_admit(self, mock_llm, sample_config, doctor_persona):
        router = MessageRouter(mock_llm)
        # transformer is AI / advanced. Doctor is AI / layperson. diff = 0 - 2 = -2. Doctor admits.
        res = router.route("Let's talk about the transformer architecture.", doctor_persona, sample_config)
        assert res.response_mode == ResponseMode.lost
        assert res.diff <= -2

    def test_route_analogizes_when_diff_minus2_analogize(self, mock_llm, sample_config):
        analogizing_doc = KLPersona(
            id="doctor",
            name="Dr. Sarah",
            profession="Cardiologist",
            personality=PersonalityProfile(
                traits=["creative"],
                speech_style="formal",
                boundary_behavior=BoundaryBehavior.analogize,
            ),
            default_level=Level.layperson,
            own_domain="medicine",
            background_summary="Doctor who makes analogies.",
        )
        router = MessageRouter(mock_llm)
        res = router.route("We optimized with LoRA adapters.", analogizing_doc, sample_config)
        assert res.response_mode == ResponseMode.analogizes

    def test_route_partial_when_bluff_and_debate(self, mock_llm, sample_config):
        bluffing_doc = KLPersona(
            id="doctor",
            name="Dr. Sarah",
            profession="Cardiologist",
            personality=PersonalityProfile(
                traits=["proud"],
                speech_style="confident",
                boundary_behavior=BoundaryBehavior.bluff,
            ),
            default_level=Level.layperson,
            own_domain="medicine",
            background_summary="Never admits not knowing.",
        )
        router = MessageRouter(mock_llm)
        res = router.route(
            "We optimized with LoRA adapters.", bluffing_doc, sample_config, tone=Tone.debate
        )
        assert res.response_mode == ResponseMode.partial

    def test_route_partial_when_deflect(self, mock_llm, sample_config):
        deflecting_doc = KLPersona(
            id="doctor",
            name="Dr. Sarah",
            profession="Cardiologist",
            personality=PersonalityProfile(
                traits=["evasive"],
                speech_style="smooth",
                boundary_behavior=BoundaryBehavior.deflect,
            ),
            default_level=Level.layperson,
            own_domain="medicine",
            background_summary="Changes the topic smoothly.",
        )
        router = MessageRouter(mock_llm)
        res = router.route("We optimized with LoRA adapters.", deflecting_doc, sample_config)
        assert res.response_mode == ResponseMode.partial
