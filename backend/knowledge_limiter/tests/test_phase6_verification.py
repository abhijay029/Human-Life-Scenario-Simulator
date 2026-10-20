"""Phase 6 tests — OutputVerifier.

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
    ResponseMode,
    KnowledgeConfig,
    ConceptLexiconEntry,
)
from backend.knowledge_limiter.verification.verifier import (
    OutputVerifier,
)


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def doctor_persona():
    return KLPersona(
        id="doctor",
        name="Dr. Sarah",
        profession="Cardiologist",
        personality=PersonalityProfile(
            traits=["careful"],
            speech_style="medical",
            boundary_behavior=BoundaryBehavior.ask_back,
        ),
        default_level=Level.layperson,
        own_domain="medicine",
        background_summary="Cardiologist",
    )


@pytest.fixture
def sample_config():
    return KnowledgeConfig(
        scenario_id="s1",
        per_persona={
            "doctor": {
                "medicine": Level.expert,
                "artificial_intelligence": Level.layperson,
            }
        },
        concept_lexicon={
            "transformer": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
            "backpropagation": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
            "lora": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.expert),
            "echocardiogram": ConceptLexiconEntry(domain="medicine", min_level=Level.basic),
        },
    )


class TestOutputVerifier:
    def test_lexicon_check_clean_reply(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        v = verifier.lexicon_check("I work with heart patients daily.", doctor_persona, sample_config)
        assert len(v) == 0

    def test_lexicon_check_violation(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        # Doctor using 'transformer' independently
        v = verifier.lexicon_check(
            "We used a transformer to diagnose the arrhythmias.", doctor_persona, sample_config
        )
        assert len(v) == 1
        assert v[0].term == "transformer"
        assert v[0].persona_level == "layperson"

    def test_lexicon_check_echoed_term_allowed(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        last_message = "Our model uses a transformer architecture."
        reply = "What exactly is a transformer in this context?"
        v = verifier.lexicon_check(reply, doctor_persona, sample_config, last_message=last_message)
        assert len(v) == 0

    def test_lexicon_check_in_domain_allowed(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        # echocardiogram is medicine/basic, doctor is medicine/expert
        v = verifier.lexicon_check(
            "An echocardiogram will clarify the valve condition.", doctor_persona, sample_config
        )
        assert len(v) == 0

    def test_verify_passes_clean_reply(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        res = verifier.verify(
            reply="I agree, let us monitor the patient.",
            persona=doctor_persona,
            knowledge_config=sample_config,
            response_mode=ResponseMode.understands,
        )
        assert res.passed is True
        assert len(res.violations) == 0

    def test_verify_fails_on_lexicon_violation(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        res = verifier.verify(
            reply="We must adjust the backpropagation weights.",
            persona=doctor_persona,
            knowledge_config=sample_config,
            response_mode=ResponseMode.understands,
        )
        assert res.passed is False
        assert len(res.violations) == 1

    def test_verify_over_restriction_warning(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        res = verifier.verify(
            reply="Dunno.",
            persona=doctor_persona,
            knowledge_config=sample_config,
            response_mode=ResponseMode.understands,
        )
        assert res.over_restriction_warning is True

    def test_verify_llm_not_called_by_default(self, mock_llm, doctor_persona, sample_config):
        verifier = OutputVerifier(mock_llm)
        verifier.verify(
            reply="I'm curious how your software works.",
            persona=doctor_persona,
            knowledge_config=sample_config,
            response_mode=ResponseMode.lost,
            run_llm_verifier=False,
        )
        mock_llm.complete_structured.assert_not_called()

    def test_verify_llm_called_when_requested(self, mock_llm, doctor_persona, sample_config):
        class LLMOut(BaseModel):
            violation: bool
            span: str
            reason: str

        mock_llm.complete_structured.return_value = LLMOut(
            violation=True,
            span="gradient descent",
            reason="Unplausible jargon for layperson",
        )
        verifier = OutputVerifier(mock_llm)
        res = verifier.verify(
            reply="The gradient descent was erratic.",
            persona=doctor_persona,
            knowledge_config=sample_config,
            response_mode=ResponseMode.lost,
            run_llm_verifier=True,
        )
        assert res.passed is False
        assert res.llm_violation is True
        assert res.llm_span == "gradient descent"
