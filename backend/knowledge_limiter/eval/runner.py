"""
Evaluation runner for Knowledge Limiter.

Calculates:
- Leak rate (percentage of forbidden technical terms produced outside persona expertise)
- Over-restriction rate (percentage of times persona acts ignorant of things within its level)
- Router accuracy (evaluated against hand-labeled probe dataset)
- Latency percentiles (p50, p95 per turn breakdown)
"""
from __future__ import annotations

import json
import logging
import statistics
import time
from typing import Any
from pydantic import BaseModel

from .probes import (
    DOCTOR_PROBES,
    ENGINEER_PROBES,
    PersonaProbe,
    ProbeCategory,
    generate_router_benchmark_set,
)
from ..schemas.models import Level, ResponseMode
from ..schemas.helpers import level_gte
from ..llm_client import LLMClient
from ..router.classifier import MessageRouter
from ..generation.persona_generator import PersonaGenerator, ConversationTurn
from ..verification.verifier import OutputVerifier
from ..cli import _build_demo_scenario

logger = logging.getLogger(__name__)


class EvalMetrics(BaseModel):
    leak_rate: float
    over_restriction_rate: float
    router_accuracy: float
    total_probes: int
    p50_latency_ms: float
    p95_latency_ms: float
    step_latencies: dict[str, float]


def run_eval_suite(
    report_file: str | None = "eval_report.json",
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Execute evaluation benchmark across router accuracy and persona probes."""
    if llm_client is None:
        llm_client = LLMClient()

    doctor, engineer, scenario, knowledge_config = _build_demo_scenario()
    personas_map = {doctor.id: doctor, engineer.id: engineer}

    router = MessageRouter(llm_client)
    generator = PersonaGenerator(llm_client)
    verifier = OutputVerifier(llm_client)

    # 1. Router accuracy test
    router_probes = generate_router_benchmark_set()
    router_correct = 0

    for probe in router_probes:
        res = router.classify(probe.message, knowledge_config)
        # Domain match and level match
        domain_match = res.primary_domain.lower() == probe.expected_domain.lower()
        level_match = res.required_level == probe.expected_level
        if domain_match and level_match:
            router_correct += 1

    router_accuracy = router_correct / len(router_probes) if router_probes else 0.0

    # 2. Persona probe test (leak rate, over-restriction, latency)
    all_probes = DOCTOR_PROBES + ENGINEER_PROBES
    leaks = 0
    over_restrictions = 0
    total_latency_ms: list[float] = []
    router_latencies: list[float] = []
    gen_latencies: list[float] = []
    ver_latencies: list[float] = []

    for probe in all_probes:
        persona = personas_map[probe.persona_id]

        # Route
        t0 = time.monotonic()
        route_res = router.route(
            message=probe.prompt,
            persona=persona,
            knowledge_config=knowledge_config,
            tone=scenario.tone,
        )
        router_latencies.append(route_res.classification.latency_ms)

        # Generate
        gen_res = generator.generate(
            persona=persona,
            knowledge_config=knowledge_config,
            scenario_description=scenario.description,
            tone=scenario.tone,
            response_mode=route_res.response_mode,
            history=[ConversationTurn("Interviewer", probe.prompt)],
        )
        gen_latencies.append(gen_res.latency_ms)

        # Verify
        ver_res = verifier.verify(
            reply=gen_res.reply,
            persona=persona,
            knowledge_config=knowledge_config,
            response_mode=route_res.response_mode,
            last_message=probe.prompt,
        )
        ver_latencies.append(ver_res.latency_ms)

        total_turn = (time.monotonic() - t0) * 1000
        total_latency_ms.append(total_turn)

        # Check for forbidden leaks in reply
        reply_lower = gen_res.reply.lower()
        has_leak = any(forbidden in reply_lower for forbidden in probe.forbidden_terms)
        if not ver_res.passed or has_leak:
            leaks += 1

        # Check for over-restriction
        if probe.expected_category == ProbeCategory.should_know:
            if route_res.response_mode in (ResponseMode.lost,) or len(gen_res.reply.strip()) < 15:
                over_restrictions += 1

    leak_rate = leaks / len(all_probes) if all_probes else 0.0
    over_rest_rate = over_restrictions / len(all_probes) if all_probes else 0.0

    total_latency_ms.sort()
    p50 = statistics.median(total_latency_ms) if total_latency_ms else 0.0
    p95_idx = int(0.95 * len(total_latency_ms))
    p95 = total_latency_ms[min(p95_idx, len(total_latency_ms) - 1)] if total_latency_ms else 0.0

    metrics = {
        "leak_rate": round(leak_rate, 4),
        "over_restriction_rate": round(over_rest_rate, 4),
        "router_accuracy": round(router_accuracy, 4),
        "total_probes": len(all_probes),
        "total_router_probes": len(router_probes),
        "p50_latency_ms": round(p50, 1),
        "p95_latency_ms": round(p95, 1),
        "mean_router_latency_ms": round(statistics.mean(router_latencies), 1) if router_latencies else 0.0,
        "mean_generation_latency_ms": round(statistics.mean(gen_latencies), 1) if gen_latencies else 0.0,
        "mean_verifier_latency_ms": round(statistics.mean(ver_latencies), 1) if ver_latencies else 0.0,
    }

    if report_file:
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2)
        except Exception as exc:
            logger.warning("Could not write eval report to %s: %s", report_file, exc)

    return metrics
