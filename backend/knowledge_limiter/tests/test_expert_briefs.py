"""Tests for expert briefs: level gating, research pipeline, config compile, prompt injection.

All LLM / web calls are mocked.
"""
from __future__ import annotations

import pathlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.knowledge_limiter.api.routes import router as kl_router
from backend.knowledge_limiter.generation.persona_generator import (
    ConversationTurn,
    PersonaGenerator,
)
from backend.knowledge_limiter.llm_client import (
    GroundedResult,
    LLMClient,
    _extract_grounding_sources,
)
from backend.knowledge_limiter.research import brief_generator as bg
from backend.knowledge_limiter.research.brief_generator import (
    BriefGenerator,
    _clean_facts,
    _RawBriefOutput,
    _RawFact,
)
from backend.knowledge_limiter.schemas.helpers import select_brief_facts
from backend.knowledge_limiter.schemas.models import (
    BoundaryBehavior,
    BriefFact,
    Concept,
    KLPersona,
    KnowledgeConfig,
    Level,
    PersonalityProfile,
    ResponseMode,
    Tone,
    Topic,
    TopicBrief,
)


def _persona(pid: str = "p1", own: str = "medicine", default: Level = Level.layperson) -> KLPersona:
    return KLPersona(
        id=pid,
        name=pid.upper(),
        profession="Doctor",
        personality=PersonalityProfile(
            traits=["calm"], speech_style="plain", boundary_behavior=BoundaryBehavior.admit
        ),
        default_level=default,
        own_domain=own,
        background_summary="A doctor.",
    )


FACTS = [
    BriefFact(text="Statins lower LDL cholesterol in most adults.", min_level=Level.basic),
    BriefFact(text="Guidelines now stratify risk using lipoprotein(a) testing.", min_level=Level.advanced),
    BriefFact(text="Inclisiran dosing needs only two injections a year.", min_level=Level.expert),
]


def _config(level: Level, domain: str = "medicine") -> KnowledgeConfig:
    return KnowledgeConfig(
        scenario_id="s",
        per_persona={"p1": {domain: level}},
        expert_briefs={domain: FACTS},
    )


# --------------------------------------------------------------------------- gating


class TestSelectBriefFacts:
    @pytest.mark.parametrize(
        "level,expected",
        [(Level.layperson, 0), (Level.basic, 1), (Level.advanced, 2), (Level.expert, 3)],
    )
    def test_facts_gated_by_persona_level(self, level: Level, expected: int) -> None:
        out = select_brief_facts(_persona(), _config(level), ["medicine"])
        assert len(out) == expected

    def test_layperson_gets_nothing_even_in_own_domain_default(self) -> None:
        assert select_brief_facts(_persona(), _config(Level.layperson), ["medicine"]) == []

    def test_unconfigured_domain_falls_back_to_default_level(self) -> None:
        cfg = KnowledgeConfig(scenario_id="s", per_persona={"p1": {}}, expert_briefs={"law": FACTS})
        assert select_brief_facts(_persona(default=Level.layperson), cfg, ["law"]) == []
        assert len(select_brief_facts(_persona(default=Level.expert), cfg, ["law"])) == 3

    def test_other_domains_are_not_leaked(self) -> None:
        cfg = _config(Level.expert, "medicine")
        assert select_brief_facts(_persona(), cfg, ["economics"]) == []

    def test_domain_match_is_case_insensitive(self) -> None:
        cfg = _config(Level.expert, "medicine")
        assert len(select_brief_facts(_persona(), cfg, ["  Medicine "])) == 3

    def test_no_briefs_returns_empty(self) -> None:
        cfg = KnowledgeConfig(scenario_id="s", per_persona={"p1": {"medicine": Level.expert}})
        assert select_brief_facts(_persona(), cfg, ["medicine"]) == []

    def test_focus_message_ranks_relevant_facts_first(self) -> None:
        out = select_brief_facts(
            _persona(), _config(Level.expert), ["medicine"], focus="what about inclisiran injections?"
        )
        assert out[0].startswith("Inclisiran")

    def test_limit_applies(self) -> None:
        assert len(select_brief_facts(_persona(), _config(Level.expert), ["medicine"], limit=2)) == 2


# ----------------------------------------------------------------- persona prompt


class TestPromptInjection:
    def _generate(self, level: Level) -> str:
        llm = MagicMock()
        llm.complete.return_value = "ok"
        res = PersonaGenerator(llm).generate(
            persona=_persona(),
            knowledge_config=_config(level),
            scenario_description="scenario",
            tone=Tone.discussion,
            response_mode=ResponseMode.understands,
            history=[ConversationTurn("X", "tell me about cholesterol")],
            domains=["medicine"],
            focus_message="tell me about cholesterol",
        )
        return res.prompt_used

    def test_expert_prompt_contains_all_facts(self) -> None:
        prompt = self._generate(Level.expert)
        assert "THINGS YOU KNOW FROM YOUR WORK" in prompt
        assert "Inclisiran" in prompt and "Statins" in prompt

    def test_advanced_prompt_excludes_expert_fact(self) -> None:
        prompt = self._generate(Level.advanced)
        assert "lipoprotein(a)" in prompt
        assert "Inclisiran" not in prompt

    def test_layperson_prompt_has_no_section(self) -> None:
        prompt = self._generate(Level.layperson)
        assert "THINGS YOU KNOW FROM YOUR WORK" not in prompt
        assert "Statins" not in prompt

    def test_domains_omitted_means_no_briefs(self) -> None:
        llm = MagicMock()
        llm.complete.return_value = "ok"
        res = PersonaGenerator(llm).generate(
            persona=_persona(),
            knowledge_config=_config(Level.expert),
            scenario_description="s",
            tone=Tone.discussion,
            response_mode=ResponseMode.understands,
            history=[],
        )
        assert "THINGS YOU KNOW FROM YOUR WORK" not in res.prompt_used


# -------------------------------------------------------------------- generation


def _topic(tid: str, levels: dict[str, Level], name: str = "Cholesterol") -> Topic:
    return Topic(
        id=tid,
        name=name,
        domain="medicine",
        concepts=[Concept(term="LDL", min_level=Level.basic)],
        levels=levels,
    )


class TestCleanFacts:
    def test_layperson_is_clamped_to_basic(self) -> None:
        out = _clean_facts([_RawFact(text="A reasonably long factual sentence.", min_level=Level.layperson)])
        assert out[0].min_level == Level.basic

    def test_drops_short_long_and_duplicate(self) -> None:
        raw = [
            _RawFact(text="too short", min_level=Level.advanced),
            _RawFact(text="x" * 400, min_level=Level.advanced),
            _RawFact(text="A valid fact about something real.", min_level=Level.advanced),
            _RawFact(text="a  valid fact about SOMETHING real.", min_level=Level.expert),
        ]
        assert len(_clean_facts(raw)) == 1

    def test_newlines_collapsed(self) -> None:
        out = _clean_facts([_RawFact(text="Line one\n\nline two is here.", min_level=Level.advanced)])
        assert "\n" not in out[0].text


@pytest.fixture
def brief_env(tmp_path: pathlib.Path):
    llm = MagicMock()
    llm.complete_grounded.return_value = GroundedResult(
        text="notes", sources=[{"title": "Site", "url": "https://x.test/a"}], grounded=True
    )
    llm.complete_structured.return_value = _RawBriefOutput(
        facts=[
            _RawFact(text="Established fact about the field.", min_level=Level.advanced),
            _RawFact(text="A very recent niche development here.", min_level=Level.expert),
        ]
    )
    with patch.object(bg.settings, "BRIEF_CACHE_DIR", str(tmp_path / "briefs")):
        yield llm


class TestBriefGenerator:
    def test_only_advanced_or_expert_topics_are_researched(self, brief_env) -> None:
        gen = BriefGenerator(brief_env)
        topics = [
            _topic("lay", {"p1": Level.layperson, "p2": Level.basic}, "Easy"),
            _topic("exp", {"p1": Level.layperson, "p2": Level.expert}, "Hard"),
        ]
        res = gen.generate(topics)
        assert set(res.briefs) == {"exp"}
        assert res.skipped == ["lay"]
        assert brief_env.complete_grounded.call_count == 1

    def test_research_prompt_has_only_topic_info(self, brief_env) -> None:
        gen = BriefGenerator(brief_env)
        gen.generate([_topic("exp", {"p1": Level.expert}, "Cholesterol")])
        prompt = brief_env.complete_grounded.call_args.args[0][0]["content"]
        assert "Cholesterol" in prompt and "LDL" in prompt
        # No scenario / persona fields exist in the prompt context
        assert "scenario" not in prompt.lower()

    def test_sources_and_grounded_flag_are_returned(self, brief_env) -> None:
        res = BriefGenerator(brief_env).generate([_topic("exp", {"p1": Level.expert})])
        brief = res.briefs["exp"]
        assert brief.grounded is True
        assert brief.sources[0].url == "https://x.test/a"
        assert len(brief.facts) == 2

    def test_grounded_brief_is_cached(self, brief_env) -> None:
        gen = BriefGenerator(brief_env)
        topics = [_topic("exp", {"p1": Level.expert})]
        gen.generate(topics)
        gen.generate(topics)
        assert brief_env.complete_grounded.call_count == 1

    def test_ungrounded_brief_is_not_cached(self, brief_env) -> None:
        brief_env.complete_grounded.return_value = GroundedResult(text="notes", grounded=False)
        gen = BriefGenerator(brief_env)
        topics = [_topic("exp", {"p1": Level.expert})]
        first = gen.generate(topics)
        gen.generate(topics)
        assert first.briefs["exp"].grounded is False
        assert brief_env.complete_grounded.call_count == 2

    def test_failure_is_reported_per_topic_not_raised(self, brief_env) -> None:
        brief_env.complete_grounded.side_effect = RuntimeError("quota")
        res = BriefGenerator(brief_env).generate([_topic("exp", {"p1": Level.expert})])
        assert res.briefs == {} and "quota" in res.errors["exp"]

    def test_caps_number_of_researched_topics(self, brief_env) -> None:
        topics = [_topic(f"t{i}", {"p1": Level.expert}, f"Topic {i}") for i in range(12)]
        res = BriefGenerator(brief_env).generate(topics)
        assert len(res.briefs) == bg.MAX_RESEARCHED_TOPICS
        assert len(res.skipped) == 4


# --------------------------------------------------------------- grounding / LLM


class TestGroundingSources:
    def test_snake_case_chunks_deduped(self) -> None:
        resp = SimpleNamespace(
            response_metadata={
                "grounding_metadata": {
                    "grounding_chunks": [
                        {"web": {"uri": "https://a.test", "title": "A"}},
                        {"web": {"uri": "https://a.test", "title": "A again"}},
                        {"web": {"uri": "https://b.test", "title": "B"}},
                    ]
                }
            }
        )
        assert [s["url"] for s in _extract_grounding_sources(resp)] == ["https://a.test", "https://b.test"]

    def test_camel_case_and_missing(self) -> None:
        camel = SimpleNamespace(
            response_metadata={"groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://c.test"}}]}}
        )
        assert _extract_grounding_sources(camel)[0]["url"] == "https://c.test"
        assert _extract_grounding_sources(SimpleNamespace(response_metadata={})) == []

    def test_no_keys_falls_back_ungrounded(self) -> None:
        client = LLMClient()
        with patch("backend.knowledge_limiter.llm_client.get_gemini_keys", return_value=[]), patch.object(
            LLMClient, "complete", return_value="plain text"
        ):
            res = client.complete_grounded([{"role": "user", "content": "hi"}])
        assert res.grounded is False and res.text == "plain text"

    def test_gemini_with_sources_is_grounded(self) -> None:
        response = SimpleNamespace(
            content="researched text",
            response_metadata={"grounding_metadata": {"grounding_chunks": [{"web": {"uri": "https://d.test"}}]}},
        )
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = response
        with patch("backend.knowledge_limiter.llm_client.get_gemini_keys", return_value=["k"]), patch(
            "backend.knowledge_limiter.llm_client._build_gemini_llm", return_value=fake_llm
        ), patch("backend.knowledge_limiter.llm_client._messages_to_lc", return_value=[]):
            res = LLMClient().complete_grounded([{"role": "user", "content": "hi"}])
        fake_llm.bind_tools.assert_called_once_with([{"google_search": {}}])
        assert res.grounded is True and res.sources[0]["url"] == "https://d.test"

    def test_gemini_without_sources_is_not_marked_grounded(self) -> None:
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = SimpleNamespace(
            content="text", response_metadata={}
        )
        with patch("backend.knowledge_limiter.llm_client.get_gemini_keys", return_value=["k"]), patch(
            "backend.knowledge_limiter.llm_client._build_gemini_llm", return_value=fake_llm
        ), patch("backend.knowledge_limiter.llm_client._messages_to_lc", return_value=[]):
            res = LLMClient().complete_grounded([{"role": "user", "content": "hi"}])
        assert res.grounded is False


# ------------------------------------------------------------------------- API

_app = FastAPI()
_app.include_router(kl_router)


@pytest.fixture
def client():
    return TestClient(_app)


def test_save_config_compiles_expert_briefs(client) -> None:
    topic_a = _topic("a", {"p1": Level.expert}).model_copy(
        update={"brief": TopicBrief(facts=[BriefFact(text="Fact one is here today.", min_level=Level.advanced)])}
    )
    topic_b = _topic("b", {"p1": Level.expert}, "Other").model_copy(
        update={
            "brief": TopicBrief(
                facts=[
                    BriefFact(text="fact one is here today.", min_level=Level.expert),  # dup, higher level
                    BriefFact(text="Fact two is here too.", min_level=Level.basic),
                    BriefFact(text="   ", min_level=Level.basic),  # blank dropped
                ]
            )
        }
    )
    payload = {
        "scenario_id": "s",
        "personas": [_persona().model_dump(mode="json")],
        "topics": [topic_a.model_dump(mode="json"), topic_b.model_dump(mode="json")],
    }
    res = client.post("/kl/config/save", json=payload)
    assert res.status_code == 200
    facts = res.json()["knowledge_config"]["expert_briefs"]["medicine"]
    by_text = {f["text"].lower(): f["min_level"] for f in facts}
    assert by_text == {"fact one is here today.": "expert", "fact two is here too.": "basic"}


def test_save_config_without_briefs_has_empty_expert_briefs(client) -> None:
    payload = {
        "scenario_id": "s",
        "personas": [_persona().model_dump(mode="json")],
        "topics": [_topic("a", {"p1": Level.expert}).model_dump(mode="json")],
    }
    res = client.post("/kl/config/save", json=payload)
    assert res.json()["knowledge_config"]["expert_briefs"] == {}


def test_generate_briefs_endpoint(client) -> None:
    from backend.knowledge_limiter.api import routes

    with patch.object(
        routes._brief_generator,
        "generate",
        return_value=bg.BriefGenerationResult(
            briefs={"a": TopicBrief(facts=[BriefFact(text="Some fact about it.", min_level=Level.expert)], grounded=True)},
            skipped=["b"],
        ),
    ):
        res = client.post(
            "/kl/briefs/generate",
            json={"topics": [_topic("a", {"p1": Level.expert}).model_dump(mode="json")]},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["briefs"]["a"]["grounded"] is True and body["skipped"] == ["b"]


# ------------------------------------------------------ full chat route (gating e2e)


def _chat(client, persona_level: Level) -> str:
    """Call /kl/chat and return the prompt the persona LLM received."""
    from backend.knowledge_limiter.api import routes
    from backend.knowledge_limiter.schemas.models import ConceptLexiconEntry

    cfg = _config(persona_level).model_copy(
        update={"concept_lexicon": {"ldl": ConceptLexiconEntry(domain="medicine", min_level=Level.basic)}}
    )
    captured: dict[str, str] = {}

    def fake_complete(messages, model=None, temperature=None):
        captured["prompt"] = messages[0]["content"]
        return "Sure, sounds good."

    with patch.object(routes._llm_client, "complete", side_effect=fake_complete):
        res = client.post(
            "/kl/chat/p1",
            json={
                "message": "What about LDL and inclisiran?",
                "scenario_description": "A check-up.",
                "knowledge_config": cfg.model_dump(mode="json"),
                "target_persona": _persona().model_dump(mode="json"),
                "history": [],
            },
        )
    assert res.status_code == 200, res.text
    return captured["prompt"]


def test_chat_route_gives_expert_persona_the_brief(client) -> None:
    prompt = _chat(client, Level.expert)
    assert "Inclisiran dosing" in prompt


def test_chat_route_withholds_expert_facts_from_advanced_persona(client) -> None:
    prompt = _chat(client, Level.advanced)
    assert "lipoprotein(a)" in prompt
    assert "Inclisiran dosing" not in prompt


def test_chat_route_gives_layperson_no_brief(client) -> None:
    prompt = _chat(client, Level.layperson)
    assert "THINGS YOU KNOW FROM YOUR WORK" not in prompt
