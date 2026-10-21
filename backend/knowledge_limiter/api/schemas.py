"""
API schemas for the Knowledge Limiter endpoints.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from ..schemas.models import (
    KLPersona,
    Topic,
    TopicBrief,
    KnowledgeConfig,
    ResponseMode,
    Tone,
    Level,
)
from ..topic_generation.generator import KLPersonaInput
from ..verification.verifier import VerificationResult
from ..router.classifier import ClassificationResult


class GenerateTopicsRequest(BaseModel):
    scenario_description: str
    tone: Tone = Tone.discussion
    personas: list[KLPersonaInput]
    decision_points: list[str] = []


class GenerateTopicsResponse(BaseModel):
    topics: list[Topic]


class GenerateBriefsRequest(BaseModel):
    topics: list[Topic]


class GenerateBriefsResponse(BaseModel):
    briefs: dict[str, TopicBrief]  # topic_id -> brief
    errors: dict[str, str] = {}
    skipped: list[str] = []


class SaveConfigRequest(BaseModel):
    scenario_id: str
    personas: list[KLPersona]
    topics: list[Topic]


class SaveConfigResponse(BaseModel):
    knowledge_config: KnowledgeConfig
    message: str = "Configuration saved successfully"


class KLChatRequest(BaseModel):
    message: str
    scenario_description: str
    tone: Tone = Tone.discussion
    knowledge_config: KnowledgeConfig
    target_persona: KLPersona
    history: list[dict[str, str]] = []  # [{"speaker": "...", "message": "..."}]
    run_llm_verifier: bool = False
    session_id: Optional[str] = None   # observer pipeline key (None = observer disabled)


class KLChatResponse(BaseModel):
    reply: str
    target_persona_id: str
    response_mode: ResponseMode
    persona_level: Level
    classification: ClassificationResult
    verifier_result: VerificationResult
    latency_breakdown_ms: dict[str, float]
