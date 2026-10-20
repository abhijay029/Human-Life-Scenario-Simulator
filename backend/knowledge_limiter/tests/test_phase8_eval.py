"""Phase 8 tests — Evaluation harness runner.

All LLM calls are mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from pydantic import BaseModel

from backend.knowledge_limiter.eval.probes import generate_router_benchmark_set
from backend.knowledge_limiter.eval.runner import run_eval_suite
from backend.knowledge_limiter.schemas.models import Level


class _MockRouterOut(BaseModel):
    domains: list[str]
    required_level: Level
    primary_domain: str


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    # LLM classifier return
    llm.complete_structured.return_value = _MockRouterOut(
        domains=["artificial_intelligence"],
        required_level=Level.layperson,
        primary_domain="artificial_intelligence",
    )
    # LLM persona generation return
    llm.complete.return_value = "I am a doctor, so I focus on the clinical symptoms rather than technology."
    return llm


class TestEvaluationSuite:
    def test_benchmark_probe_set_has_expected_count(self):
        probes = generate_router_benchmark_set()
        assert len(probes) >= 60

    def test_run_eval_suite_computes_all_metrics(self, mock_llm, tmp_path):
        report_file = tmp_path / "test_report.json"
        metrics = run_eval_suite(report_file=str(report_file), llm_client=mock_llm)

        assert "leak_rate" in metrics
        assert "over_restriction_rate" in metrics
        assert "router_accuracy" in metrics
        assert "p50_latency_ms" in metrics
        assert "p95_latency_ms" in metrics
        assert metrics["total_probes"] > 0
        assert report_file.exists()
