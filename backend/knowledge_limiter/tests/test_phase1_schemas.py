"""Phase 1 tests — schemas, helpers, and config.

Run with:
    python -m pytest backend/knowledge_limiter/tests/test_phase1_schemas.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.knowledge_limiter.schemas.constants import LEVEL_ORDER
from backend.knowledge_limiter.schemas.helpers import (
    get_level,
    level_diff,
    level_gte,
    level_lt,
)
from backend.knowledge_limiter.schemas.models import (
    BoundaryBehavior,
    Concept,
    ConceptLexiconEntry,
    KLPersona,
    KnowledgeConfig,
    Level,
    PersonalityProfile,
    Scenario,
    Tone,
    Topic,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_personality() -> PersonalityProfile:
    return PersonalityProfile(
        traits=["curious", "analytical"],
        speech_style="formal",
        boundary_behavior=BoundaryBehavior.admit,
    )


@pytest.fixture()
def sample_persona(sample_personality: PersonalityProfile) -> KLPersona:
    return KLPersona(
        id="persona_alice",
        name="Alice",
        personality=sample_personality,
        profession="Data Scientist",
        default_level=Level.basic,
        own_domain="artificial_intelligence",
        background_summary="Alice works on ML pipelines and model evaluation.",
    )


@pytest.fixture()
def sample_knowledge_config() -> KnowledgeConfig:
    return KnowledgeConfig(
        scenario_id="scenario_001",
        per_persona={
            "persona_alice": {
                "artificial_intelligence": Level.expert,
                "medicine": Level.layperson,
            }
        },
        concept_lexicon={
            "transformer": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
        },
    )


# ---------------------------------------------------------------------------
# Level ordering
# ---------------------------------------------------------------------------


class TestLevelOrdering:
    """Verify that the Level enum and LEVEL_ORDER encode the correct ordering."""

    def test_level_order_values(self) -> None:
        assert LEVEL_ORDER[Level.layperson] < LEVEL_ORDER[Level.basic]
        assert LEVEL_ORDER[Level.basic] < LEVEL_ORDER[Level.advanced]
        assert LEVEL_ORDER[Level.advanced] < LEVEL_ORDER[Level.expert]

    def test_all_levels_present(self) -> None:
        assert set(LEVEL_ORDER.keys()) == set(Level)

    def test_level_enum_string_values(self) -> None:
        """Level enum members serialise as plain strings."""
        assert Level.layperson.value == "layperson"
        assert Level.expert.value == "expert"


# ---------------------------------------------------------------------------
# level_gte
# ---------------------------------------------------------------------------


class TestLevelGte:
    def test_same_level(self) -> None:
        assert level_gte(Level.basic, Level.basic) is True

    def test_higher_gte_lower(self) -> None:
        assert level_gte(Level.expert, Level.layperson) is True

    def test_lower_not_gte_higher(self) -> None:
        assert level_gte(Level.layperson, Level.advanced) is False

    def test_adjacent_levels(self) -> None:
        assert level_gte(Level.advanced, Level.basic) is True
        assert level_gte(Level.basic, Level.advanced) is False


# ---------------------------------------------------------------------------
# level_lt
# ---------------------------------------------------------------------------


class TestLevelLt:
    def test_same_level(self) -> None:
        assert level_lt(Level.basic, Level.basic) is False

    def test_lower_lt_higher(self) -> None:
        assert level_lt(Level.layperson, Level.expert) is True

    def test_higher_not_lt_lower(self) -> None:
        assert level_lt(Level.expert, Level.basic) is False


# ---------------------------------------------------------------------------
# level_diff
# ---------------------------------------------------------------------------


class TestLevelDiff:
    def test_same_returns_zero(self) -> None:
        assert level_diff(Level.basic, Level.basic) == 0

    def test_positive_when_above(self) -> None:
        # expert(3) - layperson(0) = 3
        assert level_diff(Level.expert, Level.layperson) == 3

    def test_negative_when_below(self) -> None:
        # layperson(0) - expert(3) = -3
        assert level_diff(Level.layperson, Level.expert) == -3

    def test_adjacent_diff(self) -> None:
        assert level_diff(Level.advanced, Level.basic) == 1
        assert level_diff(Level.basic, Level.advanced) == -1


# ---------------------------------------------------------------------------
# get_level
# ---------------------------------------------------------------------------


class TestGetLevel:
    def test_returns_config_level_when_domain_in_config(
        self,
        sample_persona: KLPersona,
        sample_knowledge_config: KnowledgeConfig,
    ) -> None:
        level = get_level(sample_persona, sample_knowledge_config, "artificial_intelligence")
        assert level == Level.expert

    def test_returns_config_level_for_secondary_domain(
        self,
        sample_persona: KLPersona,
        sample_knowledge_config: KnowledgeConfig,
    ) -> None:
        level = get_level(sample_persona, sample_knowledge_config, "medicine")
        assert level == Level.layperson

    def test_falls_back_to_default_when_domain_not_in_config(
        self,
        sample_persona: KLPersona,
        sample_knowledge_config: KnowledgeConfig,
    ) -> None:
        level = get_level(sample_persona, sample_knowledge_config, "economics")
        # persona.default_level is basic
        assert level == Level.basic

    def test_falls_back_when_persona_not_in_per_persona(
        self,
        sample_personality: PersonalityProfile,
        sample_knowledge_config: KnowledgeConfig,
    ) -> None:
        unknown_persona = KLPersona(
            id="persona_unknown",
            name="Bob",
            personality=sample_personality,
            profession="Chef",
            default_level=Level.layperson,
            own_domain="culinary_arts",
            background_summary="Bob is a professional chef.",
        )
        level = get_level(unknown_persona, sample_knowledge_config, "artificial_intelligence")
        assert level == Level.layperson


# ---------------------------------------------------------------------------
# KLPersona serialisation
# ---------------------------------------------------------------------------


class TestKLPersonaSerialization:
    def test_model_dump_roundtrip(self, sample_persona: KLPersona) -> None:
        dumped = sample_persona.model_dump()
        restored = KLPersona.model_validate(dumped)
        assert restored == sample_persona

    def test_level_serialised_as_string(self, sample_persona: KLPersona) -> None:
        dumped = sample_persona.model_dump()
        assert dumped["default_level"] == "basic"

    def test_boundary_behavior_serialised_as_string(self, sample_persona: KLPersona) -> None:
        dumped = sample_persona.model_dump()
        assert dumped["personality"]["boundary_behavior"] == "admit"

    def test_json_roundtrip(self, sample_persona: KLPersona) -> None:
        json_str = sample_persona.model_dump_json()
        restored = KLPersona.model_validate_json(json_str)
        assert restored == sample_persona

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            # 'own_domain' is required
            KLPersona(
                id="x",
                name="X",
                personality=PersonalityProfile(
                    traits=[],
                    speech_style="casual",
                    boundary_behavior=BoundaryBehavior.bluff,
                ),
                profession="Tester",
                background_summary="No domain provided.",
            )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# KnowledgeConfig serialisation
# ---------------------------------------------------------------------------


class TestKnowledgeConfigSerialization:
    def test_model_dump_roundtrip(self, sample_knowledge_config: KnowledgeConfig) -> None:
        dumped = sample_knowledge_config.model_dump()
        restored = KnowledgeConfig.model_validate(dumped)
        assert restored == sample_knowledge_config

    def test_per_persona_levels_serialised_as_strings(
        self, sample_knowledge_config: KnowledgeConfig
    ) -> None:
        dumped = sample_knowledge_config.model_dump()
        alice_levels = dumped["per_persona"]["persona_alice"]
        assert alice_levels["artificial_intelligence"] == "expert"
        assert alice_levels["medicine"] == "layperson"

    def test_concept_lexicon_serialised(self, sample_knowledge_config: KnowledgeConfig) -> None:
        dumped = sample_knowledge_config.model_dump()
        entry = dumped["concept_lexicon"]["transformer"]
        assert entry["domain"] == "artificial_intelligence"
        assert entry["min_level"] == "advanced"


# ---------------------------------------------------------------------------
# Scenario serialisation
# ---------------------------------------------------------------------------


class TestScenarioSerialization:
    @pytest.fixture()
    def sample_scenario(self) -> Scenario:
        return Scenario(
            id="scenario_001",
            description="A debate between a doctor and an AI researcher.",
            tone=Tone.debate,
            personas=["persona_alice", "persona_bob"],
            topics=[
                Topic(
                    id="topic_ai_ethics",
                    name="AI Ethics",
                    domain="artificial_intelligence",
                    concepts=[
                        Concept(term="bias in models", min_level=Level.basic),
                        Concept(term="alignment problem", min_level=Level.advanced),
                    ],
                    levels={"persona_alice": Level.expert, "persona_bob": Level.layperson},
                )
            ],
        )

    def test_model_dump_roundtrip(self, sample_scenario: Scenario) -> None:
        dumped = sample_scenario.model_dump()
        restored = Scenario.model_validate(dumped)
        assert restored == sample_scenario

    def test_tone_serialised_as_string(self, sample_scenario: Scenario) -> None:
        dumped = sample_scenario.model_dump()
        assert dumped["tone"] == "debate"

    def test_topic_levels_serialised_as_strings(self, sample_scenario: Scenario) -> None:
        dumped = sample_scenario.model_dump()
        topic_levels = dumped["topics"][0]["levels"]
        assert topic_levels["persona_alice"] == "expert"
        assert topic_levels["persona_bob"] == "layperson"

    def test_json_roundtrip(self, sample_scenario: Scenario) -> None:
        json_str = sample_scenario.model_dump_json()
        restored = Scenario.model_validate_json(json_str)
        assert restored == sample_scenario
