"""Phase 2 tests — TopicGenerator.

Run with:
    python -m pytest backend/knowledge_limiter/tests/test_phase2_topic_generation.py -v

All LLM calls are mocked — no real API calls are made.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.knowledge_limiter.schemas.models import Level, Tone, Topic, Concept
from backend.knowledge_limiter.topic_generation.generator import (
    KLPersonaInput,
    TopicGenerationInput,
    TopicGenerationOutput,
    TopicGenerator,
    _RawTopicGenerationOutput,
    _RawTopic,
    _RawConcept,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_input(
    description: str = "A doctor and an AI researcher discuss healthcare AI.",
    tone: Tone = Tone.discussion,
    professions: list[str] | None = None,
) -> TopicGenerationInput:
    if professions is None:
        professions = ["Doctor", "AI Researcher"]
    personas = [
        KLPersonaInput(name=f"Persona{i}", profession=p, background_summary=f"Background of {p}.")
        for i, p in enumerate(professions)
    ]
    return TopicGenerationInput(
        scenario_description=description,
        tone=tone,
        personas=personas,
    )


def _minimal_raw_topics_json() -> str:
    """Return a minimal valid JSON string matching _RawTopicGenerationOutput."""
    return json.dumps(
        {
            "topics": [
                {
                    "id": "topic_ai_diagnosis",
                    "name": "AI in Medical Diagnosis",
                    "domain": "artificial_intelligence",
                    "concepts": [
                        {"term": "machine learning", "min_level": "basic"},
                        {"term": "diagnostic accuracy", "min_level": "advanced"},
                    ],
                    "suggested_levels": {
                        "Persona0": "advanced",
                        "Persona1": "expert",
                    },
                },
                {
                    "id": "topic_patient_data_privacy",
                    "name": "Patient Data Privacy",
                    "domain": "ethics",
                    "concepts": [
                        {"term": "HIPAA", "min_level": "layperson"},
                        {"term": "federated learning", "min_level": "expert"},
                    ],
                    "suggested_levels": {
                        "Persona0": "advanced",
                        "Persona1": "basic",
                    },
                },
            ]
        }
    )


def _make_raw_output() -> _RawTopicGenerationOutput:
    """Build a _RawTopicGenerationOutput object for use in structured-output mocks."""
    return _RawTopicGenerationOutput.model_validate(json.loads(_minimal_raw_topics_json()))


@pytest.fixture()
def mock_llm() -> MagicMock:
    llm = MagicMock()
    llm.complete_structured.return_value = _make_raw_output()
    return llm


@pytest.fixture()
def generator(mock_llm: MagicMock, tmp_path: pathlib.Path) -> TopicGenerator:
    """A TopicGenerator with a mocked LLM and a temporary cache directory."""
    gen = TopicGenerator(llm_client=mock_llm)
    # Override cache dir to use tmp_path so tests don't pollute the real cache.
    with patch(
        "backend.knowledge_limiter.topic_generation.generator.settings"
    ) as mock_settings:
        mock_settings.TOPIC_CACHE_DIR = str(tmp_path / "kl_topics")
        mock_settings.FAST_MODEL = "gemini-2.5-flash"
        gen._cache_path = lambda key: tmp_path / "kl_topics" / f"{key}.json"  # type: ignore[method-assign]
        (tmp_path / "kl_topics").mkdir(parents=True, exist_ok=True)
        yield gen


# ---------------------------------------------------------------------------
# Cache key determinism
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_same_input_same_key(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp = _make_input()
        assert gen._cache_key(inp) == gen._cache_key(inp)

    def test_profession_order_does_not_matter(self) -> None:
        """Professions are sorted before hashing so order is irrelevant."""
        gen = TopicGenerator(llm_client=MagicMock())
        inp_a = _make_input(professions=["Doctor", "AI Researcher"])
        inp_b = _make_input(professions=["AI Researcher", "Doctor"])
        assert gen._cache_key(inp_a) == gen._cache_key(inp_b)

    def test_different_description_different_key(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp_a = _make_input(description="Scenario A")
        inp_b = _make_input(description="Scenario B")
        assert gen._cache_key(inp_a) != gen._cache_key(inp_b)

    def test_different_tone_different_key(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp_a = _make_input(tone=Tone.casual)
        inp_b = _make_input(tone=Tone.debate)
        assert gen._cache_key(inp_a) != gen._cache_key(inp_b)

    def test_key_is_hex_sha256(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp = _make_input()
        key = gen._cache_key(inp)
        # SHA-256 hex digest is 64 characters long
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


# ---------------------------------------------------------------------------
# Decision points (scenario -> decision -> topics ordering)
# ---------------------------------------------------------------------------


class TestDecisionPoints:
    def test_no_decision_points_keeps_original_key(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp = _make_input()
        inp_empty = inp.model_copy(update={"decision_points": ["", "  "]})
        assert gen._cache_key(inp) == gen._cache_key(inp_empty)

    def test_decision_point_changes_key(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp = _make_input()
        with_dp = inp.model_copy(update={"decision_points": ["Tell the truth"]})
        assert gen._cache_key(inp) != gen._cache_key(with_dp)

    def test_decision_point_order_does_not_matter(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp = _make_input()
        a = inp.model_copy(update={"decision_points": ["one", "two"]})
        b = inp.model_copy(update={"decision_points": ["two", "one"]})
        assert gen._cache_key(a) == gen._cache_key(b)

    def test_prompt_contains_single_decision_point(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp = _make_input().model_copy(update={"decision_points": ["Reveal the music deal"]})
        prompt = gen._render_prompt(inp)
        assert "Decision point being explored: Reveal the music deal" in prompt

    def test_prompt_lists_multiple_branches(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        inp = _make_input().model_copy(update={"decision_points": ["Branch A", "Branch B"]})
        prompt = gen._render_prompt(inp)
        assert "Decision branches being compared:" in prompt
        assert "- Branch A" in prompt and "- Branch B" in prompt

    def test_prompt_omits_section_without_decision_points(self) -> None:
        gen = TopicGenerator(llm_client=MagicMock())
        prompt = gen._render_prompt(_make_input())
        assert "Decision point" not in prompt and "Decision branches" not in prompt


# ---------------------------------------------------------------------------
# _parse_raw
# ---------------------------------------------------------------------------


class TestParseRaw:
    @pytest.fixture()
    def gen(self) -> TopicGenerator:
        return TopicGenerator(llm_client=MagicMock())

    def test_parses_valid_json(self, gen: TopicGenerator) -> None:
        inp = _make_input()
        raw = _minimal_raw_topics_json()
        output = gen._parse_raw(raw, inp)

        assert isinstance(output, TopicGenerationOutput)
        assert len(output.topics) == 2

    def test_topic_fields_correct(self, gen: TopicGenerator) -> None:
        inp = _make_input()
        output = gen._parse_raw(_minimal_raw_topics_json(), inp)

        first = output.topics[0]
        assert first.id == "topic_ai_diagnosis"
        assert first.name == "AI in Medical Diagnosis"
        assert first.domain == "artificial_intelligence"

    def test_concepts_parsed(self, gen: TopicGenerator) -> None:
        inp = _make_input()
        output = gen._parse_raw(_minimal_raw_topics_json(), inp)
        first = output.topics[0]

        assert len(first.concepts) == 2
        assert first.concepts[0].term == "machine learning"
        assert first.concepts[0].min_level == Level.basic

    def test_suggested_levels_become_topic_levels(self, gen: TopicGenerator) -> None:
        inp = _make_input()
        output = gen._parse_raw(_minimal_raw_topics_json(), inp)
        first = output.topics[0]

        assert first.levels["Persona0"] == Level.advanced
        assert first.levels["Persona1"] == Level.expert

    def test_raises_value_error_on_invalid_json(self, gen: TopicGenerator) -> None:
        inp = _make_input()
        with pytest.raises(ValueError, match="invalid JSON"):
            gen._parse_raw("this is not json {{{", inp)

    def test_raises_value_error_on_wrong_schema(self, gen: TopicGenerator) -> None:
        inp = _make_input()
        bad_json = json.dumps({"wrong_key": []})
        with pytest.raises(ValueError, match="schema"):
            gen._parse_raw(bad_json, inp)

    def test_raises_value_error_on_invalid_level(self, gen: TopicGenerator) -> None:
        inp = _make_input()
        bad_json = json.dumps(
            {
                "topics": [
                    {
                        "id": "topic_x",
                        "name": "X",
                        "domain": "misc",
                        "concepts": [{"term": "y", "min_level": "INVALID_LEVEL"}],
                        "suggested_levels": {"Persona0": "layperson"},
                    }
                ]
            }
        )
        with pytest.raises(ValueError):
            gen._parse_raw(bad_json, inp)


# ---------------------------------------------------------------------------
# Cache hit behaviour
# ---------------------------------------------------------------------------


class TestCacheHit:
    def test_llm_not_called_on_cache_hit(self, tmp_path: pathlib.Path) -> None:
        """The LLM must NOT be called when a valid cached result exists."""
        mock_llm = MagicMock()
        mock_llm.complete_structured.return_value = _make_raw_output()

        gen = TopicGenerator(llm_client=mock_llm)
        cache_dir = tmp_path / "kl_cache"
        cache_dir.mkdir()

        inp = _make_input()
        key = gen._cache_key(inp)

        # Manually pre-populate the cache.
        expected = TopicGenerationOutput(
            topics=[
                Topic(
                    id="topic_cached",
                    name="Cached Topic",
                    domain="daily_life",
                    concepts=[Concept(term="cooking", min_level=Level.layperson)],
                    levels={"Persona0": Level.layperson},
                )
            ]
        )
        cache_file = cache_dir / f"{key}.json"
        cache_file.write_text(expected.model_dump_json(), encoding="utf-8")

        # Patch settings and _cache_path so the generator uses our tmp dir.
        with patch(
            "backend.knowledge_limiter.topic_generation.generator.settings"
        ) as mock_settings:
            mock_settings.TOPIC_CACHE_DIR = str(cache_dir)
            mock_settings.FAST_MODEL = "gemini-2.5-flash"
            gen._cache_path = lambda k: cache_dir / f"{k}.json"  # type: ignore[method-assign]

            result = gen.generate(inp)

        # LLM must not have been invoked.
        mock_llm.complete_structured.assert_not_called()

        # Returned result must match cached data.
        assert result.topics[0].id == "topic_cached"

    def test_llm_called_on_cache_miss(self, tmp_path: pathlib.Path) -> None:
        """The LLM MUST be called when there is no cached result."""
        mock_llm = MagicMock()
        mock_llm.complete_structured.return_value = _make_raw_output()

        gen = TopicGenerator(llm_client=mock_llm)
        cache_dir = tmp_path / "kl_cache_miss"
        cache_dir.mkdir()

        inp = _make_input()

        with patch(
            "backend.knowledge_limiter.topic_generation.generator.settings"
        ) as mock_settings:
            mock_settings.TOPIC_CACHE_DIR = str(cache_dir)
            mock_settings.FAST_MODEL = "gemini-2.5-flash"
            gen._cache_path = lambda k: cache_dir / f"{k}.json"  # type: ignore[method-assign]

            result = gen.generate(inp)

        mock_llm.complete_structured.assert_called_once()
        assert len(result.topics) == 2

    def test_result_is_cached_after_generation(self, tmp_path: pathlib.Path) -> None:
        """After a successful generation the result should be written to cache."""
        mock_llm = MagicMock()
        mock_llm.complete_structured.return_value = _make_raw_output()

        gen = TopicGenerator(llm_client=mock_llm)
        cache_dir = tmp_path / "kl_cache_write"
        cache_dir.mkdir()

        inp = _make_input()
        key = gen._cache_key(inp)

        with patch(
            "backend.knowledge_limiter.topic_generation.generator.settings"
        ) as mock_settings:
            mock_settings.TOPIC_CACHE_DIR = str(cache_dir)
            mock_settings.FAST_MODEL = "gemini-2.5-flash"
            gen._cache_path = lambda k: cache_dir / f"{k}.json"  # type: ignore[method-assign]

            gen.generate(inp)

        assert (cache_dir / f"{key}.json").exists()
