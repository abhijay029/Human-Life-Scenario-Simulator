"""Constants for the Knowledge Limiter module."""

from __future__ import annotations

from .models import Level

# ---------------------------------------------------------------------------
# LEVEL_DESCRIPTIONS
# Maps each Level to a human-readable description of what can/cannot be used.
# ---------------------------------------------------------------------------

LEVEL_DESCRIPTIONS: dict[Level, str] = {
    Level.layperson: (
        "News-level awareness only. Can discuss broad ideas (e.g. 'AI chatbots exist', "
        "'vaccines prevent disease') but cannot explain mechanisms or use field terminology. "
        "Must NOT use jargon, acronyms, or technical vocabulary from the domain."
    ),
    Level.basic: (
        "High-level how-it-works understanding. Knows that 'neural networks learn from data' "
        "or 'antibiotics kill bacteria' but does not know implementation details or edge cases. "
        "May use common terms but must avoid specialist or sub-field vocabulary."
    ),
    Level.advanced: (
        "Standard field competency. Comfortable with recognised field terminology such as "
        "'transformer architecture' or 'randomised controlled trials'. Can discuss trade-offs, "
        "limitations, and well-known methodologies. May NOT use cutting-edge or niche concepts."
    ),
    Level.expert: (
        "Cutting-edge and niche mastery. Can use terms like 'LoRA fine-tuning' or "
        "'CRISPR off-target effects', discuss recent research, subtle distinctions, and "
        "open problems in the field. No vocabulary restrictions within the domain."
    ),
}

# ---------------------------------------------------------------------------
# LEVEL_ORDER
# Maps each Level to an integer rank for numeric comparisons.
# ---------------------------------------------------------------------------

LEVEL_ORDER: dict[Level, int] = {
    Level.layperson: 0,
    Level.basic: 1,
    Level.advanced: 2,
    Level.expert: 3,
}
