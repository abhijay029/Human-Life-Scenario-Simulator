"""Helper functions for knowledge level comparisons and lookups."""

from __future__ import annotations

import re
from typing import Iterable

from .constants import LEVEL_ORDER
from .models import KLPersona, KnowledgeConfig, Level

MAX_BRIEF_FACTS_PER_TURN = 6


def level_gte(a: Level, b: Level) -> bool:
    """Return True if level *a* is greater than or equal to level *b*."""
    return LEVEL_ORDER[a] >= LEVEL_ORDER[b]


def level_lt(a: Level, b: Level) -> bool:
    """Return True if level *a* is strictly less than level *b*."""
    return LEVEL_ORDER[a] < LEVEL_ORDER[b]


def level_diff(persona_level: Level, required_level: Level) -> int:
    """Return the signed difference (persona_level rank − required_level rank).

    Positive → persona is *above* the required level.
    Zero     → exact match.
    Negative → persona is *below* the required level.
    """
    return LEVEL_ORDER[persona_level] - LEVEL_ORDER[required_level]


def get_level(
    persona: KLPersona,
    knowledge_config: KnowledgeConfig,
    domain: str,
) -> Level:
    """Look up the knowledge level for *persona* in *domain*.

    First checks ``knowledge_config.per_persona[persona.id][domain]``.
    Falls back to ``persona.default_level`` if the domain is not configured.
    """
    per_persona_map = knowledge_config.per_persona.get(persona.id, {})
    return per_persona_map.get(domain, persona.default_level)


def _level_for_domain_ci(
    persona: KLPersona, knowledge_config: KnowledgeConfig, domain: str
) -> Level:
    """Like :func:`get_level` but tolerant of case/whitespace differences in the domain key."""
    wanted = domain.strip().lower()
    for key, level in knowledge_config.per_persona.get(persona.id, {}).items():
        if key.strip().lower() == wanted:
            return level
    return persona.default_level


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def select_brief_facts(
    persona: KLPersona,
    knowledge_config: KnowledgeConfig,
    domains: Iterable[str],
    focus: str = "",
    limit: int = MAX_BRIEF_FACTS_PER_TURN,
) -> list[str]:
    """Return expert-brief facts *persona* is allowed to use for *domains*.

    A fact is only returned when the persona's level in that fact's domain is at or
    above the fact's ``min_level`` — so a layperson never receives expert knowledge.
    If *focus* (e.g. the incoming message) is given, facts sharing more words with
    it are listed first. At most *limit* facts are returned.
    """
    briefs = {k.strip().lower(): v for k, v in knowledge_config.expert_briefs.items()}
    if not briefs:
        return []

    focus_words = _words(focus)
    scored: list[tuple[int, int, str]] = []  # (-overlap, original position, text)
    seen: set[str] = set()
    for domain in domains:
        key = domain.strip().lower()
        if key in seen or key not in briefs:
            continue
        seen.add(key)
        level = _level_for_domain_ci(persona, knowledge_config, domain)
        for fact in briefs[key]:
            if level_gte(level, fact.min_level):
                overlap = len(focus_words & _words(fact.text))
                scored.append((-overlap, len(scored), fact.text))

    scored.sort()
    return [text for _, _, text in scored[:limit]]
