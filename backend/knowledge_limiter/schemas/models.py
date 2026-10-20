"""Pydantic v2 data models for the Knowledge Limiter module."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Level enum — ordered: layperson < basic < advanced < expert
# Stored as plain str values so Pydantic serialises them as strings.
# ---------------------------------------------------------------------------

class Level(str, Enum):
    layperson = "layperson"
    basic = "basic"
    advanced = "advanced"
    expert = "expert"


# ---------------------------------------------------------------------------
# Tone enum
# ---------------------------------------------------------------------------

class Tone(str, Enum):
    casual = "casual"
    debate = "debate"
    discussion = "discussion"


# ---------------------------------------------------------------------------
# ResponseMode & BoundaryBehavior enums
# ---------------------------------------------------------------------------

class ResponseMode(str, Enum):
    understands = "understands"
    partial = "partial"
    lost = "lost"
    analogizes = "analogizes"


class BoundaryBehavior(str, Enum):
    admit = "admit"
    bluff = "bluff"
    deflect = "deflect"
    ask_back = "ask_back"
    analogize = "analogize"


# ---------------------------------------------------------------------------
# Concept
# ---------------------------------------------------------------------------

class Concept(BaseModel):
    """A key concept within a topic, tagged with the minimum Level required."""

    term: str = Field(..., description="The concept term or phrase.")
    min_level: Level = Field(..., description="Minimum knowledge level to use/understand this concept.")


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

class Topic(BaseModel):
    """A conversation topic with per-persona knowledge levels."""

    id: str = Field(..., description="Snake-case identifier, e.g. 'topic_machine_learning'.")
    name: str = Field(..., description="Human-readable topic name.")
    domain: str = Field(..., description="Domain label, e.g. 'medicine', 'economics'.")
    concepts: list[Concept] = Field(default_factory=list)
    levels: dict[str, Level] = Field(
        default_factory=dict,
        description="Mapping of persona_id (str) → Level for this topic.",
    )


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

class Scenario(BaseModel):
    """A full conversation scenario with participants and topics."""

    id: str
    description: str
    tone: Tone
    personas: list[str] = Field(
        default_factory=list,
        description="List of persona IDs participating in this scenario.",
    )
    topics: list[Topic] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# KnowledgeConfig
# ---------------------------------------------------------------------------

class ConceptLexiconEntry(BaseModel):
    """Entry in the concept lexicon mapping a term to its domain and minimum level."""

    domain: str
    min_level: Level


class KnowledgeConfig(BaseModel):
    """Runtime knowledge configuration for a scenario."""

    scenario_id: str
    # Nested mapping: { persona_id: { domain: Level } }
    per_persona: dict[str, dict[str, Level]] = Field(
        default_factory=dict,
        description="Per-persona domain knowledge levels.",
    )
    # { term_lower: ConceptLexiconEntry }
    concept_lexicon: dict[str, ConceptLexiconEntry] = Field(
        default_factory=dict,
        description="Concept lexicon mapping lowercase term → domain & min_level.",
    )


# ---------------------------------------------------------------------------
# PersonalityProfile
# ---------------------------------------------------------------------------

class PersonalityProfile(BaseModel):
    """Personality and speech profile for a KL persona."""

    traits: list[str] = Field(default_factory=list, description="Personality trait descriptors.")
    speech_style: str = Field(..., description="E.g. 'formal', 'casual', 'technical'.")
    boundary_behavior: BoundaryBehavior = Field(
        ...,
        description="How this persona behaves when at the boundary of their knowledge.",
    )


# ---------------------------------------------------------------------------
# KLPersona  (distinct from backend/agents/persona.py::Persona)
# ---------------------------------------------------------------------------

class KLPersona(BaseModel):
    """Knowledge-Limiter persona — separate from the existing simulation Persona."""

    id: str = Field(..., description="Unique persona identifier.")
    name: str
    personality: PersonalityProfile
    profession: str
    default_level: Level = Field(
        Level.layperson,
        description="Fallback knowledge level when domain is not configured.",
    )
    own_domain: str = Field(..., description="The domain this persona is an expert in.")
    background_summary: str = Field(..., description="Short background context (1-3 sentences).")
