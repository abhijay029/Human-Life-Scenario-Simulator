"""Pydantic-settings configuration for the Knowledge Limiter module."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings for the Knowledge Limiter."""

    # LLM model identifiers
    FAST_MODEL: str = "gemini-2.5-flash"
    MAIN_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEYS: str = ""  # Comma-separated list for multi-key rotation

    # Ollama fallback
    ENGINE_MODEL: str = "qwen2.5:3b"

    # Caching
    TOPIC_CACHE_DIR: str = ".cache/kl_topics"
    BRIEF_CACHE_DIR: str = ".cache/kl_briefs"
    BRIEF_CACHE_TTL_HOURS: int = 168  # web-sourced facts go stale; re-research after a week

    # Feature flags
    ENABLE_CONCEPT_LEARNING: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def get_gemini_keys(self) -> list[str]:
        """Return list of all configured Gemini API keys for rotation."""
        keys: list[str] = []
        if self.GEMINI_API_KEYS:
            keys.extend([k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()])
        if self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip() not in keys:
            keys.append(self.GEMINI_API_KEY.strip())
        return keys


# Module-level singleton — import this in other modules.
settings = Settings()


def get_gemini_keys(settings_obj: Settings | None = None) -> list[str]:
    """Module-level helper to return all configured Gemini API keys."""
    cfg = settings_obj or settings
    return cfg.get_gemini_keys()

