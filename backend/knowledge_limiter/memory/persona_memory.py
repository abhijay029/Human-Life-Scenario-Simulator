"""
Conversation memory and dynamic knowledge learning for Knowledge Limiter.

Core requirements:
1. Strict isolation: each persona's memory contains only what that persona has
   actually heard or spoken. Private background/facts from others are never leaked.
2. Concept learning (optional, togglable per scenario):
   When another speaker explains a concept clearly, temporarily raises that
   persona's level for that specific concept so they don't act confused again
   5 turns later.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from pydantic import BaseModel, Field

from ..schemas.models import Level, ConceptLexiconEntry
from ..schemas.constants import LEVEL_ORDER
from ..schemas.helpers import level_gte

logger = logging.getLogger(__name__)


class Utterance(BaseModel):
    speaker: str
    message: str
    turn_index: int


class KLPersonaMemory:
    """Manages isolated conversation memory and learned concepts for one persona."""

    def __init__(self, persona_id: str, enable_learning: bool = True) -> None:
        self.persona_id = persona_id
        self.enable_learning = enable_learning
        self.heard_utterances: list[Utterance] = []
        # concept_term_lower -> raised Level
        self.learned_concepts: dict[str, Level] = {}

    def add_heard(self, speaker: str, message: str, turn_index: int) -> None:
        """Record an utterance that this persona actually heard."""
        self.heard_utterances.append(
            Utterance(speaker=speaker, message=message, turn_index=turn_index)
        )

    def get_history_text(self, window: int = 6) -> str:
        """Return the recent conversation slice witnessed by this persona."""
        recent = self.heard_utterances[-window:]
        if not recent:
            return "(conversation just started)"
        return "\n".join(f"{u.speaker}: {u.message}" for u in recent)

    def learn_concept(self, term: str, new_level: Level) -> None:
        """Temporarily upgrade the knowledge level for a specific concept."""
        if not self.enable_learning:
            return
        term_lower = term.lower().strip()
        current = self.learned_concepts.get(term_lower)
        if current is None or LEVEL_ORDER[new_level] > LEVEL_ORDER[current]:
            self.learned_concepts[term_lower] = new_level
            logger.info(
                "[Memory] Persona %s learned concept '%s' up to level %s",
                self.persona_id,
                term_lower,
                new_level.value,
            )

    def get_effective_level(self, term: str, base_level: Level) -> Level:
        """Return effective level taking into account any dynamically learned concepts."""
        if not self.enable_learning:
            return base_level
        term_lower = term.lower().strip()
        learned = self.learned_concepts.get(term_lower)
        if learned is not None and LEVEL_ORDER[learned] > LEVEL_ORDER[base_level]:
            return learned
        return base_level

    def inspect_for_learning(
        self, speaker: str, message: str, lexicon: dict[str, ConceptLexiconEntry]
    ) -> list[str]:
        """Check if incoming message explains a concept clearly to this persona.

        Patterns recognized:
        - "X is a ...", "X means ...", "X basically ..."
        """
        if not self.enable_learning:
            return []

        learned_terms: list[str] = []
        msg_lower = message.lower()

        # Explanation patterns
        patterns = [
            r"\b([a-z0-9_\-\s]{3,30})\s+(?:is|are|means|refers to|stands for)\s+(?:a|an|the|essentially|basically)",
            r"(?:think of|essentially)\s+([a-z0-9_\-\s]{3,30})\s+as",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, msg_lower):
                candidate = match.group(1).strip()
                # Check if candidate matches any lexicon term
                for term, entry in lexicon.items():
                    if term == candidate or term in candidate:
                        # Raised to basic if previously layperson
                        self.learn_concept(term, Level.basic)
                        learned_terms.append(term)

        return learned_terms
