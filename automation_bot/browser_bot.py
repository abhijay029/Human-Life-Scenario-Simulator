"""
Automated Browser Bot for Human Life Scenario Simulator
======================================================
Automates Microsoft Edge or Google Chrome to navigate to http://localhost:3000,
walks through Character Setup, Knowledge Profiles, Scenario Configuration,
triggers the simulation, and views the Real-Time Observer relationship
trajectories and scorecard live on the user's screen.

Automatically starts the FastAPI backend (port 8000) and Next.js frontend (port 3000)
if they are not already running!

Usage:
  python -m automation_bot.browser_bot
  python -m automation_bot.browser_bot --browser msedge
  python -m automation_bot.browser_bot --browser chrome
  python -m automation_bot.browser_bot --turns 16
"""
from __future__ import annotations

import sys
import io
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel
from playwright.sync_api import sync_playwright

from .scenarios import SCENARIOS

app = typer.Typer(help="Automated Browser Simulator Bot", invoke_without_command=True)
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_url_alive(url: str, timeout: float = 1.0) -> bool:
    """Checks if an HTTP URL responds with 200 OK."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_servers_running(project_root: Path) -> list[subprocess.Popen]:
    """Ensures both backend (8000) and frontend (3000) are up, starting them if needed."""
    spawned_procs = []

    # 1. Backend check (port 8000)
    if not is_url_alive("http://localhost:8000/health"):
        console.print("[dim yellow]Backend server not detected on port 8000. Auto-starting FastAPI...[/dim yellow]")
        py_exe = sys.executable
        backend_proc = subprocess.Popen(
            [py_exe, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        spawned_procs.append(backend_proc)

        # Wait up to 20s for backend
        for _ in range(20):
            time.sleep(1)
            if is_url_alive("http://localhost:8000/health"):
                console.print("[dim green]✓ Backend server ready at http://localhost:8000[/dim green]")
                break
        else:
            console.print("[yellow]Backend took longer than expected to report healthy, continuing...[/yellow]")
    else:
        console.print("[dim green]✓ Backend server is active on http://localhost:8000[/dim green]")

    # 2. Frontend check (port 3000)
    if not is_url_alive("http://localhost:3000"):
        console.print("[dim yellow]Frontend server not detected on port 3000. Auto-starting Next.js dev server...[/dim yellow]")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=str(project_root / "frontend"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        spawned_procs.append(frontend_proc)

        # Wait up to 45s for Next.js to compile and serve 200 OK
        console.print("[dim]Waiting for Next.js compilation (10-25s)...[/dim]")
        for _ in range(45):
            time.sleep(1)
            if is_url_alive("http://localhost:3000"):
                console.print("[dim green]✓ Frontend server ready at http://localhost:3000[/dim green]")
                break
        else:
            console.print("[yellow]Frontend taking time to compile, proceeding to connect...[/yellow]")
    else:
        console.print("[dim green]✓ Frontend server is active on http://localhost:3000[/dim green]")

    return spawned_procs


def run_browser_simulation(
    browser_channel: str = "msedge",
    turns: int = 6,
    scenario_name: str = "startup",
    keep_open: bool = True,
):
    console.print()
    console.print(Panel(
        f"[bold white]Launching Visible Browser Automation[/bold white]\n"
        f"[dim]Scenario:[/dim] [spring_green3]{scenario_name}[/spring_green3] | [dim]Turns:[/dim] [cyan]{turns}[/cyan]\n"
        f"[dim]Browser:[/dim] [cyan]{browser_channel}[/cyan] | [dim]Target:[/dim] [cyan]http://localhost:3000[/cyan]\n"
        f"This will auto-verify servers and open your browser to run the simulation.",
        title="🌐 [bold cyan]Browser Simulator Bot[/bold cyan]",
        border_style="cyan",
    ))

    # Auto-start servers if down
    spawned = ensure_servers_running(PROJECT_ROOT)

    with sync_playwright() as p:
        console.print(f"[dim]Launching visible {browser_channel} window...[/dim]")
        try:
            browser = p.chromium.launch(
                channel=browser_channel,
                headless=False,
                args=["--start-maximized"],
            )
        except Exception as exc:
            console.print(f"[yellow]Could not launch {browser_channel}: {exc}. Falling back to default chromium...[/yellow]")
            browser = p.chromium.launch(headless=False, args=["--start-maximized"])

        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        try:
            # 1. Navigate to frontend
            console.print("[bold cyan]Step 1: Navigating to http://localhost:3000...[/bold cyan]")
            page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)

            # 2. Character Builder screen
            console.print("[bold cyan]Step 2: Character Builder detected. Configuring personas...[/bold cyan]")
            page.wait_for_selector("text=Character Builder", timeout=60000)

            # If scenario defines personas, populate them in the Character Builder
            if scenario_name in SCENARIOS and "personas" in SCENARIOS[scenario_name]:
                personas = SCENARIOS[scenario_name]["personas"]
                if len(personas) >= 2:
                    console.print(f"[dim]Setting characters: {personas[0]['name']} & {personas[1]['name']}...[/dim]")
                    name_inputs = page.locator("input[placeholder='Rahul Sharma']")
                    occ_inputs = page.locator("input[placeholder='Senior Manager']")

                    if name_inputs.count() >= 1:
                        name_inputs.first.fill(personas[0]["name"])
                        time.sleep(0.15)
                    if name_inputs.count() >= 2:
                        name_inputs.nth(1).fill(personas[1]["name"])
                        time.sleep(0.15)

                    if occ_inputs.count() >= 1:
                        occ_inputs.first.fill(personas[0]["occupation"])
                        time.sleep(0.15)
                    if occ_inputs.count() >= 2:
                        occ_inputs.nth(1).fill(personas[1]["occupation"])
                        time.sleep(0.15)

            page.evaluate("window.scrollBy({ top: 300, behavior: 'smooth' })")
            time.sleep(1.5)
            page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' })")
            time.sleep(1)

            # Click Continue to Scenario / Knowledge Setup
            continue_btn = page.locator("button:has-text('Continue to Scenario')")
            if continue_btn.count() > 0:
                console.print("[dim]Clicking 'Continue to Scenario →'...[/dim]")
                continue_btn.first.click()
                time.sleep(2.5)

            # 3. Knowledge Profiles screen (if visible)
            if page.locator("text=Knowledge Profiles").count() > 0:
                console.print("[bold cyan]Step 3: Reviewing Knowledge Profiles & Boundaries...[/bold cyan]")
                time.sleep(2)
                confirm_btn = page.locator("button:has-text('Confirm Knowledge Config')")
                skip_btn = page.locator("button:has-text('Skip')")
                if confirm_btn.count() > 0 and confirm_btn.first.is_enabled():
                    console.print("[dim]Confirming knowledge configuration...[/dim]")
                    confirm_btn.first.click()
                    time.sleep(2.5)

                # If still on Knowledge screen, click Skip to proceed to Scenario
                if page.locator("text=Knowledge Profiles").count() > 0 and skip_btn.count() > 0:
                    console.print("[dim]Proceeding directly to Scenario Setup...[/dim]")
                    skip_btn.first.click()
                    time.sleep(2)

            # 4. Scenario Setup screen
            console.print("[bold cyan]Step 4: Scenario Setup. Setting parameters...[/bold cyan]")
            page.wait_for_selector("text=Scenario Setup", timeout=30000)
            page.evaluate("window.scrollBy({ top: 350, behavior: 'smooth' })")
            time.sleep(1.5)

            # Populate scenario text if specified
            if scenario_name in SCENARIOS:
                scen = SCENARIOS[scenario_name]
                console.print(f"[dim]Configuring scenario: {scen.get('title', scenario_name)}...[/dim]")
                textareas = page.locator("textarea")
                if textareas.count() > 0 and scen.get("scenario"):
                    textareas.first.fill(scen["scenario"])
                    time.sleep(0.3)
                if textareas.count() > 1 and scen.get("decision_point"):
                    textareas.nth(1).fill(scen["decision_point"])
                    time.sleep(0.3)

            # Adjust turns if requested
            plus_btn = page.locator("button:has-text('+')")
            minus_btn = page.locator("button:has-text('−')")
            target_turns = min(20, max(2, turns))
            if plus_btn.count() > 0 and target_turns > 4:
                console.print(f"[dim]Adjusting dialogue turns to {target_turns}...[/dim]")
                for _ in range(target_turns - 4):
                    plus_btn.first.click()
                    time.sleep(0.1)
            elif minus_btn.count() > 0 and target_turns < 4:
                console.print(f"[dim]Adjusting dialogue turns to {target_turns}...[/dim]")
                for _ in range(4 - target_turns):
                    minus_btn.first.click()
                    time.sleep(0.1)

            # Click Run Simulation
            run_btn = page.locator("button:has-text('Run Simulation')")
            if run_btn.count() == 0:
                run_btn = page.locator("button:has-text('Run')")

            console.print("[bold green]Clicking 'Run Simulation →'...[/bold green]")
            run_btn.first.click()

            # 5. Waiting for simulation
            console.print(f"[dim]Simulation is running ({target_turns} turns)... Watching live progression...[/dim]")
            start_time = time.time()
            max_wait_seconds = 600  # 10 minutes timeout
            completed = False

            while time.time() - start_time < max_wait_seconds:
                # Check for completion
                if (
                    page.locator("text=Simulation Results").count() > 0
                    or page.locator("h2:has-text('Simulation Results')").count() > 0
                ):
                    completed = True
                    break

                # Check if UI returned to scenario screen with an error banner (⚠ ...)
                err_loc = page.locator(".bg-red-alert\\/10, [data-testid='error-banner']")
                if err_loc.count() > 0 and err_loc.first.is_visible():
                    err_text = err_loc.first.inner_text().strip()
                    if err_text.startswith("⚠") or "failed" in err_text.lower():
                        console.print(f"[bold red]Simulation error detected in UI: {err_text}[/bold red]")
                        break

                time.sleep(3)

            if not completed:
                raise TimeoutError(f"Simulation did not reach Results within {max_wait_seconds}s.")

            console.print("[bold spring_green3]Simulation completed! Viewing results...[/bold spring_green3]")
            time.sleep(3)

            # 6. View Dialogue
            page.evaluate("window.scrollBy({ top: 250, behavior: 'smooth' })")
            time.sleep(3)

            # 7. Switch to Real-Time Observer Tab!
            observer_tab = page.locator("button:has-text('Observer')")
            if observer_tab.count() > 0:
                console.print("[bold cyan]Step 5: Opening Real-Time Observer & Trajectory Tab...[/bold cyan]")
                observer_tab.first.click()
                time.sleep(2)
                # Scroll to show dyad charts and gauges
                page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' })")
                time.sleep(3)
                page.evaluate("window.scrollBy({ top: 500, behavior: 'smooth' })")
                time.sleep(3)

            # 8. Switch to Scorecard Tab if available inside Observer
            scorecard_tab = page.locator("button:has-text('Scorecard')")
            if scorecard_tab.count() > 0:
                console.print("[bold cyan]Step 6: Viewing Final Conversation Scorecard...[/bold cyan]")
                scorecard_tab.first.click()
                time.sleep(3)

            console.print()
            console.print(Panel(
                "[bold spring_green3]Browser simulation automation finished successfully![/bold spring_green3]\n"
                f"Completed [bold cyan]{target_turns} turns[/bold cyan] for scenario [bold white]'{scenario_name}'[/bold white].\n"
                "The browser will stay open so you can inspect the charts, dialogue, and scorecards.",
                border_style="spring_green3",
            ))

            if keep_open:
                console.print("[dim]Press Enter in this terminal to close the browser (or close it manually)...[/dim]")
                try:
                    input()
                except Exception:
                    time.sleep(60)

        finally:
            browser.close()


@app.command()
def main(
    scenario: str = typer.Option("startup", "--scenario", "-s", help="Preset scenario: startup | medical | ethics | marathon | music"),
    turns: int = typer.Option(6, "--turns", "-t", help="Dialogue turns to execute (e.g. 4 to 20)"),
    browser: str = typer.Option("msedge", "--browser", "-b", help="Browser to use: msedge | chrome"),
):
    """
    Automate the Human Life Scenario Simulator in a real visible browser.
    """
    run_browser_simulation(browser_channel=browser, turns=turns, scenario_name=scenario, keep_open=True)


if __name__ == "__main__":
    app()
