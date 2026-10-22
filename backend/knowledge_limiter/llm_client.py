"""Shared Ollama LLM client for the Knowledge Limiter and Observer modules."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from backend.core.llm import get_evaluator

logger = logging.getLogger(__name__)

_ollama_llm = get_evaluator()


def _messages_to_lc(messages: list[dict[str, str]]) -> list[Any]:
    """Convert role/content dictionaries into LangChain message objects."""
    from langchain_core.messages import HumanMessage, SystemMessage

    result: list[Any] = []
    for message in messages:
        if message.get("role", "user") == "system":
            result.append(SystemMessage(content=message.get("content", "")))
        else:
            result.append(HumanMessage(content=message.get("content", "")))
    return result


def _complete_via_ollama(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> str:
    """Complete a prompt using the shared Ollama evaluator instance."""
    logger.info("Executing completion via shared Ollama evaluator")
    response = _ollama_llm.invoke(_messages_to_lc(messages))
    return str(response.content)


def _complete_structured_via_ollama(
    messages: list[dict[str, str]],
    output_schema: type[BaseModel],
    temperature: float = 0.0,
) -> BaseModel:
    """Complete a structured prompt using the shared Ollama evaluator instance."""
    logger.info("Executing structured completion via shared Ollama evaluator")
    structured_llm = _ollama_llm.with_structured_output(output_schema)
    return structured_llm.invoke(_messages_to_lc(messages))


class GroundedResult(BaseModel):
    """Completion result with optional supporting sources."""

    text: str
    sources: list[dict[str, str]] = []
    grounded: bool = False


class LLMClient:
    """Provider-neutral interface backed exclusively by the shared Ollama model."""

    def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        return _complete_via_ollama(
            messages,
            temperature=0.2 if temperature is None else temperature,
        )

    def complete_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        return _complete_structured_via_ollama(
            messages,
            output_schema,
            temperature=0.0 if temperature is None else temperature,
        )

    def complete_grounded(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> GroundedResult:
        """Complete locally; Ollama does not provide web-grounding metadata."""
        return GroundedResult(
            text=self.complete(messages, model=model, temperature=temperature),
            sources=[],
            grounded=False,
        )
