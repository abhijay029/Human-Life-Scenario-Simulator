# Knowledge Limiter Module — Architecture & Technical Design

## 1. Executive Summary

The **Knowledge Limiter** is a multi-layer cognitive constraint system designed for the Human Life Scenario Simulator. Rather than relying on fragile negative prompting ("do not mention transformers"), the system enforces strict knowledge boundaries through positive capability profiling, deterministic lexicon pre-filtering, runtime classification, response-mode steering, output verification, and isolated memory.

---

## 2. Core Design Principles

1. **Default to Layperson, Not Omniscient:** Every persona begins as an average educated adult across all domains unless explicitly configured otherwise.
2. **Gate Both Comprehension & Speech:** The persona cannot nod along to incomprehensible jargon, nor can it generate domain-specific mechanisms it does not understand.
3. **Positive Descriptions Over Prohibitions:** Prompts articulate what the persona *does* know from everyday life and their domain, rather than giving a leaky list of forbidden words.
4. **Boundary Behavior is Personality-Dependent:** When pushed beyond their knowledge level, personas react according to their personality (`admit`, `bluff`, `deflect`, `ask_back`, `analogize`) and scenario tone (`debate`, `discussion`, `casual`).
5. **Strict Latency Budget (< 3s per turn):**
   - Sub-millisecond lexicon pre-pass to skip LLM calls on obvious concepts.
   - Small, fast model for routing classification when required.
   - Streamable main model for in-character generation.
   - LLM verifier triggered only when out-of-domain lexicon checks are inconclusive.
6. **User-Editable Everything:** Topics, concept tags, and persona levels can be reviewed and edited in the setup UI before or during simulation.

---

## 3. Technology Stack & Choices

| Component | Choice | Rationale |
|---|---|---|
| **Language** | Python 3.11+ / 3.12 | Modern type hinting, fast runtime, native async support. |
| **Data Models** | Pydantic v2 | Strict schema validation, fast C-core serialization, clean OpenAPI integration. |
| **Web Framework** | FastAPI | High-throughput async endpoints, automatic OpenAPI documentation. |
| **Prompt Engine** | Jinja2 | Clean separation of prompt logic and Python source; templates editable independently. |
| **LLM Interface** | `LLMClient` (Provider-Agnostic) | Decoupled abstraction (`complete`, `complete_structured`) supporting Google Gemini (`gemini-2.5-flash`), Ollama, or OpenAI without caller refactoring. |
| **CLI & Formatting** | Typer & Rich | Interactive command-line testing, formatted status panels, and benchmark report generation. |
| **Frontend UI** | Next.js 14 / React 18 / Tailwind | Integrated with existing simulator frontend; grid-based topic review and bulk editing. |
| **Test Suite** | Pytest | Comprehensive unit tests across all 8 phases (80 unit & integration tests). |

---

## 4. Multi-Layer Pipeline

```
Incoming Turn Message
         │
         ▼
┌─────────────────────────────────┐
│   Phase 4: Message Router       │
│  - Lexicon Pre-Pass (< 1ms)     │  ── Hit? ──> Use Lexicon Domain & Level
│  - LLM Classifier (if needed)   │
└─────────────────────────────────┘
         │
         ▼ (Compare Persona Level vs Required Level)
┌─────────────────────────────────┐
│ ResponseMode Decision Engine    │
│  - understands (diff >= 0)      │
│  - partial     (diff == -1)     │
│  - lost / analogizes (diff <= -2│
│  (Adjusted by BoundaryBehavior) │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Phase 5: Persona Generator    │
│  - Identity & Personality       │
│  - Positive Knowledge Profile   │
│  - Isolated Heard Memory        │
│  - Turn Response Instruction    │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Phase 6: Output Verifier      │
│  Layer 1: Deterministic Lexicon │
│           Scan (Allows Echoes)  │
│  Layer 2: LLM Verifier (opt)    │
└─────────────────────────────────┘
         │
         ├── Violation Detected? ──> Re-prompt with offending terms (Max 2 retries)
         │                           Fallback: Safe in-character uncertainty
         ▼ Passed
Persona Reply Delivered
```

---

## 5. Knowledge Levels & Semantics

| Level | Can Use / Understand | Cannot Use / Explain |
|---|---|---|
| `layperson` | News-level ideas ("AI chatbots", "vaccines prevent disease") | Technical mechanisms, math, internal architectures |
| `basic` | High-level mechanisms ("learns from data", "antibiotics kill bacteria") | Model architectures, equations, specialized protocols |
| `advanced` | Standard field terminology ("transformer", "CT angiography", "randomized trials") | Cutting-edge research, niche hyperparameter tuning |
| `expert` | Everything in domain (niche specifics, edge cases, formulas) | Nothing restricted within their domain |

---

## 6. Memory Isolation & Dynamic Learning (Phase 7)

- **Isolated Memory:** Each persona maintains its own memory log consisting strictly of utterances it has heard or spoken in the conversation. No persona context is cross-contaminated with another's private background facts.
- **Dynamic Concept Learning:** When enabled, if another speaker provides an explanation (e.g., *"A transformer is essentially a neural network that..."*), the listener's effective level for that specific term is dynamically upgraded (e.g. from `layperson` to `basic`), preventing unrealistic repeated confusion.

---

## 7. Evaluation & Benchmark Suite (Phase 8)

The module ships with an automated evaluation harness:
- **Router Benchmark Set:** ~100 hand-labeled messages across AI, Medicine, Economics, and Daily Life domains.
- **Persona Probe Set:** Reference probes for Dr. Sarah Chen (Cardiologist) and Alex Rivera (ML Engineer) testing `should_know`, `partial`, `should_not_know`, and adversarial baiting.
- **Key Metrics:**
  - `leak_rate`: Proportion of turns where forbidden out-of-domain technical terms leak into replies.
  - `over_restriction_rate`: Proportion of turns where a persona acts ignorant of things within its capability.
  - `router_accuracy`: Accuracy of topic domain and level classification.
  - `p50_latency_ms` and `p95_latency_ms`: Per-turn performance monitoring.

---

## 8. Observer Agent — Real-Time Evaluation & Trajectory Tracking

### 8.1 System Overview

The **Observer Agent** (`backend/observer/`) provides quantitative real-time evaluation and relationship trajectory tracking across simulation dialogue turns.

```
       Turn Generated (LangGraph speak / KL chat)
                           │
                           ▼
              TurnEvent (Public transcript only)
                           │
                           ▼ (emit_turn_sync via call_soon_threadsafe)
             ┌─────────────────────────────┐
             │   asyncio.Queue (Per-Session)│
             └─────────────────────────────┘
                           │
                           ▼
             ┌─────────────────────────────┐
             │   Async Background Worker   │
             │   - ObserverService         │
             │   - MathUtils (EMA + Clamping)
             │   - SQLite Storage          │
             │   - SSE Event Broadcast     │
             └─────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
SSE Client (Next.js)                   SQLite Database
("turn", "observation",                (.cache/observer.db)
 "trajectory", "final")
```

### 8.2 Directed Dyadic Relationship Model

For every pair of participants (A, B), the observer tracks directed dyadic states:
- `A->B`: How persona A views/relates to persona B.
- `B->A`: How persona B views/relates to persona A.

**Tracked Dimensions & Bounds:**
- `trust`: 0.0 to 100.0 (Neutral = 50.0)
- `rapport`: 0.0 to 100.0 (Neutral = 50.0)
- `tension`: 0.0 to 100.0 (Neutral = 50.0)
- `respect`: 0.0 to 100.0 (Neutral = 50.0)
- `power_balance`: -100.0 to +100.0 (Neutral = 0.0)

**Mathematical Modeling & Smoothing:**
1. **Delta Clamping:** Raw deltas from LLM scoring are clamped to `[-10.0, +10.0]` to prevent single-turn distortion.
2. **Exponential Moving Average (EMA):**
   $$\text{effective\_delta} = \alpha \cdot \text{clamped\_delta}$$
   $$\text{value}_{t} = \text{clamp}(\text{value}_{t-1} + \text{effective\_delta},\, \text{min\_bound},\, \text{max\_bound})$$
   with $\alpha = 0.40$.
3. **Slope Calculation:** Ordinary Least Squares (OLS) regression over the turn history:
   $$\text{slope} = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sum (x_i - \bar{x})^2}$$
4. **Trajectory Classification:**
   - For `trust`, `rapport`, `respect`, `power_balance`: slope $\ge +0.75 \to \text{"improving"}$; slope $\le -0.75 \to \text{"deteriorating"}$; otherwise $\text{"stable"}$.
   - For `tension` (inverted polarity): slope $\ge +0.75 \to \text{"deteriorating"}$; slope $\le -0.75 \to \text{"improving"}$.
5. **Turning Point Detection:** Any per-turn change where $|\text{clamped\_delta}| \ge 5.0$ records a `TurningPoint` with timestamp, dimension, and reason.

### 8.3 Zero-Latency & Privacy Guarantees

- **Non-blocking LangGraph Hook:** Simulation execution is decoupled from observer evaluation via `asyncio.Queue` and `loop.call_soon_threadsafe()`. Zero latency is added to persona generation.
- **Privacy Boundary:** The observer only receives the public dialogue transcript (`TurnEvent: speaker, listeners, message`). It has zero access to private persona vector memory, system prompts, or hidden knowledge profiles.
- **Quota Resilience (Degraded Mode):** Free-tier Gemini quota limits (HTTP 429) trigger a single retry followed by a non-fatal fallback: the previous dyad state is held with delta 0.0 and flagged `degraded=True`.

### 8.4 REST & Streaming SSE API

Mounted at `/observer/*`:
- `POST /observer/sessions` — Register session and initialize background worker
- `GET /observer/sessions` — List all sessions from SQLite storage
- `GET /observer/sessions/{id}/stream` — Server-Sent Events stream (`turn`, `observation`, `trajectory`, `final`, `heartbeat`)
- `GET /observer/sessions/{id}/observations` — Retrieve all turn observations
- `GET /observer/sessions/{id}/trajectory` — Retrieve trajectory summaries for all dyads
- `GET /observer/sessions/{id}/scorecard` — Retrieve final 7-metric realism scorecard
- `POST /observer/sessions/{id}/turn` — Manually emit a turn event
- `POST /observer/sessions/{id}/finalize` — Manually trigger evaluation finalization
