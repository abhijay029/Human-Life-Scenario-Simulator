"""Topic Generation for the Knowledge Limiter module.

Generates a list of :class:`~backend.knowledge_limiter.schemas.models.Topic`
objects for a given :class:`TopicGenerationInput` by rendering a Jinja2 prompt
and calling the LLM client with structured output.

Caching is file-system based: results are serialised as JSON under
``settings.TOPIC_CACHE_DIR``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ValidationError

from ..config import settings
from ..llm_client import LLMClient
from ..schemas.models import Concept, Level, Tone, Topic

logger = logging.getLogger(__name__)

# Path to the directory containing Jinja2 templates.
_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class KLPersonaInput(BaseModel):
    """Minimal persona representation used as topic-generation input."""

    name: str
    profession: str
    background_summary: str


class TopicGenerationInput(BaseModel):
    """All information needed to generate topics for a scenario."""

    scenario_description: str
    tone: Tone
    personas: list[KLPersonaInput]
    # The decision point (single run) or decision branches (multiverse) the
    # user wants to explore. They steer where the conversation is headed, so
    # they are part of the context topics are generated from.
    decision_points: list[str] = []


class TopicGenerationOutput(BaseModel):
    """The structured result of topic generation."""

    topics: list[Topic]


# ---------------------------------------------------------------------------
# Internal LLM response schema (mirrors the JSON the LLM returns)
# ---------------------------------------------------------------------------


class _RawConcept(BaseModel):
    term: str
    min_level: Level


class _RawTopic(BaseModel):
    id: str
    name: str
    domain: str
    concepts: list[_RawConcept]
    suggested_levels: dict[str, Level]


class _RawTopicGenerationOutput(BaseModel):
    topics: list[_RawTopic]


# ---------------------------------------------------------------------------
# TopicGenerator
# ---------------------------------------------------------------------------


class TopicGenerator:
    """Generates conversation topics for a scenario using an LLM.

    Caches results on disk to avoid redundant API calls.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),
        )

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, inp: TopicGenerationInput) -> str:
        """Generate a deterministic SHA-256 cache key for *inp*.

        The key is derived from:
        - ``scenario_description``
        - ``tone``
        - Sorted list of ``profession`` strings from personas.
        - Sorted, non-empty ``decision_points`` (only appended when present, so
          keys for inputs without decision points are unchanged).
        """
        sorted_professions = sorted(p.profession for p in inp.personas)
        # Bump this namespace when topic semantics change so older cached
        # scenario themes cannot bypass the objective-subjects prompt.
        raw = f"objective-subjects-v2|{inp.scenario_description}|{inp.tone.value}|{','.join(sorted_professions)}"
        decisions = sorted(d.strip() for d in inp.decision_points if d.strip())
        if decisions:
            raw += "|" + "||".join(decisions)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, key: str) -> pathlib.Path:
        cache_dir = pathlib.Path(settings.TOPIC_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{key}.json"

    def _load_cache(self, key: str) -> TopicGenerationOutput | None:
        """Return a cached result if it exists, else ``None``."""
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TopicGenerationOutput.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load cache at %s: %s", path, exc)
            return None

    def _save_cache(self, key: str, result: TopicGenerationOutput) -> None:
        """Persist *result* to the cache directory as JSON."""
        path = self._cache_path(key)
        try:
            path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save cache at %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Prompt rendering
    # ------------------------------------------------------------------

    def _render_prompt(self, inp: TopicGenerationInput) -> str:
        template = self._jinja_env.get_template("topic_generation.jinja2")
        return template.render(
            scenario_description=inp.scenario_description,
            tone=inp.tone.value,
            personas=inp.personas,
            decision_points=[d.strip() for d in inp.decision_points if d.strip()],
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_raw(self, raw_json: str, inp: TopicGenerationInput) -> TopicGenerationOutput:
        """Parse a raw JSON string from the LLM into a :class:`TopicGenerationOutput`.

        The ``suggested_levels`` dict (keyed by persona *name*) is converted to
        the ``levels`` dict on each :class:`Topic` (also keyed by persona name,
        used as a stand-in persona ID when full IDs are not available at this stage).

        Raises:
            ValueError: If *raw_json* is not valid JSON or cannot be parsed into
                        the expected schema.
        """
        try:
            data: Any = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

        try:
            raw_output = _RawTopicGenerationOutput.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"LLM JSON did not match expected schema: {exc}") from exc

        topics: list[Topic] = []
        for raw_topic in raw_output.topics:
            levels: dict[str, Level] = dict(raw_topic.suggested_levels)
            topic = Topic(
                id=raw_topic.id,
                name=raw_topic.name,
                domain=raw_topic.domain,
                concepts=[
                    Concept(term=c.term, min_level=c.min_level)
                    for c in raw_topic.concepts
                ],
                levels=levels,
            )
            topics.append(topic)

        return TopicGenerationOutput(topics=topics)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, inp: TopicGenerationInput) -> TopicGenerationOutput:
        """Generate topics for *inp*, using the cache when available.

        On an LLM validation failure the call is retried once with the same
        prompt before re-raising.

        Args:
            inp: The scenario description, tone, and personas.

        Returns:
            A :class:`TopicGenerationOutput` with a list of :class:`Topic` objects.
        """
        key = self._cache_key(inp)

        cached = self._load_cache(key)
        if cached is not None:
            logger.debug("Cache hit for key %s", key)
            return cached

        prompt = self._render_prompt(inp)
        messages = [{"role": "user", "content": prompt}]

        # Attempt with structured output (one retry on failure).
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                raw_output: _RawTopicGenerationOutput = self._llm.complete_structured(  # type: ignore[assignment]
                    messages=messages,
                    output_schema=_RawTopicGenerationOutput,
                )
                # Convert _RawTopicGenerationOutput → TopicGenerationOutput
                topics: list[Topic] = []
                for raw_topic in raw_output.topics:
                    topic = Topic(
                        id=raw_topic.id,
                        name=raw_topic.name,
                        domain=raw_topic.domain,
                        concepts=[
                            Concept(term=c.term, min_level=c.min_level)
                            for c in raw_topic.concepts
                        ],
                        levels=dict(raw_topic.suggested_levels),
                    )
                    topics.append(topic)
                result = TopicGenerationOutput(topics=topics)
                self._save_cache(key, result)
                return result
            except Exception as exc:
                last_exc = exc
                logger.warning("Attempt %d failed: %s — retrying…", attempt + 1, exc)

        # Fallback to rich scenario-tailored heuristic topics if LLM calls fail (e.g. quota limit)
        logger.warning(
            "LLM topic generation failed (%s). Falling back to dynamic heuristic generator.",
            last_exc,
        )
        result = self._fallback_heuristic_topics(inp)
        self._save_cache(key, result)
        return result

    def _fallback_heuristic_topics(self, inp: TopicGenerationInput) -> TopicGenerationOutput:
        """Dynamically generate tailored topics based on persona professions and scenario text."""
        topics: list[Topic] = []
        combined_text = (
            f"{inp.scenario_description} "
            + " ".join(inp.decision_points)
            + " "
            + " ".join(f"{p.name} {p.profession} {p.background_summary}" for p in inp.personas)
        ).lower()

        # Check domain presence
        has_ai = any(w in combined_text for w in ["ai", "machine learning", "ml", "engineer", "software", "model", "deep learning"])
        has_med = any(w in combined_text for w in ["doctor", "cardiologist", "medical", "patient", "clinic", "health", "hospital"])
        has_biz = any(w in combined_text for w in ["business", "manager", "firm", "corporate", "money", "finance", "deal"])
        has_music = any(w in combined_text for w in ["music", "creative", "artist", "production", "song", "track"])
        has_ethics = any(w in combined_text for w in ["ethics", "privacy", "bias", "safety", "trust", "moral", "regulation"])

        def is_expert(p: KLPersonaInput, domain: str) -> Level:
            p_text = f"{p.profession} {p.background_summary}".lower()
            if domain == "artificial_intelligence" and any(w in p_text for w in ["ai", "ml", "engineer", "data scientist", "software"]):
                return Level.expert
            if domain == "medicine" and any(w in p_text for w in ["doctor", "cardiologist", "physician", "surgeon", "nurse"]):
                return Level.expert
            if domain == "business" and any(w in p_text for w in ["manager", "executive", "director", "founder"]):
                return Level.advanced
            if domain == "music" and any(w in p_text for w in ["music", "producer", "artist", "singer"]):
                return Level.expert
            return Level.layperson

        # AI Topics
        if has_ai:
            topics.append(
                Topic(
                    id="topic_ai_architectures",
                    name="Deep Learning & Neural Architectures",
                    domain="artificial_intelligence",
                    concepts=[
                        Concept(term="neural network", min_level=Level.basic),
                        Concept(term="transformer architecture", min_level=Level.advanced),
                        Concept(term="backpropagation", min_level=Level.advanced),
                        Concept(term="LoRA fine-tuning", min_level=Level.expert),
                    ],
                    levels={p.name: is_expert(p, "artificial_intelligence") for p in inp.personas},
                )
            )
            topics.append(
                Topic(
                    id="topic_ai_diagnostics",
                    name="AI in Diagnostic Automation",
                    domain="artificial_intelligence",
                    concepts=[
                        Concept(term="AI chatbot", min_level=Level.layperson),
                        Concept(term="pattern recognition", min_level=Level.basic),
                        Concept(term="inference latency", min_level=Level.advanced),
                        Concept(term="out-of-distribution generalization", min_level=Level.expert),
                    ],
                    levels={p.name: (Level.basic if is_expert(p, "medicine") == Level.expert else is_expert(p, "artificial_intelligence")) for p in inp.personas},
                )
            )

        # Medicine Topics
        if has_med:
            topics.append(
                Topic(
                    id="topic_clinical_cardiology",
                    name="Clinical Diagnostics & Cardiology",
                    domain="medicine",
                    concepts=[
                        Concept(term="blood pressure", min_level=Level.layperson),
                        Concept(term="echocardiogram", min_level=Level.basic),
                        Concept(term="myocardial infarction", min_level=Level.advanced),
                        Concept(term="hemodynamic monitoring", min_level=Level.expert),
                    ],
                    levels={p.name: is_expert(p, "medicine") for p in inp.personas},
                )
            )
            topics.append(
                Topic(
                    id="topic_medical_imaging",
                    name="Medical Imaging & Protocols",
                    domain="medicine",
                    concepts=[
                        Concept(term="ultrasound", min_level=Level.layperson),
                        Concept(term="MRI protocol", min_level=Level.advanced),
                        Concept(term="CT angiography", min_level=Level.advanced),
                        Concept(term="artifact suppression", min_level=Level.expert),
                    ],
                    levels={p.name: is_expert(p, "medicine") for p in inp.personas},
                )
            )

        # Music Topics
        if has_music:
            topics.append(
                Topic(
                    id="topic_music_production",
                    name="Music Production & Sound Engineering",
                    domain="music",
                    concepts=[
                        Concept(term="song arrangement", min_level=Level.layperson),
                        Concept(term="digital audio workstation", min_level=Level.basic),
                        Concept(term="mastering and mixing", min_level=Level.advanced),
                        Concept(term="compression sidechaining", min_level=Level.expert),
                    ],
                    levels={p.name: is_expert(p, "music") for p in inp.personas},
                )
            )

        # Business & Management Topics
        if has_biz or len(topics) < 4:
            topics.append(
                Topic(
                    id="topic_career_stability",
                    name="Professional Career Trajectory & Risk",
                    domain="business",
                    concepts=[
                        Concept(term="job security", min_level=Level.layperson),
                        Concept(term="contract negotiation", min_level=Level.basic),
                        Concept(term="equity and compensation", min_level=Level.advanced),
                    ],
                    levels={p.name: is_expert(p, "business") for p in inp.personas},
                )
            )

        # Ethics & Compliance Topics
        topics.append(
            Topic(
                id="topic_privacy_regulations",
                name="Patient Privacy & Data Compliance",
                domain="ethics",
                concepts=[
                    Concept(term="confidentiality", min_level=Level.layperson),
                    Concept(term="HIPAA regulations", min_level=Level.basic),
                    Concept(term="de-identification protocols", min_level=Level.advanced),
                ],
                levels={p.name: Level.basic for p in inp.personas},
            )
        )

        topics.append(
            Topic(
                id="topic_decision_making",
                name="Evidence-Based Decision Making",
                domain="methodology",
                concepts=[
                    Concept(term="common sense observation", min_level=Level.layperson),
                    Concept(term="statistical correlation", min_level=Level.basic),
                    Concept(term="randomized controlled trials", min_level=Level.advanced),
                ],
                levels={p.name: (Level.advanced if (is_expert(p, "medicine") == Level.expert or is_expert(p, "artificial_intelligence") == Level.expert) else Level.layperson) for p in inp.personas},
            )
        )

        return TopicGenerationOutput(topics=topics)
