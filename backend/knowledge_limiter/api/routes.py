"""
FastAPI Routes for Knowledge Limiter.

Endpoints:
- POST /kl/topics/generate: returns suggested topics and per-persona levels.
- POST /kl/briefs/generate: researches expert briefs (web-grounded) for advanced/expert topics.
- POST /kl/config/save: compiles confirmed topics and per-persona levels into KnowledgeConfig with flattened concept lexicon.
- POST /kl/chat/{persona_id}: executes full runtime pipeline (router -> generator -> verifier with retry).
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from .schemas import (
    GenerateTopicsRequest,
    GenerateTopicsResponse,
    GenerateBriefsRequest,
    GenerateBriefsResponse,
    SaveConfigRequest,
    SaveConfigResponse,
    KLChatRequest,
    KLChatResponse,
)
from ..schemas.models import (
    BriefFact,
    KnowledgeConfig,
    ConceptLexiconEntry,
    Level,
)
from ..schemas.constants import LEVEL_ORDER
from ..llm_client import LLMClient
from ..topic_generation.generator import TopicGenerator, TopicGenerationInput
from ..research.brief_generator import BriefGenerator
from ..router.classifier import MessageRouter
from ..generation.persona_generator import PersonaGenerator, ConversationTurn
from ..verification.verifier import OutputVerifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kl", tags=["Knowledge Limiter"])

# Shared service instances
_llm_client = LLMClient()
_topic_generator = TopicGenerator(_llm_client)
_brief_generator = BriefGenerator(_llm_client)
_router = MessageRouter(_llm_client)
_generator = PersonaGenerator(_llm_client)
_verifier = OutputVerifier(_llm_client)


@router.post("/topics/generate", response_model=GenerateTopicsResponse)
def generate_topics(req: GenerateTopicsRequest):
    """Generate 8-12 suggested topics with concept min_levels and persona levels."""
    try:
        inp = TopicGenerationInput(
            scenario_description=req.scenario_description,
            tone=req.tone,
            personas=req.personas,
            decision_points=req.decision_points,
        )
        out = _topic_generator.generate(inp)
        return GenerateTopicsResponse(topics=out.topics)
    except Exception as exc:
        logger.exception("Topic generation failed")
        raise HTTPException(status_code=500, detail=f"Topic generation failed: {exc}")


@router.post("/briefs/generate", response_model=GenerateBriefsResponse)
def generate_briefs(req: GenerateBriefsRequest):
    """Research expert briefs for topics where some persona is advanced/expert.

    Only each topic's name, domain and key concepts are used for the web search — never
    the scenario text or persona details.
    """
    try:
        out = _brief_generator.generate(req.topics)
        return GenerateBriefsResponse(briefs=out.briefs, errors=out.errors, skipped=out.skipped)
    except Exception as exc:
        logger.exception("Brief generation failed")
        raise HTTPException(status_code=500, detail=f"Brief generation failed: {exc}")


@router.post("/config/save", response_model=SaveConfigResponse)
def save_knowledge_config(req: SaveConfigRequest):
    """Compile reviewed topics and personas into a final KnowledgeConfig."""
    try:
        per_persona: dict[str, dict[str, Level]] = {p.id: {} for p in req.personas}
        concept_lexicon: dict[str, ConceptLexiconEntry] = {}
        expert_briefs: dict[str, dict[str, BriefFact]] = {}  # domain -> {fact_text_lower: fact}

        for topic in req.topics:
            # Map levels per persona for this domain
            for persona_id, level in topic.levels.items():
                if persona_id not in per_persona:
                    per_persona[persona_id] = {}
                per_persona[persona_id][topic.domain] = level

            # Merge reviewed brief facts by domain (keep the higher level for duplicates)
            if topic.brief and topic.brief.grounded:
                bucket = expert_briefs.setdefault(topic.domain, {})
                for fact in topic.brief.facts:
                    text = fact.text.strip()
                    if not text:
                        continue
                    fkey = text.lower()
                    prev = bucket.get(fkey)
                    if prev is None or LEVEL_ORDER[fact.min_level] > LEVEL_ORDER[prev.min_level]:
                        bucket[fkey] = BriefFact(text=text, min_level=fact.min_level)

            # Flatten concepts into concept_lexicon
            for c in topic.concepts:
                term_key = c.term.strip().lower()
                # If term exists, keep the higher level
                existing = concept_lexicon.get(term_key)
                if existing is None or LEVEL_ORDER[c.min_level] > LEVEL_ORDER[existing.min_level]:
                    concept_lexicon[term_key] = ConceptLexiconEntry(
                        domain=topic.domain,
                        min_level=c.min_level,
                    )

        # Ensure personas have their own_domain set if not already present
        for p in req.personas:
            if p.own_domain and p.own_domain not in per_persona[p.id]:
                per_persona[p.id][p.own_domain] = Level.expert

        config = KnowledgeConfig(
            scenario_id=req.scenario_id,
            per_persona=per_persona,
            concept_lexicon=concept_lexicon,
            expert_briefs={d: list(facts.values()) for d, facts in expert_briefs.items() if facts},
        )
        return SaveConfigResponse(knowledge_config=config)
    except Exception as exc:
        logger.exception("Failed to compile knowledge config")
        raise HTTPException(status_code=400, detail=f"Invalid config data: {exc}")


@router.post("/chat/{persona_id}", response_model=KLChatResponse)
def chat_with_persona(persona_id: str, req: KLChatRequest):
    """Send a message to a persona. Runs router -> generation -> verifier with retries."""
    if req.target_persona.id != persona_id:
        raise HTTPException(
            status_code=400,
            detail=f"Mismatched persona_id in URL ({persona_id}) and body ({req.target_persona.id})",
        )

    try:
        last_msg = req.history[-1]["message"] if req.history else req.message
        conv_turns = [
            ConversationTurn(speaker=h["speaker"], message=h["message"]) for h in req.history
        ]

        # 1. Route
        route_res = _router.route(
            message=req.message,
            persona=req.target_persona,
            knowledge_config=req.knowledge_config,
            tone=req.tone,
        )

        # 2. Generate (expert-brief facts are filtered by this persona's level per domain)
        brief_domains = route_res.classification.domains or [route_res.classification.primary_domain]
        gen_res = _generator.generate(
            persona=req.target_persona,
            knowledge_config=req.knowledge_config,
            scenario_description=req.scenario_description,
            tone=req.tone,
            response_mode=route_res.response_mode,
            history=conv_turns,
            domains=brief_domains,
            focus_message=req.message,
        )
        reply = gen_res.reply

        # 3. Verify
        ver_res = _verifier.verify(
            reply=reply,
            persona=req.target_persona,
            knowledge_config=req.knowledge_config,
            response_mode=route_res.response_mode,
            last_message=last_msg,
            run_llm_verifier=req.run_llm_verifier,
        )

        # 4. Retry loop on violation
        if not ver_res.passed:
            violation_terms = [v.term for v in ver_res.violations]
            if ver_res.llm_span:
                violation_terms.append(ver_res.llm_span)

            for _ in range(2):
                extra_note = f" (Do NOT use or casually explain these technical terms: {', '.join(violation_terms)})"
                gen_res = _generator.generate(
                    persona=req.target_persona,
                    knowledge_config=req.knowledge_config,
                    scenario_description=req.scenario_description + extra_note,
                    tone=req.tone,
                    response_mode=route_res.response_mode,
                    history=conv_turns,
                    domains=brief_domains,
                    focus_message=req.message,
                )
                reply = gen_res.reply
                ver_res = _verifier.verify(
                    reply=reply,
                    persona=req.target_persona,
                    knowledge_config=req.knowledge_config,
                    response_mode=route_res.response_mode,
                    last_message=last_msg,
                    run_llm_verifier=req.run_llm_verifier,
                )
                if ver_res.passed:
                    break
            else:
                reply = "I'm not entirely sure about the technical details on that, to be honest."

        timings = {
            "router_ms": route_res.classification.latency_ms,
            "generation_ms": gen_res.latency_ms,
            "verification_ms": ver_res.latency_ms,
            "total_ms": round(
                route_res.classification.latency_ms
                + gen_res.latency_ms
                + ver_res.latency_ms,
                2,
            ),
        }

        # ── Observer hook (non-blocking, KL runtime) ──────────────────────────
        # Emit only the public turn: speaker name + final reply text.
        if req.session_id:
            try:
                from backend.observer.pipeline import get_pipeline
                from backend.observer.schemas import TurnEvent
                import asyncio as _asyncio
                _event = TurnEvent(
                    session_id=req.session_id,
                    turn_index=len(conv_turns),
                    speaker=req.target_persona.name,
                    listeners=[],
                    message=reply,
                    runtime="kl_chat",
                )
                pipeline = get_pipeline()
                try:
                    loop = _asyncio.get_event_loop()
                    loop.call_soon_threadsafe(pipeline._sessions[req.session_id].queue.put_nowait, _event)
                except Exception:
                    pass  # session not yet registered — observer is optional
            except Exception as _obs_exc:
                logger.debug("KL observer emit skipped: %s", _obs_exc)
        # ─────────────────────────────────────────────────────────────────────

        return KLChatResponse(
            reply=reply,
            target_persona_id=persona_id,
            response_mode=route_res.response_mode,
            persona_level=route_res.persona_level,
            classification=route_res.classification,
            verifier_result=ver_res,
            latency_breakdown_ms=timings,
        )
    except Exception as exc:
        logger.exception("Chat processing failed")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {exc}")
