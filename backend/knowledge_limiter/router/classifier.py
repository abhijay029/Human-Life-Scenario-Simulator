"""
Runtime router for the Knowledge Limiter module.

For each incoming message directed at a persona:
1. Classify: which domains it touches and what concept level it requires.
   (Lexicon pre-pass skips LLM call for obviously matched concepts/messages)
2. Compare required level vs. the persona's level for that domain.
3. Select ResponseMode:
   - understands: required level <= persona level (diff >= 0)
   - partial: one level above (diff == -1)
   - lost: two or more levels above (diff <= -2)
   - analogizes: above level AND persona's own_domain offers a natural analogy
   Respects persona boundary_behavior (admit, bluff, deflect, ask_back, analogize) and tone.
4. Unlisted topics: falls back to persona.default_level.
"""
from __future__ import annotations

import logging
import pathlib
import time
from typing import Any
from pydantic import BaseModel

from ..schemas.models import (
    KnowledgeConfig,
    KLPersona,
    Level,
    ResponseMode,
    Tone,
    BoundaryBehavior,
)
from ..schemas.helpers import level_diff, get_level
from ..schemas.constants import LEVEL_ORDER
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


class ClassificationResult(BaseModel):
    domains: list[str]
    primary_domain: str
    required_level: Level
    via_lexicon: bool
    latency_ms: float


class RouterResult(BaseModel):
    classification: ClassificationResult
    persona_level: Level
    response_mode: ResponseMode
    diff: int


class MessageRouter:
    """Classifies incoming messages and selects the persona response mode."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._jinja_env = None

    def _get_jinja_env(self):
        if self._jinja_env is None:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(_PROMPTS_DIR)),
                autoescape=select_autoescape(enabled_extensions=()),
            )
        return self._jinja_env

    def _lexicon_prepass(
        self, message: str, knowledge_config: KnowledgeConfig
    ) -> tuple[str | None, Level | None]:
        """Scan message against concept_lexicon.

        Returns (primary_domain, required_level) of highest min_level match found,
        or (None, None).
        """
        msg_lower = message.lower()
        best_domain: str | None = None
        best_level: Level | None = None

        for term, entry in knowledge_config.concept_lexicon.items():
            if term in msg_lower:
                if best_level is None or LEVEL_ORDER[entry.min_level] > LEVEL_ORDER[best_level]:
                    best_level = entry.min_level
                    best_domain = entry.domain

        return best_domain, best_level

    def _classify_via_llm(self, message: str) -> tuple[list[str], str, Level]:
        """Call LLM classifier."""
        env = self._get_jinja_env()
        template = env.get_template("router_classify.jinja2")
        prompt = template.render(message=message)
        messages = [{"role": "user", "content": prompt}]

        class _RouterLLMOutput(BaseModel):
            domains: list[str]
            required_level: Level
            primary_domain: str

        result = self._llm.complete_structured(
            messages=messages,
            output_schema=_RouterLLMOutput,
        )
        return result.domains, result.primary_domain, result.required_level

    def classify(self, message: str, knowledge_config: KnowledgeConfig) -> ClassificationResult:
        """Classify message via lexicon pre-pass or LLM."""
        t0 = time.monotonic()

        lex_domain, lex_level = self._lexicon_prepass(message, knowledge_config)
        if lex_domain is not None and lex_level is not None:
            # Lexicon match: use directly for short messages or as fast shortcut
            via_lexicon = len(message.strip()) < 80
            if via_lexicon:
                elapsed = (time.monotonic() - t0) * 1000
                return ClassificationResult(
                    domains=[lex_domain],
                    primary_domain=lex_domain,
                    required_level=lex_level,
                    via_lexicon=True,
                    latency_ms=round(elapsed, 2),
                )

        # Fallback to LLM
        try:
            domains, primary_domain, required_level = self._classify_via_llm(message)
            via_lex = False
        except Exception as exc:
            logger.warning("LLM classification failed (%s), falling back to lexicon or layperson", exc)
            domains = [lex_domain] if lex_domain else ["general"]
            primary_domain = lex_domain or "general"
            required_level = lex_level or Level.layperson
            via_lex = lex_domain is not None

        elapsed = (time.monotonic() - t0) * 1000
        return ClassificationResult(
            domains=domains,
            primary_domain=primary_domain,
            required_level=required_level,
            via_lexicon=via_lex,
            latency_ms=round(elapsed, 2),
        )

    def route(
        self,
        message: str,
        persona: KLPersona,
        knowledge_config: KnowledgeConfig,
        tone: Tone = Tone.discussion,
    ) -> RouterResult:
        """Full route pipeline: classify, compare level, pick ResponseMode."""
        classification = self.classify(message, knowledge_config)
        persona_level = get_level(persona, knowledge_config, classification.primary_domain)
        diff = level_diff(persona_level, classification.required_level)
        behavior = persona.personality.boundary_behavior

        if diff >= 0:
            mode = ResponseMode.understands
        elif diff == -1:
            mode = ResponseMode.partial
        else:
            # diff <= -2 (lost territory)
            if behavior == BoundaryBehavior.analogize and persona.own_domain:
                mode = ResponseMode.analogizes
            elif behavior == BoundaryBehavior.bluff:
                mode = ResponseMode.partial if tone in (Tone.debate, Tone.discussion) else ResponseMode.lost
            elif behavior == BoundaryBehavior.deflect:
                mode = ResponseMode.partial
            elif behavior == BoundaryBehavior.ask_back:
                mode = ResponseMode.lost  # will ask a clarification question in lost mode
            else:
                mode = ResponseMode.lost

        return RouterResult(
            classification=classification,
            persona_level=persona_level,
            response_mode=mode,
            diff=diff,
        )
