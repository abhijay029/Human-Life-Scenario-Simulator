"""
Expert-brief generation for the Knowledge Limiter.

For each selected objective subject area, a web-search-grounded call gathers
level-tagged facts directly. A structured extraction call is used only if the
grounded response cannot be parsed as the required JSON.

The research prompt contains ONLY the topic name, domain and key concepts — never the
scenario text or persona details — so personal scenarios are not sent to search.
Facts across all knowledge levels are returned to the user for review; at chat time they are gated by persona level
(see ``schemas.helpers.select_brief_facts``).
"""
from __future__ import annotations

import hashlib
import logging
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from ..config import settings
from ..llm_client import LLMClient
from ..schemas.models import BriefFact, BriefSource, Level, Topic, TopicBrief
from .search_provider import SearchProvider, build_search_provider

logger = logging.getLogger(__name__)

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"

MAX_RESEARCHED_TOPICS = 12
MAX_FACTS_PER_TOPIC = 8
MIN_FACT_CHARS = 15
MAX_FACT_CHARS = 300
MAX_WORKERS = 3
WEB_RESEARCH_LEVELS = {Level.advanced, Level.expert}


class _RawFact(BaseModel):
    text: str
    min_level: Level


class _RawBriefOutput(BaseModel):
    facts: list[_RawFact]


class BriefGenerationResult(BaseModel):
    briefs: dict[str, TopicBrief] = {}   # topic_id -> brief
    errors: dict[str, str] = {}          # topic_id -> reason it could not be researched
    skipped: list[str] = []              # topic ids beyond the research cap


def _clean_facts(raw: list[_RawFact]) -> list[BriefFact]:
    """Keep only sourced facts intended for advanced or expert personas."""
    facts: list[BriefFact] = []
    seen: set[str] = set()
    for item in raw:
        if item.min_level not in WEB_RESEARCH_LEVELS:
            continue
        text = " ".join(item.text.split())
        if not (MIN_FACT_CHARS <= len(text) <= MAX_FACT_CHARS):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        facts.append(BriefFact(text=text, min_level=item.min_level))
        if len(facts) >= MAX_FACTS_PER_TOPIC:
            break
    return facts


class BriefGenerator:
    """Researches and caches expert briefs for topics."""

    def __init__(
        self,
        llm_client: LLMClient,
        search_provider: SearchProvider | None = None,
    ) -> None:
        self._llm = llm_client
        self._search_provider = search_provider if search_provider is not None else build_search_provider()
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),
        )

    # ------------------------------------------------------------------ cache

    @staticmethod
    def _cache_key(topic: Topic) -> str:
        concepts = ",".join(sorted(c.term.strip().lower() for c in topic.concepts))
        raw = f"knowledge-brief-v3|{topic.name.strip().lower()}|{topic.domain.strip().lower()}|{concepts}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _cache_path(key: str) -> pathlib.Path:
        cache_dir = pathlib.Path(settings.BRIEF_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{key}.json"

    def _load_cache(self, key: str) -> Optional[TopicBrief]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours > settings.BRIEF_CACHE_TTL_HOURS:
            return None
        try:
            return TopicBrief.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ignoring unreadable brief cache %s: %s", path, exc)
            return None

    def _save_cache(self, key: str, brief: TopicBrief) -> None:
        try:
            self._cache_path(key).write_text(brief.model_dump_json(indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to cache brief: %s", exc)

    # --------------------------------------------------------------- research

    def _research_topic(self, topic: Topic) -> TopicBrief:
        if self._search_provider is None:
            raise ValueError(
                "No search provider configured; set SEARCH_PROVIDER=tavily and TAVILY_API_KEY"
            )

        concepts = [c.term for c in topic.concepts]
        query = " ".join([topic.name, topic.domain, *concepts]).strip()
        search_results = self._search_provider.search(
            query,
            max_results=settings.SEARCH_MAX_RESULTS,
        )
        if not search_results:
            raise ValueError("Search returned no usable sources; no facts were added")

        notes = "\n\n".join(
            f"SOURCE: {result.title}\nURL: {result.url}\n{result.content}"
            for result in search_results
        )
        extract_prompt = self._jinja_env.get_template("brief_extract.jinja2").render(
            name=topic.name, domain=topic.domain, notes=notes
        )
        extracted = self._llm.complete_structured(
            [{"role": "user", "content": extract_prompt}],
            output_schema=_RawBriefOutput,
            model=settings.FAST_MODEL,
        )
        facts = _clean_facts(extracted.facts)
        if not facts:
            raise ValueError("No usable facts were extracted")

        return TopicBrief(
            facts=facts,
            sources=[BriefSource(title=result.title, url=result.url) for result in search_results],
            grounded=True,
        )

    # -------------------------------------------------------------- public API

    def generate(self, topics: list[Topic]) -> BriefGenerationResult:
        """Research topics that have at least one advanced or expert persona."""
        eligible = [
            topic for topic in topics
            if any(level in WEB_RESEARCH_LEVELS for level in topic.levels.values())
        ]
        chosen = eligible[:MAX_RESEARCHED_TOPICS]
        chosen_ids = {t.id for t in chosen}
        result = BriefGenerationResult(skipped=[t.id for t in eligible if t.id not in chosen_ids])

        to_research: list[Topic] = []
        for topic in chosen:
            cached = self._load_cache(self._cache_key(topic))
            if cached is not None:
                result.briefs[topic.id] = cached
            else:
                to_research.append(topic)

        def _work(topic: Topic) -> tuple[str, TopicBrief | None, str]:
            try:
                return topic.id, self._research_topic(topic), ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("Brief research failed for %s: %s", topic.id, exc)
                return topic.id, None, str(exc)

        if to_research:
            by_id = {t.id: t for t in to_research}
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(to_research))) as pool:
                for topic_id, brief, err in pool.map(_work, to_research):
                    if brief is not None:
                        result.briefs[topic_id] = brief
                        # Only cache web-backed briefs; ungrounded ones should be retried later.
                        if brief.grounded:
                            self._save_cache(self._cache_key(by_id[topic_id]), brief)
                    else:
                        result.errors[topic_id] = err

        return result
