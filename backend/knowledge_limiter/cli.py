"""
Knowledge Limiter CLI prototype.

Usage:
    python -m backend.knowledge_limiter.cli demo
    python -m backend.knowledge_limiter.cli eval-probes

Runs the doctor-vs-AI-engineer scenario through the full pipeline:
  - Topic generation (Phase 2)
  - Router classification (Phase 4)
  - Persona response generation (Phase 5)
  - Output verification (Phase 6)
"""
from __future__ import annotations

import os
import sys
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Knowledge Limiter CLI")
console = Console()


def _build_demo_scenario():
    """Build the doctor-vs-AI-engineer reference scenario."""
    from .schemas.models import (
        KLPersona,
        PersonalityProfile,
        BoundaryBehavior,
        Level,
        Tone,
        Topic,
        Concept,
        Scenario,
        KnowledgeConfig,
        ConceptLexiconEntry,
    )

    doctor = KLPersona(
        id="persona_doctor",
        name="Dr. Sarah Chen",
        profession="Cardiologist",
        personality=PersonalityProfile(
            traits=["methodical", "evidence-driven", "caring", "skeptical"],
            speech_style="precise but warm, uses medical analogies",
            boundary_behavior=BoundaryBehavior.ask_back,
        ),
        default_level=Level.layperson,
        own_domain="medicine",
        background_summary=(
            "Sarah has practiced cardiology for 12 years. She has used diagnostic software "
            "and heard AI may help with imaging, but has never studied ML or CS."
        ),
    )

    engineer = KLPersona(
        id="persona_engineer",
        name="Alex Rivera",
        profession="Senior ML Engineer",
        personality=PersonalityProfile(
            traits=["enthusiastic", "technical", "collaborative", "prone to jargon"],
            speech_style="casual but precise, loves explaining things",
            boundary_behavior=BoundaryBehavior.analogize,
        ),
        default_level=Level.layperson,
        own_domain="artificial_intelligence",
        background_summary=(
            "Alex builds and deploys large language models at a tech company. "
            "Knows medicine only from personal experience as a patient."
        ),
    )

    scenario = Scenario(
        id="scenario_doc_eng",
        description="A cardiologist and an ML engineer meet at a conference dinner and discuss AI in medicine.",
        tone=Tone.discussion,
        personas=[doctor.id, engineer.id],
        topics=[
            Topic(
                id="topic_ai_diagnostics",
                name="AI in Medical Diagnostics",
                domain="artificial_intelligence",
                concepts=[
                    Concept(term="machine learning", min_level=Level.basic),
                    Concept(term="neural network", min_level=Level.basic),
                    Concept(term="transformer", min_level=Level.advanced),
                    Concept(term="backpropagation", min_level=Level.advanced),
                    Concept(term="lora", min_level=Level.expert),
                    Concept(term="fine-tuning", min_level=Level.advanced),
                ],
                levels={doctor.id: Level.layperson, engineer.id: Level.expert},
            ),
            Topic(
                id="topic_medical_imaging",
                name="Medical Imaging",
                domain="medicine",
                concepts=[
                    Concept(term="echocardiogram", min_level=Level.basic),
                    Concept(term="mri protocol", min_level=Level.advanced),
                    Concept(term="ct angiography", min_level=Level.advanced),
                ],
                levels={doctor.id: Level.expert, engineer.id: Level.layperson},
            ),
        ],
    )

    knowledge_config = KnowledgeConfig(
        scenario_id=scenario.id,
        per_persona={
            doctor.id: {
                "artificial_intelligence": Level.layperson,
                "medicine": Level.expert,
            },
            engineer.id: {
                "artificial_intelligence": Level.expert,
                "medicine": Level.layperson,
            },
        },
        concept_lexicon={
            "transformer": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
            "backpropagation": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
            "lora": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.expert),
            "fine-tuning": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.advanced),
            "neural network": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.basic),
            "machine learning": ConceptLexiconEntry(domain="artificial_intelligence", min_level=Level.basic),
            "echocardiogram": ConceptLexiconEntry(domain="medicine", min_level=Level.basic),
            "mri protocol": ConceptLexiconEntry(domain="medicine", min_level=Level.advanced),
            "ct angiography": ConceptLexiconEntry(domain="medicine", min_level=Level.advanced),
        },
    )

    return doctor, engineer, scenario, knowledge_config


@app.command()
def demo(
    turns: int = typer.Option(4, help="Number of conversation turns"),
    run_llm_verifier: bool = typer.Option(False, help="Run LLM verifier on each reply"),
):
    """Run the doctor-vs-AI-engineer demo scenario."""
    from .llm_client import LLMClient
    from .router.classifier import MessageRouter
    from .generation.persona_generator import PersonaGenerator, ConversationTurn
    from .verification.verifier import OutputVerifier

    console.print(
        Panel(
            "[bold cyan]Knowledge Limiter Demo[/bold cyan]\nDoctor meets AI Engineer at a conference",
            expand=False,
        )
    )

    doctor, engineer, scenario, knowledge_config = _build_demo_scenario()

    llm_client = LLMClient()
    router = MessageRouter(llm_client)
    generator = PersonaGenerator(llm_client)
    verifier = OutputVerifier(llm_client)

    history: list[ConversationTurn] = []
    # Interleave speakers: engineer starts
    speaker_order = [engineer, doctor] * (turns // 2 + 1)

    for turn_i in range(turns):
        speaker = speaker_order[turn_i]
        last_msg = history[-1].message if history else ""

        console.rule(f"[dim]Turn {turn_i + 1} — {speaker.name} speaks ({speaker.profession})[/dim]")

        # 1. Route
        route_result = router.route(
            message=last_msg if last_msg else scenario.description,
            persona=speaker,
            knowledge_config=knowledge_config,
            tone=scenario.tone,
        )

        # 2. Generate
        gen_result = generator.generate(
            persona=speaker,
            knowledge_config=knowledge_config,
            scenario_description=scenario.description,
            tone=scenario.tone,
            response_mode=route_result.response_mode,
            history=history,
        )

        reply = gen_result.reply

        # 3. Verify
        verify_result = verifier.verify(
            reply=reply,
            persona=speaker,
            knowledge_config=knowledge_config,
            response_mode=route_result.response_mode,
            last_message=last_msg,
            run_llm_verifier=run_llm_verifier,
        )

        # 4. Handle violation retry
        if not verify_result.passed:
            console.print(f"[yellow]⚠ Verification failed for {speaker.name}. Retrying with constraints...[/yellow]")
            violation_terms = [v.term for v in verify_result.violations]
            if verify_result.llm_span:
                violation_terms.append(verify_result.llm_span)

            for retry_i in range(2):
                constraint_note = f" (Do NOT use or casually explain these technical terms: {', '.join(violation_terms)})"
                gen_result = generator.generate(
                    persona=speaker,
                    knowledge_config=knowledge_config,
                    scenario_description=scenario.description + constraint_note,
                    tone=scenario.tone,
                    response_mode=route_result.response_mode,
                    history=history,
                )
                reply = gen_result.reply
                verify_result = verifier.verify(
                    reply=reply,
                    persona=speaker,
                    knowledge_config=knowledge_config,
                    response_mode=route_result.response_mode,
                    last_message=last_msg,
                    run_llm_verifier=run_llm_verifier,
                )
                if verify_result.passed:
                    break
            else:
                reply = "I'm not entirely sure about the technical details on that, to be honest."

        history.append(ConversationTurn(speaker=speaker.name, message=reply))

        # Output turn
        title_info = (
            f"Mode: {route_result.response_mode.value} | "
            f"Persona level: {route_result.persona_level.value} | "
            f"Req level: {route_result.classification.required_level.value}"
        )
        console.print(
            Panel(
                f"[bold]{speaker.name}[/bold]:\n\n{reply}",
                title=f"[green]✓[/green] {title_info}" if verify_result.passed else f"[red]✗[/red] {title_info}",
                border_style="green" if verify_result.passed else "red",
            )
        )

        if not verify_result.passed:
            console.print(f"[red]  VIOLATIONS: {[v.term for v in verify_result.violations]}[/red]")
        if verify_result.over_restriction_warning:
            console.print(f"[yellow]  ⚠ Over-restriction warning logged[/yellow]")

        # Latency breakdown
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("Router", f"{route_result.classification.latency_ms:.1f}ms (via_lexicon={route_result.classification.via_lexicon})")
        table.add_row("Generation", f"{gen_result.latency_ms:.1f}ms")
        table.add_row("Verification", f"{verify_result.latency_ms:.1f}ms")
        console.print(table)
        console.print()

    console.print(Panel("[bold green]Demo finished successfully.[/bold green]", expand=False))


@app.command()
def eval_probes(
    report_file: str = typer.Option("eval_report.json", help="Path to write JSON evaluation metrics"),
):
    """Run the evaluation probe suite (Phase 8)."""
    from .eval.runner import run_eval_suite

    console.print(Panel("[bold cyan]Knowledge Limiter Evaluation Suite[/bold cyan]", expand=False))
    results = run_eval_suite(report_file=report_file)
    console.print(f"[green]Evaluation completed. Leak rate: {results['leak_rate']:.2%}, Router accuracy: {results['router_accuracy']:.2%}[/green]")


if __name__ == "__main__":
    app()
