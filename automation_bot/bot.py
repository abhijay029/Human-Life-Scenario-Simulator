"""
Automated Simulator Bot
=======================
An independent, automated runner for the Human Life Scenario Simulator.
Runs complete conversations, streams turns, and visualizes the real-time
relationship trajectories and observer analysis live in the terminal.

Usage:
  python -m automation_bot.bot
  python -m automation_bot.bot --scenario startup
  python -m automation_bot.bot --scenario medical
  python -m automation_bot.bot --mode demo
  python -m automation_bot.bot --mode direct
  python -m automation_bot.bot --mode api
"""
from __future__ import annotations

import sys
import io
import time
import json
import threading
from typing import Optional, Literal
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows to avoid cp1252 encoding crashes
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich import box
from rich.rule import Rule

from .scenarios import SCENARIOS

app = typer.Typer(help="Automated Simulator Bot", invoke_without_command=True)
console = Console()

# ── Visual Helpers ────────────────────────────────────────────────────────────

DIM_COLORS = {
    "trust": "spring_green3",
    "rapport": "deep_sky_blue1",
    "tension": "bright_red",
    "respect": "gold1",
    "power_balance": "medium_purple1",
}


def render_gauge(val: float, min_val: float = 0.0, max_val: float = 100.0, width: int = 15) -> str:
    """ASCII/Unicode colored gauge bar [██████░░░░]"""
    val = max(min_val, min(max_val, val))
    fraction = (val - min_val) / (max_val - min_val) if max_val != min_val else 0.5
    filled = int(round(fraction * width))
    empty = width - filled
    return f"[bold]█[/bold]" * filled + "[dim]░[/dim]" * empty


def trend_arrow(label: str, dim: str) -> str:
    is_tension = dim == "tension"
    if label == "improving":
        return "[spring_green3]↑ (improving)[/spring_green3]" if not is_tension else "[spring_green3]↓ (improving)[/spring_green3]"
    if label == "deteriorating":
        return "[bright_red]↓ (worsening)[/bright_red]" if not is_tension else "[bright_red]↑ (worsening)[/bright_red]"
    return "[bright_black]→ (stable)[/bright_black]"


def display_turn_banner(turn_index: int, speaker: str, total_turns: int):
    color = "cyan" if turn_index % 2 == 0 else "amber"
    console.print()
    console.print(Rule(f"[bold cyan]Turn {turn_index + 1} of {total_turns} — [bold white]{speaker}[/bold white][/bold cyan]", style="cyan"))


def display_dialogue_speech(speaker: str, message: str, index: int):
    color = "cyan" if index % 2 == 0 else "bright_yellow"
    console.print(f"[{color}][bold]{speaker}:[/bold] \"{message}\"[/{color}]")


def display_observation_card(obs: dict):
    sentiment = obs.get("sentiment", "neutral")
    score = obs.get("sentiment_score", 0.0)
    emotions = obs.get("emotion_labels", [])
    key_event = obs.get("key_event")
    degraded = obs.get("degraded", False)

    sent_style = "spring_green3" if sentiment == "positive" else "bright_red" if sentiment == "negative" else "bright_black"
    sent_str = f"[{sent_style}][bold]{sentiment.upper()}[/bold] ({score:+.2f})[/{sent_style}]"
    emo_str = ", ".join(emotions) if emotions else "none"
    degraded_str = " [orange3][DEGRADED MODE][/orange3]" if degraded else ""

    info = f"  Sentiment: {sent_str} | Emotions: [italic]{emo_str}[/italic]{degraded_str}"
    if key_event:
        info += f"\n  [bold yellow]⚡ Key Event:[/bold yellow] [italic]{key_event}[/italic]"

    console.print(Panel(info, title="[dim]Observer Telemetry[/dim]", border_style="dim", box=box.ROUNDED))


def display_dyad_table(dyads: list[dict], trajectories: Optional[list[dict]] = None):
    """Prints relationship states per directed dyad pair."""
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    table.add_column("Dyad Pair", style="bold white", width=18)
    table.add_column("Dimension", style="dim", width=14)
    table.add_column("Value", justify="right", width=7)
    table.add_column("Gauge", width=18)
    table.add_column("Trajectory", width=18)

    traj_lookup = {}
    if trajectories:
        for t in trajectories:
            pair = t.get("dyad_pair")
            dim = t.get("dimension")
            traj_lookup[(pair, dim)] = t.get("label", "stable")

    for d in dyads:
        pair = f"{d['from_party']} -> {d['to_party']}"
        dims = [
            ("trust", d.get("trust", 50.0), 0.0, 100.0),
            ("rapport", d.get("rapport", 50.0), 0.0, 100.0),
            ("tension", d.get("tension", 50.0), 0.0, 100.0),
            ("respect", d.get("respect", 50.0), 0.0, 100.0),
            ("power_balance", d.get("power_balance", 0.0), -100.0, 100.0),
        ]
        first_row = True
        for dim, val, min_v, max_v in dims:
            gauge_str = f"[{DIM_COLORS.get(dim, 'white')}]{render_gauge(val, min_v, max_v)}[/{DIM_COLORS.get(dim, 'white')}]"
            label = traj_lookup.get((pair, dim), "stable")
            arrow = trend_arrow(label, dim)
            table.add_row(
                pair if first_row else "",
                dim,
                f"{val:.1f}",
                gauge_str,
                arrow,
            )
            first_row = False

    console.print(table)


def display_scorecard(scorecard: dict):
    console.print()
    console.print(Rule("[bold spring_green3]Final Conversation Scorecard[/bold spring_green3]", style="spring_green3"))

    metrics = [
        ("Persona Consistency", scorecard.get("persona_consistency", 7.0)),
        ("Emotional Realism", scorecard.get("emotional_realism", 7.0)),
        ("Conversational Coherence", scorecard.get("conversational_coherence", 7.0)),
        ("Goal Alignment", scorecard.get("goal_alignment", 7.0)),
        ("Conflict Realism", scorecard.get("conflict_realism", 7.0)),
        ("Social Plausibility", scorecard.get("social_plausibility", 7.0)),
        ("Overall Realism", scorecard.get("overall_realism", 7.0)),
    ]

    m_table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    m_table.add_column("Realism Metric", width=28)
    m_table.add_column("Score", justify="right", width=10)
    m_table.add_column("Rating Bar", width=20)

    for name, score in metrics:
        bar = render_gauge(score, 0.0, 10.0, width=15)
        color = "spring_green3" if score >= 8.0 else "gold1" if score >= 6.0 else "bright_red"
        m_table.add_row(name, f"[{color}]{score:.1f} / 10[/{color}]", f"[{color}]{bar}[/{color}]")

    console.print(m_table)

    # Goal success
    goal_succ = scorecard.get("goal_success", {})
    if goal_succ:
        console.print("[bold]Persona Goal Success Probabilities:[/bold]")
        for name, prob in goal_succ.items():
            pct = int(round(prob * 100))
            color = "spring_green3" if pct >= 65 else "gold1" if pct >= 40 else "bright_red"
            console.print(f"  • {name}: [{color}][bold]{pct}%[/bold][/{color}]")

    outcome = scorecard.get("outcome_category", "Most Likely")
    out_style = "spring_green3" if outcome == "Best Case" else "gold1" if outcome == "Most Likely" else "bright_red"
    console.print(f"\n[bold]Outcome Category:[/bold] [{out_style}][bold]{outcome}[/bold][/{out_style}]")

    summary = scorecard.get("summary")
    if summary:
        console.print(f"[italic]{summary}[/italic]")

    recs = scorecard.get("recommendations", [])
    if recs:
        console.print("\n[bold cyan]Recommendations:[/bold cyan]")
        for r in recs:
            console.print(f"  → {r}")


# ── Execution Modes ───────────────────────────────────────────────────────────

def run_playback_mode(scenario_data: dict, delay: float):
    """
    Simulated live execution mode. Demonstrates real-time observation,
    smooth dyad EMA evolution, and terminal visualization with zero API latency.
    """
    from backend.observer.core import ObserverService
    from backend.observer.schemas import TurnEvent

    console.print("[dim]Mode: Animated Playback Engine (Zero-Token Simulation Demo)[/dim]")
    observer = ObserverService()
    session_id = f"bot_playback_{scenario_data['id']}_{int(time.time())}"
    participant_names = [p["name"] for p in scenario_data["personas"]]

    observer.get_or_create_session(
        session_id=session_id,
        participants=participant_names,
        scenario_description=scenario_data["scenario"],
    )

    dialogue = scenario_data["playback_dialogue"]

    for idx, (speaker, utterance) in enumerate(dialogue):
        display_turn_banner(idx, speaker, len(dialogue))
        display_dialogue_speech(speaker, utterance, idx)

        time.sleep(delay * 0.5)

        event = TurnEvent(
            session_id=session_id,
            turn_index=idx,
            speaker=speaker,
            listeners=[p for p in participant_names if p != speaker],
            message=utterance,
            runtime="simulation",
        )

        obs = observer.observe_turn(event)
        display_observation_card(obs.model_dump())

        # Display dyad states & trajectories
        trajectories = observer.get_all_trajectories(session_id)
        display_dyad_table(
            [s.model_dump() for s in obs.dyad_states],
            [t.model_dump() for t in trajectories],
        )

        time.sleep(delay)

    scorecard = observer.finalize(session_id)
    display_scorecard(scorecard.model_dump())


def run_direct_mode(scenario_data: dict, delay: float):
    """
    Direct in-process simulation using backend engine + observer.
    """
    from backend.agents.persona import Persona
    from backend.simulation.engine import run_simulation
    from backend.observer.pipeline import get_pipeline

    console.print("[dim]Mode: In-Process Engine + Real-Time Observer Pipeline[/dim]")

    personas = [Persona(**p) for p in scenario_data["personas"]]
    session_id = f"bot_direct_{scenario_data['id']}_{int(time.time())}"
    pipeline = get_pipeline()

    pipeline.get_or_create_session(
        session_id=session_id,
        participants=[p.name for p in personas],
        scenario_description=scenario_data["scenario"],
    )
    pipeline.start_worker(session_id)

    console.print("[dim]Starting LangGraph multi-agent simulation...[/dim]")

    # Run simulation in a thread so we can poll/watch observer progress
    result_log = []
    def _exec():
        nonlocal result_log
        result_log = run_simulation(
            personas=personas,
            scenario=scenario_data["scenario"],
            decision_point=scenario_data["decision_point"],
            max_turns=scenario_data["max_turns"],
            session_id=session_id,
        )

    t = threading.Thread(target=_exec)
    t.start()

    # Poll observations from pipeline
    observed_count = 0
    total_turns = scenario_data["max_turns"]

    while t.is_alive() or observed_count < len(pipeline.get_observations(session_id)):
        obs_list = pipeline.get_observations(session_id)
        while observed_count < len(obs_list):
            obs = obs_list[observed_count]
            # Find matching utterance
            msg_text = "..."
            if observed_count < len(result_log):
                msg_text = result_log[observed_count]["message"]
            display_turn_banner(obs.turn_index, obs.speaker, total_turns)
            display_dialogue_speech(obs.speaker, msg_text, obs.turn_index)
            display_observation_card(obs.model_dump())
            trajectories = pipeline.get_trajectories(session_id)
            display_dyad_table(
                [s.model_dump() for s in obs.dyad_states],
                [tr.model_dump() for tr in trajectories],
            )
            observed_count += 1
            time.sleep(delay)
        time.sleep(0.5)

    t.join()

    # Get final scorecard
    scorecard = pipeline.get_scorecard(session_id)
    if scorecard:
        display_scorecard(scorecard.model_dump())
    else:
        console.print("[yellow]Waiting for scorecard completion...[/yellow]")
        time.sleep(1.5)
        sc = pipeline.get_scorecard(session_id)
        if sc:
            display_scorecard(sc.model_dump())


def run_api_stream_mode(scenario_data: dict, delay: float):
    """
    Connects to running FastAPI server via SSE stream and triggers simulation.
    """
    import requests

    base_url = "http://localhost:8000"
    try:
        r = requests.get(f"{base_url}/health", timeout=3.0)
        if r.status_code != 200:
            raise RuntimeError(f"Server returned status {r.status_code}")
    except Exception as exc:
        console.print(f"[bold red]Cannot connect to FastAPI server at {base_url}[/bold red]: {exc}")
        console.print("[yellow]Falling back to In-Process direct mode...[/yellow]")
        run_direct_mode(scenario_data, delay)
        return

    session_id = f"bot_api_{scenario_data['id']}_{int(time.time())}"
    participant_names = [p["name"] for p in scenario_data["personas"]]

    # 1. Register observer session
    requests.post(
        f"{base_url}/observer/sessions",
        json={
            "session_id": session_id,
            "scenario_description": scenario_data["scenario"],
            "participants": participant_names,
        },
        timeout=5.0,
    )

    console.print(f"[dim]Connected to FastAPI server. Registered session [bold]{session_id}[/bold][/dim]")

    # 2. Trigger simulation in background thread
    def _post_sim():
        requests.post(
            f"{base_url}/simulate",
            json={
                "personas": scenario_data["personas"],
                "scenario": scenario_data["scenario"],
                "decision_point": scenario_data["decision_point"],
                "max_turns": scenario_data["max_turns"],
                "store_memories": True,
                "session_id": session_id,
            },
            timeout=300.0,
        )

    sim_thread = threading.Thread(target=_post_sim)
    sim_thread.start()

    # 3. Stream SSE events
    stream_url = f"{base_url}/observer/sessions/{session_id}/stream"
    console.print(f"[dim]Listening to SSE stream: {stream_url}[/dim]")

    current_trajs = []
    try:
        with requests.get(stream_url, stream=True, timeout=120.0) as stream_resp:
            event_type = ""
            for line in stream_resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if decoded.startswith("event: "):
                    event_type = decoded[7:].strip()
                elif decoded.startswith("data: "):
                    data_str = decoded[6:].strip()
                    try:
                        payload = json.loads(data_str)
                    except Exception:
                        continue

                    if event_type == "turn":
                        t_idx = payload.get("turn_index", 0)
                        spk = payload.get("speaker", "Unknown")
                        msg = payload.get("message", "")
                        display_turn_banner(t_idx, spk, scenario_data["max_turns"])
                        display_dialogue_speech(spk, msg, t_idx)

                    elif event_type == "observation":
                        display_observation_card(payload)
                        display_dyad_table(payload.get("dyad_states", []), current_trajs)

                    elif event_type == "trajectory":
                        current_trajs = payload.get("trajectories", [])

                    elif event_type == "final":
                        display_scorecard(payload)
                        break

    except Exception as exc:
        console.print(f"[red]Stream interrupted:[/red] {exc}")

    sim_thread.join()


# ── CLI Command ───────────────────────────────────────────────────────────────

@app.command()
def main(
    scenario: str = typer.Option("marathon", "--scenario", "-s", help="Scenario choice: marathon (16 turns) | music | startup | medical"),
    mode: str = typer.Option("demo", "--mode", "-m", help="Execution mode: demo | auto | api | direct"),
    turns: Optional[int] = typer.Option(None, "--turns", "-t", help="Override number of turns (e.g. 15 to 20)"),
    delay: float = typer.Option(0.5, "--delay", "-d", help="Seconds pause between turns for visual readability"),
):
    """
    Automated Simulator Bot runner.
    """
    scenario_key = scenario.lower()
    if scenario_key not in SCENARIOS:
        console.print(f"[bold red]Unknown scenario '{scenario}'. Available: {list(SCENARIOS.keys())}[/bold red]")
        raise typer.Exit(code=1)

    sc_data = dict(SCENARIOS[scenario_key])
    if turns is not None:
        sc_data["max_turns"] = turns

    # Header Panel
    console.print()
    header_text = (
        f"[bold white]{sc_data['title']}[/bold white]\n"
        f"[dim]{sc_data['scenario']}[/dim]\n\n"
        f"[bold cyan]Decision Point:[/bold cyan] {sc_data['decision_point']}\n"
        f"[dim]Participants: {', '.join([p['name'] for p in sc_data['personas']])} | Turns: {sc_data['max_turns']}[/dim]"
    )
    console.print(Panel(header_text, title="🤖 [bold cyan]Automated Simulator Bot[/bold cyan]", border_style="cyan", box=box.DOUBLE))

    if mode == "demo":
        run_playback_mode(sc_data, delay)
    elif mode == "direct":
        run_direct_mode(sc_data, delay)
    elif mode == "api":
        run_api_stream_mode(sc_data, delay)
    else:  # auto: check if localhost:8000 is alive, else fallback to demo or direct
        import requests
        try:
            r = requests.get("http://localhost:8000/health", timeout=1.0)
            if r.status_code == 200:
                console.print("[dim green]Detected live backend server at http://localhost:8000. Running API stream mode...[/dim green]")
                run_api_stream_mode(sc_data, delay)
                return
        except Exception:
            pass

        console.print("[dim yellow]No live backend detected at http://localhost:8000. Running animated playback demo...[/dim yellow]")
        run_playback_mode(sc_data, delay)

    console.print()
    console.print(Panel("[bold spring_green3]Simulation & Observer Analysis Complete.[/bold spring_green3]", border_style="spring_green3"))


if __name__ == "__main__":
    app()
