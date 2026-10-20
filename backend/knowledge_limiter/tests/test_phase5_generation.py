"""Phase 5 tests — PersonaGenerator.

All LLM calls are mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.knowledge_limiter.schemas.models import (
    KLPersona,
    PersonalityProfile,
    BoundaryBehavior,
    Level,
    Tone,
    ResponseMode,
    KnowledgeConfig,
)
from backend.knowledge_limiter.generation.persona_generator import (
    PersonaGenerator,
    ConversationTurn,
)
from backend.knowledge_limiter.generation.response_mode_instructions import (
    get_response_mode_instruction,
)


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.complete.return_value = "As a cardiologist, I recommend checking vitals first."
    return llm


@pytest.fixture
def doctor_persona():
    return KLPersona(
        id="doc1",
        name="Dr. Chen",
        profession="Cardiologist",
        personality=PersonalityProfile(
            traits=["observant", "cautious"],
            speech_style="professional",
            boundary_behavior=BoundaryBehavior.ask_back,
        ),
        default_level=Level.layperson,
        own_domain="medicine",
        background_summary="Specialist in cardiovascular health.",
    )


@pytest.fixture
def sample_config():
    return KnowledgeConfig(
        scenario_id="s1",
        per_persona={
            "doc1": {
                "artificial_intelligence": Level.layperson,
            }
        },
    )


class TestPersonaGenerator:
    def test_knowledge_description_includes_own_domain(self, mock_llm, doctor_persona, sample_config):
        gen = PersonaGenerator(mock_llm)
        desc = gen._build_knowledge_description(doctor_persona, sample_config)
        assert "About medicine" in desc
        assert "expert" in desc.lower()

    def test_knowledge_description_respects_config_level(self, mock_llm, doctor_persona, sample_config):
        gen = PersonaGenerator(mock_llm)
        desc = gen._build_knowledge_description(doctor_persona, sample_config)
        assert "About artificial_intelligence" in desc
        assert "curious non-expert" in desc or "layperson" in desc or "news" in desc

    def test_response_mode_instruction_understands(self):
        instr = get_response_mode_instruction(ResponseMode.understands)
        assert "expertise" in instr

    def test_response_mode_instruction_lost(self):
        instr = get_response_mode_instruction(ResponseMode.lost)
        assert "simpler explanation" in instr or "confusion" in instr

    def test_response_mode_instruction_analogizes_includes_domain(self):
        instr = get_response_mode_instruction(ResponseMode.analogizes, own_domain="cardiology")
        assert "cardiology" in instr

    def test_generate_calls_llm_with_prompt(self, mock_llm, doctor_persona, sample_config):
        gen = PersonaGenerator(mock_llm)
        res = gen.generate(
            persona=doctor_persona,
            knowledge_config=sample_config,
            scenario_description="Conference chat",
            tone=Tone.discussion,
            response_mode=ResponseMode.lost,
            history=[ConversationTurn("Alex", "We used deep backpropagation")],
        )
        assert res.reply == "As a cardiologist, I recommend checking vitals first."
        assert "Dr. Chen" in res.prompt_used
        assert res.latency_ms >= 0
        mock_llm.complete.assert_called_once()
