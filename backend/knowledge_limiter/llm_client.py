"""LLM client wrapper for the Knowledge Limiter and Observer modules.

Supports dual-tier execution:
1. Google Gemini via langchain-google-genai with multi-key rotation on 429 quota exhaustion.
2. Local Ollama fallback via langchain-ollama (model: settings.ENGINE_MODEL / qwen2.5:3b)
   providing zero-rate-limit, zero-cost structured & text completions.

langchain packages are imported lazily so that modules can be imported even when
packages are not installed in the current environment (e.g. during offline mocking).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .config import settings, get_gemini_keys

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
    """Return True if exception indicates quota, rate limit (429), or auth exhaustion."""
    err_str = str(exc).lower()
    return any(
        kw in err_str
        for kw in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "ratelimit",
            "exceeded",
            "403",
            "api_key_invalid",
            "invalid_argument",
        )
    )


def _build_gemini_llm(
    model: str,
    api_key: str | None = None,
    temperature: float = 0.2,
) -> "ChatGoogleGenerativeAI":
    """Instantiate a ChatGoogleGenerativeAI with the given model and API key."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "langchain-google-genai is required for Gemini calls. "
            "Install it with: pip install langchain-google-genai"
        ) from exc

    effective_key = api_key or settings.GEMINI_API_KEY or None
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=effective_key,
        temperature=temperature,
        max_retries=0,
    )


def _complete_via_ollama(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> str:
    """Fallback plain-text completion using local Ollama."""
    try:
        from langchain_ollama import ChatOllama  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "langchain-ollama is required for Ollama fallback in LLMClient."
        ) from exc

    logger.info("Executing completion via local Ollama (%s)", settings.ENGINE_MODEL)
    ollama_llm = ChatOllama(
        model=settings.ENGINE_MODEL,
        temperature=temperature,
    )
    lc_msgs = _messages_to_lc(messages)
    response = ollama_llm.invoke(lc_msgs)
    return str(response.content)


def _complete_structured_via_ollama(
    messages: list[dict[str, str]],
    output_schema: type[BaseModel],
    temperature: float = 0.0,
) -> BaseModel:
    """Fallback structured completion using local Ollama."""
    try:
        from langchain_ollama import ChatOllama  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "langchain-ollama is required for Ollama fallback in LLMClient."
        ) from exc

    logger.info("Executing structured completion via local Ollama (%s)", settings.ENGINE_MODEL)
    ollama_llm = ChatOllama(
        model=settings.ENGINE_MODEL,
        temperature=temperature,
    )
    structured_llm = ollama_llm.with_structured_output(output_schema)
    lc_msgs = _messages_to_lc(messages)
    return structured_llm.invoke(lc_msgs)


def _messages_to_lc(messages: list[dict[str, str]]) -> list[Any]:
    """Convert a list of ``{"role": ..., "content": ...}`` dicts to LangChain message objects."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "langchain-core is required for LLMClient."
        ) from exc

    lc_messages: list[Any] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    return lc_messages


class LLMClient:
    """Robust, provider-agnostic wrapper for LLM calls with multi-key rotation and Ollama fallback.

    First attempts Google Gemini using any available configured API keys.
    If 429 quota exhaustion occurs, it rotates through the key pool.
    If all keys are exhausted (or none configured), it transparently falls back
    to local Ollama (qwen2.5:3b), ensuring zero degraded mock fallbacks.
    """

    def __init__(self) -> None:
        self._key_index: int = 0

    def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send *messages* to the LLM and return the plain-text response string."""
        effective_model = model or settings.FAST_MODEL
        eff_temp = 0.2 if temperature is None else temperature
        keys = get_gemini_keys()

        if keys:
            num_keys = len(keys)
            for attempt in range(num_keys):
                idx = (self._key_index + attempt) % num_keys
                key = keys[idx]
                try:
                    llm = _build_gemini_llm(effective_model, api_key=key, temperature=eff_temp)
                    lc_msgs = _messages_to_lc(messages)
                    response = llm.invoke(lc_msgs)
                    self._key_index = idx  # Remember working key
                    return str(response.content)
                except Exception as exc:
                    if _is_quota_or_rate_limit_error(exc) and attempt < num_keys - 1:
                        logger.warning(
                            "Gemini key [%d/%d] exhausted or rate-limited (%s). Rotating to next key...",
                            idx + 1,
                            num_keys,
                            exc,
                        )
                        continue
                    logger.warning(
                        "Gemini call failed with key [%d/%d] (%s). Falling back to local Ollama...",
                        idx + 1,
                        num_keys,
                        exc,
                    )
                    break

        # Fallback to local Ollama
        return _complete_via_ollama(messages, temperature=eff_temp)

    def complete_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Send *messages* and return a validated Pydantic model instance."""
        effective_model = model or settings.FAST_MODEL
        eff_temp = 0.0 if temperature is None else temperature
        keys = get_gemini_keys()

        if keys:
            num_keys = len(keys)
            for attempt in range(num_keys):
                idx = (self._key_index + attempt) % num_keys
                key = keys[idx]
                try:
                    llm = _build_gemini_llm(effective_model, api_key=key, temperature=eff_temp)
                    structured_llm = llm.with_structured_output(output_schema)
                    lc_msgs = _messages_to_lc(messages)
                    result = structured_llm.invoke(lc_msgs)
                    self._key_index = idx  # Remember working key
                    return result  # type: ignore[return-value]
                except Exception as exc:
                    if _is_quota_or_rate_limit_error(exc) and attempt < num_keys - 1:
                        logger.warning(
                            "Gemini key [%d/%d] exhausted or rate-limited (%s). Rotating to next key...",
                            idx + 1,
                            num_keys,
                            exc,
                        )
                        continue
                    logger.warning(
                        "Gemini structured call failed with key [%d/%d] (%s). Falling back to local Ollama...",
                        idx + 1,
                        num_keys,
                        exc,
                    )
                    break

        # Fallback to local Ollama
        return _complete_structured_via_ollama(messages, output_schema, temperature=eff_temp)

