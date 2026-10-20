"""Phase 7 tests — KLPersonaMemory and dynamic learning."""
from __future__ import annotations

import pytest
from backend.knowledge_limiter.schemas.models import Level, ConceptLexiconEntry
from backend.knowledge_limiter.memory.persona_memory import KLPersonaMemory


@pytest.fixture
def sample_lexicon():
    return {
        "transformer": ConceptLexiconEntry(domain="ai", min_level=Level.advanced),
        "backpropagation": ConceptLexiconEntry(domain="ai", min_level=Level.advanced),
        "lora": ConceptLexiconEntry(domain="ai", min_level=Level.expert),
    }


class TestPersonaMemory:
    def test_memory_isolation_only_contains_heard(self):
        mem = KLPersonaMemory(persona_id="p1")
        mem.add_heard(speaker="Alice", message="Hello", turn_index=0)
        mem.add_heard(speaker="Bob", message="Hi Alice", turn_index=1)

        history = mem.get_history_text()
        assert "Alice: Hello" in history
        assert "Bob: Hi Alice" in history
        assert "Charlie" not in history

    def test_learning_disabled_returns_base_level(self):
        mem = KLPersonaMemory(persona_id="p1", enable_learning=False)
        mem.learn_concept("transformer", Level.advanced)
        eff = mem.get_effective_level("transformer", Level.layperson)
        assert eff == Level.layperson

    def test_learning_enabled_upgrades_level(self):
        mem = KLPersonaMemory(persona_id="p1", enable_learning=True)
        mem.learn_concept("transformer", Level.basic)
        eff = mem.get_effective_level("transformer", Level.layperson)
        assert eff == Level.basic

    def test_learning_does_not_downgrade(self):
        mem = KLPersonaMemory(persona_id="p1", enable_learning=True)
        mem.learn_concept("transformer", Level.basic)
        eff = mem.get_effective_level("transformer", Level.expert)
        assert eff == Level.expert

    def test_inspect_for_learning_detects_explanation(self, sample_lexicon):
        mem = KLPersonaMemory(persona_id="doc", enable_learning=True)
        explained = mem.inspect_for_learning(
            speaker="Alex",
            message="A transformer is essentially a neural network architecture designed for sequence modeling.",
            lexicon=sample_lexicon,
        )
        assert "transformer" in explained
        assert mem.get_effective_level("transformer", Level.layperson) == Level.basic
