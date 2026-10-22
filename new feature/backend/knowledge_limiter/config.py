"""Pydantic-settings configuration for the Knowledge Limiter module."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings for the Knowledge Limiter."""

    # LLM model identifiers
    FAST_MODEL: str = "qwen2.5:3b"
    MAIN_MODEL: str = "qwen2.5:3b"

    # Ollama fallback
    ENGINE_MODEL: str = "qwen2.5:3b"

    # Caching
    TOPIC_CACHE_DIR: str = ".cache/kl_topics"
    BRIEF_CACHE_DIR: str = ".cache/kl_briefs"
    BRIEF_CACHE_TTL_HOURS: int = 168  # web-sourced facts go stale; re-research after a week

    # Feature flags
    ENABLE_CONCEPT_LEARNING: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Module-level singleton — import this in other modules.
settings = Settings()
