"""Unit tests for LLMClient multi-key rotation and Ollama fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel

from backend.knowledge_limiter.llm_client import (
    LLMClient,
    _is_quota_or_rate_limit_error,
)


class DummySchema(BaseModel):
    message: str
    score: float = 0.0


def test_is_quota_or_rate_limit_error():
    assert _is_quota_or_rate_limit_error(Exception("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert _is_quota_or_rate_limit_error(Exception("Rate limit exceeded for requests"))
    assert _is_quota_or_rate_limit_error(Exception("403 API_KEY_INVALID"))
    assert not _is_quota_or_rate_limit_error(Exception("SyntaxError in user code"))


@patch("backend.knowledge_limiter.llm_client._build_gemini_llm")
@patch("backend.knowledge_limiter.llm_client.get_gemini_keys")
def test_complete_key_rotation_on_429(mock_get_keys, mock_build_gemini):
    mock_get_keys.return_value = ["key_1", "key_2"]

    # First key fails with 429, second key succeeds
    mock_llm_1 = MagicMock()
    mock_llm_1.invoke.side_effect = Exception("429 RESOURCE_EXHAUSTED quota exceeded")

    mock_llm_2 = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Success from key 2"
    mock_llm_2.invoke.return_value = mock_response

    mock_build_gemini.side_effect = [mock_llm_1, mock_llm_2]

    client = LLMClient()
    result = client.complete([{"role": "user", "content": "hi"}])

    assert result == "Success from key 2"
    assert mock_build_gemini.call_count == 2


@patch("backend.knowledge_limiter.llm_client._complete_via_ollama")
@patch("backend.knowledge_limiter.llm_client._build_gemini_llm")
@patch("backend.knowledge_limiter.llm_client.get_gemini_keys")
def test_complete_falls_back_to_ollama_when_all_gemini_keys_fail(
    mock_get_keys, mock_build_gemini, mock_ollama
):
    mock_get_keys.return_value = ["key_1"]
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("429 RESOURCE_EXHAUSTED quota exceeded")
    mock_build_gemini.return_value = mock_llm
    mock_ollama.return_value = "Success from Ollama fallback"

    client = LLMClient()
    result = client.complete([{"role": "user", "content": "hi"}])

    assert result == "Success from Ollama fallback"
    mock_ollama.assert_called_once()


@patch("backend.knowledge_limiter.llm_client._complete_structured_via_ollama")
@patch("backend.knowledge_limiter.llm_client._build_gemini_llm")
@patch("backend.knowledge_limiter.llm_client.get_gemini_keys")
def test_complete_structured_falls_back_to_ollama(
    mock_get_keys, mock_build_gemini, mock_ollama_struct
):
    mock_get_keys.return_value = ["key_1"]
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    mock_llm.with_structured_output.return_value = mock_structured
    mock_build_gemini.return_value = mock_llm

    expected = DummySchema(message="Parsed by Ollama", score=9.5)
    mock_ollama_struct.return_value = expected

    client = LLMClient()
    result = client.complete_structured(
        [{"role": "user", "content": "test"}],
        output_schema=DummySchema,
    )

    assert result == expected
    mock_ollama_struct.assert_called_once()
