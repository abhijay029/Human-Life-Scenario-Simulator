"""
Persona Generation for the Knowledge Limiter module.

Builds prompt incorporating:
- Persona identity & personality
- Positive knowledge description (what they DO know, per domain)
- Scenario & tone
- Response mode instruction for this turn
- Conversation history
"""
from __future__ import annotations

import logging
import pathlib
import time
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..schemas.models import KLPersona, KnowledgeConfig, ResponseMode, Tone
from ..llm_client import LLMClient
from ..config import settings
from .response_mode_instructions import get_response_mode_instruction

logger = logging.getLogger(__name__)

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"
HISTORY_WINDOW = 6


class ConversationTurn:
    def __init__(self, speaker: str, message: str) -> None:
        self.speaker = speaker
        self.message = message


class PersonaGenerationResult:
    def __init__(self, reply: str, prompt_used: str, latency_ms: float) -> None:
        self.reply = reply
        self.prompt_used = prompt_used
        self.latency_ms = latency_ms


class PersonaGenerator:
    """Generates in-character responses gated by persona knowledge."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),
        )

    def _build_knowledge_description(
        self, persona: KLPersona, knowledge_config: KnowledgeConfig
    ) -> str:
        domain_levels: dict[str, str] = {}
        persona_domains = knowledge_config.per_persona.get(persona.id, {})
        for domain, level in persona_domains.items():
            domain_levels[domain] = level.value

        if persona.own_domain and persona.own_domain not in domain_levels:
            domain_levels[persona.own_domain] = "expert"

        template = self._jinja_env.get_template("knowledge_description.jinja2")
        return template.render(
            domain_levels=domain_levels,
            unlisted_note=True,
        )

    def _build_history(self, history: list[ConversationTurn]) -> str:
        window = history[-HISTORY_WINDOW:]
        return (
            "\n".join(f"{t.speaker}: {t.message}" for t in window)
            if window
            else "(conversation just started)"
        )

    def generate(
        self,
        persona: KLPersona,
        knowledge_config: KnowledgeConfig,
        scenario_description: str,
        tone: Tone,
        response_mode: ResponseMode,
        history: list[ConversationTurn],
        model: Optional[str] = None,
    ) -> PersonaGenerationResult:
        t0 = time.monotonic()

        knowledge_desc = self._build_knowledge_description(persona, knowledge_config)
        mode_instruction = get_response_mode_instruction(response_mode, persona.own_domain)
        history_text = self._build_history(history)

        template = self._jinja_env.get_template("persona_speak.jinja2")
        prompt = template.render(
            persona=persona,
            knowledge_description=knowledge_desc,
            scenario_description=scenario_description,
            tone=tone.value,
            response_mode_instruction=mode_instruction,
            conversation_history=history_text,
        )

        messages = [{"role": "user", "content": prompt}]
        effective_model = model or settings.MAIN_MODEL
        reply = self._llm.complete(messages, model=effective_model)
        reply = reply.strip()

        elapsed = (time.monotonic() - t0) * 1000
        return PersonaGenerationResult(
            reply=reply, prompt_used=prompt, latency_ms=round(elapsed, 2)
        )
