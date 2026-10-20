# Automated Simulator Bot

An independent, automated terminal bot that runs human life simulations and visualizes the real-time **Observer Agent** and **Relationship Trajectory Tracking** turn-by-turn with colorized meters and gauge bars.

This tool is kept completely separate from the main application codebase in `automation_bot/`.

---

## Features

- **Live Turn Streaming:** Shows each persona's dialogue as it speaks.
- **Real-Time Telemetry:** Sentiment analysis, emotional state tags, and key conflict events per turn.
- **Visual Dyad Trajectories:** Colorized gauge meters (`[████████░░] 78.0`) and trend arrows ($\uparrow$ improving, $\downarrow$ deteriorating, $\rightarrow$ stable) for:
  - `trust`
  - `rapport`
  - `tension` (inverted polarity)
  - `respect`
  - `power_balance`
- **Final Evaluation Scorecard:** 7 realism metrics on a 0–10 scale, persona goal success probabilities, and strategic recommendations.
- **Three Scenarios Included:**
  - `music` (Family career conflict: Arjun vs Rahul)
  - `startup` (Co-founder cap table & IP dispute: Rohan vs Natasha)
  - `medical` (Clinical safety vs hospital AI triage: Dr. Sen vs Kabir)

---

## Quickstart

### 1. Browser Bot (Visible Browser Automation)
Opens your real web browser (Edge or Chrome), fills inputs, clicks through Character Setup, Knowledge Profiles, triggers the simulation, and displays the **Observer** tab and relationship charts on your screen:

```bash
# Launch visible Edge browser and run simulation
python -m automation_bot.browser_bot

# Or with Chrome
python -m automation_bot.browser_bot --browser chrome
```

---

### 2. Terminal Bot (Live Rich Terminal Streaming)
Run directly in your terminal with colored speaker dialogue, live telemetry, and gauge meters:

```bash
# Default (Auto-detects live backend or runs demo)
python -m automation_bot.bot

# Run with different scenarios
python -m automation_bot.bot --scenario startup
python -m automation_bot.bot --scenario medical

# Force Instant Demo Playback (Zero tokens, immediate visualization)
python -m automation_bot.bot --mode demo

# Stream directly from running FastAPI server (http://localhost:8000)
python -m automation_bot.bot --mode api

# Adjust turn pacing (e.g. 1 second per turn)
python -m automation_bot.bot --delay 1.0
```

---

## Modes

| Mode | Flag | Description |
|---|---|---|
| **Auto** | `--mode auto` (default) | Pings `http://localhost:8000/health`. If alive, connects to the SSE stream. Otherwise runs the playback demo. |
| **API** | `--mode api` | Connects to the running FastAPI server, triggers `/simulate`, and reads `/observer/sessions/{id}/stream`. |
| **Direct** | `--mode direct` | Runs the simulation engine and observer directly in-process without needing a web server. |
| **Demo** | `--mode demo` | High-fidelity playback of scripted dialogue through the observer logic. Great for presentations and testing without quota usage. |
