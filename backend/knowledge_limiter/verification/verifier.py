"""
Output verification for Knowledge Limiter.

Two layers:
1. Deterministic lexicon scan: check if reply uses terms above persona's level.
   Allows echoed terms the other speaker just used when phrased as question/clarification.
2. LLM verifier (small model): runs only when out-of-domain and lexicon check is inconclusive.

Also monitors over-restriction (persona pretending ignorance of things within its level).
"""
from __future__ import annotations

import logging
import pathlib
import time
from typing import Optional
from pydantic import BaseModel

from ..schemas.models import KLPersona, KnowledgeConfig, ResponseMode
from ..schemas.helpers import get_level
from ..schemas.constants import LEVEL_ORDER
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


class LexiconViolation(BaseModel):
    term: str
    domain: str
    required_level: str
    persona_level: str


class VerificationResult(BaseModel):
    passed: bool
    violations: list[LexiconViolation] = []
    llm_violation: bool = False
    llm_span: str = ""
    llm_reason: str = ""
    latency_ms: float = 0.0
    over_restriction_warning: bool = False


class OutputVerifier:
    """Verifies generated responses against persona knowledge boundaries."""

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

    def _is_echoed_term(self, term: str, last_message: str) -> bool:
        """Allow term if other speaker just used it."""
        if not last_message:
            return False
        return term.lower() in last_message.lower()

    def lexicon_check(
        self,
        reply: str,
        persona: KLPersona,
        knowledge_config: KnowledgeConfig,
        last_message: str = "",
    ) -> list[LexiconViolation]:
        """Scan reply for concept terms above persona's level."""
        violations: list[LexiconViolation] = []
        reply_lower = reply.lower()

        for term, entry in knowledge_config.concept_lexicon.items():
            if term not in reply_lower:
                continue

            # Allow if echoed from last speaker's message
            if self._is_echoed_term(term, last_message):
                continue

            persona_level = get_level(persona, knowledge_config, entry.domain)
            if LEVEL_ORDER[persona_level] < LEVEL_ORDER[entry.min_level]:
                violations.append(
                    LexiconViolation(
                        term=term,
                        domain=entry.domain,
                        required_level=entry.min_level.value,
                        persona_level=persona_level.value,
                    )
                )

        return violations

    def llm_verify(
        self,
        reply: str,
        persona: KLPersona,
        knowledge_config: KnowledgeConfig,
        last_message: str = "",
    ) -> tuple[bool, str, str]:
        """Run LLM verifier. Returns (violation, span, reason)."""
        persona_domains = knowledge_config.per_persona.get(persona.id, {})
        knowledge_summary = "; ".join(
            f"{domain}={level.value}" for domain, level in persona_domains.items()
        ) or f"default={persona.default_level.value}"

        env = self._get_jinja_env()
        template = env.get_template("verifier.jinja2")
        prompt = template.render(
            persona=persona,
            knowledge_summary=knowledge_summary,
            reply=reply,
            last_message=last_message,
        )
        messages = [{"role": "user", "content": prompt}]

        class _VerifierOutput(BaseModel):
            violation: bool
            span: str = ""
            reason: str = ""

        try:
            result = self._llm.complete_structured(
                messages=messages,
                output_schema=_VerifierOutput,
            )
            return result.violation, result.span, result.reason
        except Exception as exc:
            logger.warning("LLM verifier failed: %s", exc)
            return False, "", ""

    def verify(
        self,
        reply: str,
        persona: KLPersona,
        knowledge_config: KnowledgeConfig,
        response_mode: ResponseMode,
        last_message: str = "",
        run_llm_verifier: bool = False,
    ) -> VerificationResult:
        """Execute output verification pipeline."""
        t0 = time.monotonic()

        violations = self.lexicon_check(reply, persona, knowledge_config, last_message)

        # Over-restriction check
        over_restriction = False
        if response_mode == ResponseMode.understands and len(reply.strip()) < 15:
            logger.warning(
                "[over-restriction] Persona %s gave unexpectedly empty reply in 'understands' mode: %r",
                persona.name,
                reply,
            )
            over_restriction = True

        llm_violation = False
        llm_span = ""
        llm_reason = ""

        # Run LLM verifier only if requested and lexicon check didn't already catch violations
        if run_llm_verifier and not violations:
            llm_violation, llm_span, llm_reason = self.llm_verify(
                reply, persona, knowledge_config, last_message
            )

        passed = len(violations) == 0 and not llm_violation
        elapsed = (time.monotonic() - t0) * 1000

        return VerificationResult(
            passed=passed,
            violations=violations,
            llm_violation=llm_violation,
            llm_span=llm_span,
            llm_reason=llm_reason,
            latency_ms=round(elapsed, 2),
            over_restriction_warning=over_restriction,
        )
