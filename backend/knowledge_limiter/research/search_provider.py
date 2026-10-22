"""Search-provider abstraction used by Knowledge Limiter research."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Return relevant, source-backed search results for a query."""


class TavilySearchProvider:
    """Tavily-backed search provider using the standard-library HTTP client."""

    endpoint = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        if not api_key.strip():
            raise ValueError("TAVILY_API_KEY is required when SEARCH_PROVIDER=tavily")
        self._api_key = api_key.strip()
        self._timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        payload = json.dumps(
            {
                "api_key": self._api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": max(1, min(max_results, 10)),
                "include_answer": False,
                "include_raw_content": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = json.load(response)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise RuntimeError(f"Tavily search failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Tavily returned invalid JSON") from exc

        results: list[SearchResult] = []
        for item in data.get("results", []):
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            results.append(
                SearchResult(
                    title=str(item.get("title", "")).strip() or url,
                    url=url,
                    content=content,
                )
            )
        return results


def build_search_provider() -> SearchProvider | None:
    """Build the configured provider, or disable research when none is configured."""
    provider = settings.SEARCH_PROVIDER.strip().lower()
    if provider in {"", "none", "disabled"}:
        return None
    if provider == "tavily":
        return TavilySearchProvider(
            settings.TAVILY_API_KEY,
            timeout=settings.SEARCH_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Unsupported SEARCH_PROVIDER: {settings.SEARCH_PROVIDER}")
