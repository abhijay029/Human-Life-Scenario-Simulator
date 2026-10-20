"""
Observer Agent CLI Demo.

Feed a scripted dialogue through ObserverService and print dyad states + trajectories per turn.

Usage:
    python -m backend.observer.cli
    python -m backend.observer.cli --scenario conflict
    python -m backend.observer.cli --scenario reconcile
"""
from __future__ import annotations

import sys
import io

# Force UTF-8 output on Windows (prevents cp1252 UnicodeEncodeError for special chars)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

app = typer.Typer(help="Observer Agent CLI Demo", invoke_without_command=True)
console = Console()


SCRIPTS: dict[str, dict] = {
    "music_career": {
        "description": "Arjun tells his father Rahul he wants to drop engineering and pursue music full-time after graduating. He has already been offered a music production deal worth ₹3 lakh.",
        "participants": ["Arjun", "Rahul"],
        "turns": [
            ("Arjun", ["Rahul"], "Dad, I need to talk to you about something important. I've decided I don't want to continue with engineering after graduation."),
            ("Rahul", ["Arjun"], "What are you talking about? You have one semester left! We've invested everything in your education."),
            ("Arjun", ["Rahul"], "I know, and I'm grateful. But I've been offered a music production deal — ₹3 lakh upfront. This is real, Dad. It's not a hobby anymore."),
            ("Rahul", ["Arjun"], "₹3 lakh? That's nothing compared to an engineering salary. Music is unstable. What happens when the money runs out?"),
            ("Arjun", ["Rahul"], "I understand your fear. But I've been preparing for this for two years. I have savings, contacts, and a business plan. I'm not being reckless."),
            ("Rahul", ["Arjun"], "...I didn't know you'd been working on this for two years. Why didn't you tell me earlier?"),
        ],
    },
    "conflict": {
        "description": "Two colleagues argue over a missed project deadline that caused a client escalation.",
        "participants": ["Priya", "Karan"],
        "turns": [
            ("Priya", ["Karan"], "Karan, the client just called. They're furious. The deliverable you promised wasn't ready."),
            ("Karan", ["Priya"], "You're blaming me? You signed off on the timeline knowing it was unrealistic!"),
            ("Priya", ["Karan"], "I trusted you to flag it if you were behind. That's basic professional communication."),
            ("Karan", ["Priya"], "I sent you three updates last week. Did you even read them? Or were you too busy impressing the executives?"),
            ("Priya", ["Karan"], "That is completely out of line. My relationship with leadership has nothing to do with your missed deadlines."),
            ("Karan", ["Priya"], "You know what, you're right. I should have called instead of emailing. I'm sorry for the snide comment. But we both need to fix this together."),
        ],
    },
    "reconcile": {
        "description": "Two estranged friends meet again after a long silence following a falling out.",
        "participants": ["Meera", "Dev"],
        "turns": [
            ("Meera", ["Dev"], "I didn't expect to see you here. It's been almost two years."),
            ("Dev", ["Meera"], "I know. I've wanted to reach out but I wasn't sure you'd want to hear from me after... everything."),
            ("Meera", ["Dev"], "Honestly, I was hurt for a long time. But I've had time to think. I played my part in how things went wrong too."),
            ("Dev", ["Meera"], "That means a lot to hear. I said things I regret. I shouldn't have made assumptions without listening to your side."),
            ("Meera", ["Dev"], "Me too. I think I wanted to be right more than I wanted to keep our friendship."),
            ("Dev", ["Meera"], "So... do you think we can try again? Slowly, but try?"),
        ],
    },
}


def _dimension_trend_arrow(dim: str, slope: float, threshold: float = 0.75) -> str:
    from backend.observer.math_utils import classify_trajectory
    label = classify_trajectory(dim, slope)
    if label == "improving":
        return "[green]▲ improving[/green]"
    elif label == "deteriorating":
        return "[red]▼ deteriorating[/red]"
    return "[dim]→ stable[/dim]"


@app.command()
def demo(
    scenario: str = typer.Option("music_career", help="Scenario key: music_career | conflict | reconcile"),
    show_prompt: bool = typer.Option(False, help="Print the rendered prompt for the first turn"),
):
    """Run a scripted dialogue through the Observer Agent and display real-time dyad states."""
    if scenario not in SCRIPTS:
        console.print(f"[red]Unknown scenario '{scenario}'. Choose from: {', '.join(SCRIPTS.keys())}[/red]")
        raise typer.Exit(code=1)

    script = SCRIPTS[scenario]
    participants = script["participants"]
    turns = script["turns"]

    console.print()
    console.print(Panel(
        f"[bold cyan]Observer Agent — Real-Time Demo[/bold cyan]\n"
        f"[dim]Scenario:[/dim] [white]{scenario}[/white]\n"
        f"[dim]Participants:[/dim] [white]{', '.join(participants)}[/white]\n\n"
        f"[italic]{script['description']}[/italic]",
        expand=False,
        border_style="cyan",
    ))
    console.print()

    from backend.observer.core import ObserverService
    from backend.observer.schemas import TurnEvent
    from backend.observer.math_utils import calculate_slope

    service = ObserverService()  # uses real LLM
    session_id = f"cli_demo_{scenario}"
    service.get_or_create_session(
        session_id,
        participants=participants,
        scenario_description=script["description"],
    )

    for turn_idx, (speaker, listeners, message) in enumerate(turns):
        console.rule(f"[bold]Turn {turn_idx + 1} — {speaker}[/bold]")
        console.print(f"[bold white]{speaker}:[/bold white] \"{message}\"")
        console.print()

        event = TurnEvent(
            session_id=session_id,
            turn_index=turn_idx,
            speaker=speaker,
            listeners=listeners,
            message=message,
        )

        obs = service.observe_turn(event)

        # Sentiment badge
        sentiment_color = {"positive": "green", "neutral": "yellow", "negative": "red"}[obs.sentiment]
        console.print(
            f"  Sentiment: [{sentiment_color}]{obs.sentiment} ({obs.sentiment_score:+.2f})[/{sentiment_color}]"
            f"  |  Emotions: {', '.join(obs.emotion_labels) if obs.emotion_labels else 'N/A'}"
            + (" | [dim]DEGRADED[/dim]" if obs.degraded else "")
        )
        if obs.key_event:
            console.print(f"  [bold yellow]Key Event:[/bold yellow] {obs.key_event}")
        console.print()

        # Dyad state table
        session = service.get_or_create_session(session_id)
        for pair_key, dyad_state in session.dyads.items():
            history = session.history_values.get(pair_key, {})

            tbl = Table(
                title=f"[bold]{pair_key}[/bold]",
                box=box.SIMPLE_HEAD,
                header_style="bold cyan",
                show_lines=False,
                min_width=55,
            )
            tbl.add_column("Dimension", style="dim")
            tbl.add_column("Value", justify="right")
            tbl.add_column("Δ This Turn", justify="right")
            tbl.add_column("Trend", justify="left")

            pair_deltas = obs.dyad_deltas.get(pair_key, {})

            for dim in ("trust", "rapport", "tension", "respect", "power_balance"):
                val = getattr(dyad_state, dim)
                raw_delta = pair_deltas.get(dim, 0.0)
                effective_delta = round(0.4 * max(-10.0, min(10.0, raw_delta)), 2)
                hist_vals = history.get(dim, [val])
                slope = calculate_slope(hist_vals)
                trend = _dimension_trend_arrow(dim, slope)

                delta_color = "green" if effective_delta > 0 else ("red" if effective_delta < 0 else "dim")
                delta_str = f"[{delta_color}]{effective_delta:+.1f}[/{delta_color}]"

                tbl.add_row(dim, f"{val:.1f}", delta_str, trend)

            console.print(tbl)
        console.print()

    # Final scorecard
    console.rule("[bold cyan]Final Scorecard[/bold cyan]")
    console.print("[dim]Running comprehensive post-conversation evaluation...[/dim]")

    scorecard = service.finalize(session_id)

    score_tbl = Table(box=box.SIMPLE_HEAD, header_style="bold cyan", show_lines=False)
    score_tbl.add_column("Metric", style="dim")
    score_tbl.add_column("Score / 10", justify="right")

    metrics = [
        ("persona_consistency", scorecard.persona_consistency),
        ("emotional_realism", scorecard.emotional_realism),
        ("conversational_coherence", scorecard.conversational_coherence),
        ("goal_alignment", scorecard.goal_alignment),
        ("conflict_realism", scorecard.conflict_realism),
        ("social_plausibility", scorecard.social_plausibility),
        ("overall_realism", scorecard.overall_realism),
    ]
    for name, value in metrics:
        color = "green" if value >= 8 else ("yellow" if value >= 6 else "red")
        score_tbl.add_row(name, f"[{color}]{value:.1f}[/{color}]")
    console.print(score_tbl)

    if scorecard.goal_success:
        console.print("\n  [bold]Goal Success Probabilities:[/bold]")
        for person, prob in scorecard.goal_success.items():
            color = "green" if prob >= 0.7 else ("yellow" if prob >= 0.4 else "red")
            console.print(f"  {person}: [{color}]{prob:.0%}[/{color}]")

    console.print(f"\n  [bold]Outcome:[/bold] {scorecard.outcome_category}")
    if scorecard.summary:
        console.print(f"\n  [italic]{scorecard.summary}[/italic]")

    if scorecard.key_turning_points:
        console.print("\n  [bold yellow]Key Turning Points:[/bold yellow]")
        for tp in scorecard.key_turning_points:
            console.print(f"  • {tp}")

    if scorecard.recommendations:
        console.print("\n  [bold]Recommendations:[/bold]")
        for r in scorecard.recommendations:
            console.print(f"  → {r}")

    console.print()
    console.print(Panel("[bold green]Observer demo complete.[/bold green]", expand=False))


if __name__ == "__main__":
    app()
