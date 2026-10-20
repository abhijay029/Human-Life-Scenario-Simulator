"""Helper functions for knowledge level comparisons and lookups."""

from __future__ import annotations

from .constants import LEVEL_ORDER
from .models import KLPersona, KnowledgeConfig, Level


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
