# Human Life Scenario Simulator (HLSS) v0.3.0

HLSS is a multi-agent simulation system for exploring difficult real-life conversations before they happen. A user defines two or more characters, a shared situation, and either one decision or several alternative decisions. Persona agents generate a dialogue, while an Observer agent estimates sentiment, relationship direction, goal success, outcome, turning points, and recommendations.

The current implementation has two applications:

- A Python/FastAPI backend that owns LLM calls, persona memory, simulation, analysis, and multiverse ranking.
- A Next.js/React frontend that provides the character builder, scenario wizard, simulation status screen, and result visualisations.

Team: Abhijay Tambe (70), Himanshu Khobragade (04), Arpit Deshmukh (66)  
Guide: Prof. Harshita Patil

## Architecture and request flow

```text
Browser (Next.js :3000)
        |
        | direct HTTP requests to http://localhost:8000
        v
FastAPI (main.py)
        |
        +-- /characters/build -> Gemini character extraction
        +-- /simulate         -> LangGraph dialogue -> Observer analysis
        +-- /multiverse       -> sequential branches -> comparison report
        |
        +-- Ollama engine/observer/evaluator models
        +-- Gemini Embedding 001 -> local ChromaDB (./chroma_store)
```

The normal request path is:

1. The frontend collects persona records and scenario information.
2. FastAPI validates the request with Pydantic.
3. Each persona becomes a `Persona` object and, when enabled, its facts are inserted into that persona's ChromaDB collection.
4. The simulation engine creates one `PersonaAgent` per persona.
5. Agents bid for the next speaking turn. The highest-scoring eligible agent speaks through the engine LLM.
6. The dialogue repeats until the configured turn limit or until no agent has enough urgency to continue.
7. The Observer LLM analyses the completed dialogue into a structured result.
8. In multiverse mode, every branch follows the same process and branches are ranked by average persona goal-success probability.
9. The frontend renders the dialogue, analysis, ranked report, and (for multiverse runs) an interactive decision tree.

## Repository map

### Backend

| File | Responsibility and approach |
|---|---|
| `backend/__init__.py` | Package marker; no runtime logic. |
| `backend/agents/__init__.py` | Package marker for persona and Observer agents. |
| `backend/agents/persona.py` | Defines the Pydantic `Persona` model: name, age, occupation, traits, values, communication style, emotional triggers, background, and goals. `to_system_prompt()` converts those fields into an in-character prompt preview. The engine uses a more compact runtime prompt. |
| `backend/agents/observer.py` | Defines structured Observer output models and a LangChain prompt/parser. It passes scenario, decision, goals, and dialogue to the observer model and returns parsed analysis. It requests concise strings, at most two turning points, and at most two recommendations. Empty dialogue returns `{}`. |
| `backend/api/__init__.py` | Package marker for the API layer. |
| `backend/api/schemas.py` | FastAPI request/response contracts. It validates at least two personas, two to six multiverse branches, and two to twenty turns. It also defines dialogue, analysis, branch-summary, and character-builder response shapes. |
| `backend/api/routes.py` | Implements `/health`, `/simulate`, `/multiverse`, and `/characters/build`. Blocking model/simulation work is moved to a one-worker `ThreadPoolExecutor`. `_sim_lock` rejects overlapping simulations with HTTP 429. Character building uses Gemini; simulation and Observer calls use the backend components. Single-run analysis failures are tolerated by returning `analysis=None`; branch failures are retained inside multiverse results. |
| `backend/core/__init__.py` | Package marker for shared backend services. |
| `backend/core/llm.py` | Centralises three `ChatOllama` factories: `get_engine()`, `get_observer()`, and `get_evaluator()`. Model names come from `ENGINE_MODEL`, `OBSERVER_MODEL`, and `EVALUATOR_MODEL`. This is separate from the Gemini model instantiated directly in `routes.py` for persona extraction. |
| `backend/memory/__init__.py` | Package marker for memory services. |
| `backend/memory/memory_manager.py` | Provides thread-safe persistent ChromaDB memory. Each persona gets a sanitised collection name (`persona_<name>`). Persona facts are embedded in one batch with Gemini `models/gemini-embedding-001`; runtime recall embeds a query and retrieves nearest memories using cosine distance. A process-wide lock serialises local-store access. |
| `backend/simulation/__init__.py` | Package marker for simulation services. |
| `backend/simulation/engine.py` | Core dialogue engine. It defines `Bid`, `SimulationState`, bid/speaking prompts, `PersonaAgent`, scoring rules, and a compiled LangGraph. Bids run in parallel (maximum four concurrent calls), but the selected speaker is not the previous speaker. A name mention bypasses a bid LLM call and gives that persona urgency. Speaking sees the last two messages plus one recalled memory. Bid and speaking chains retry failures; bid failures fall back to urgency 2. The graph always permits a first utterance, then stops below `SPEAK_THRESHOLD` or at `max_turns`. Early exchanges are written back to memory only for the first few turns to reduce embedding traffic. |
| `backend/simulation/multiverse.py` | Runs each decision branch with the same personas and scenario. Despite importing concurrency support and accepting `max_workers`, the current implementation loops sequentially to protect free-tier limits and local ChromaDB. Each branch is analysed, failures are retained as error records, and successful branches are sorted by average goal-success probability. |
| `backend/evaluation/multiverse_evaluate.py` | Optional LLM-based realism evaluator, separate from the user-facing Observer. It scores persona consistency, emotional realism, conversational coherence, goal alignment, conflict realism, social plausibility, and overall realism from 1–10. It strips fences, extracts JSON, repairs common formatting problems, retries three times, excludes failed branches from averages, and returns per-branch plus averaged scores. |

### Entry point, configuration, and maintenance

| File | Responsibility and approach |
|---|---|
| `main.py` | Creates FastAPI, enables CORS for `localhost:3000` and `127.0.0.1:3000`, and includes the API router. Uvicorn starts the server. |
| `clean_chromadb.py` | Opens persistent ChromaDB with reset enabled and calls `client.reset()`. This destructively clears local persona/conversation memories. |
| `.env` | Local configuration for `GEMINI_API_KEY`, `GEMINI_MODEL`, `ENGINE_MODEL`, `OBSERVER_MODEL`, `EVALUATOR_MODEL`, `OLLAMA_BASE_URL`, and `CURRENT_MODEL`. It is ignored by Git; never commit keys. |
| `.gitignore` | Excludes secrets, `.hlss`, Python caches, ChromaDB, frontend dependencies/build output, notebooks, and other local/generated files. |
| `requirements.txt` | Pinned Python dependencies for FastAPI/Uvicorn, Pydantic, LangChain/LangGraph, Ollama, Gemini integrations, and ChromaDB. |

### Frontend application

| File | Responsibility and approach |
|---|---|
| `frontend/src/app/layout.tsx` | App Router root layout. Sets metadata, loads global CSS, and applies the scanline effect to the body. |
| `frontend/src/app/page.tsx` | Main client-side state machine: `build -> simulate -> running -> results`. It owns defaults, request state, duplicate-run protection, errors, reset, and selection of `/simulate` versus `/multiverse`. |
| `frontend/src/app/globals.css` | Global design system: fonts, dark background, grid/scanline effects, panels, glow effects, animations, scrollbars, and React Flow dark-theme overrides. |
| `frontend/src/components/ui.tsx` | Reusable `Panel`, `Button`, `Input`, `Textarea`, `Badge`, `Tag`, `TagInput`, `Spinner`, `Divider`, and `ProgressBar` primitives using Tailwind classes. |
| `frontend/src/components/CharacterBuilder.tsx` | Persona editor with multiple cards, editable scalar fields, tag-style list fields, add/remove operations, and AI Quick Build through `/characters/build`. It validates the minimum persona information before advancing. |
| `frontend/src/components/ScenarioSetup.tsx` | Scenario and run configuration. Switches single/multiverse modes, edits the scenario, edits one decision or 2–6 branches, controls maximum turns, and disables Run until valid. |
| `frontend/src/components/SimulatingScreen.tsx` | Non-streaming progress screen. Animated status steps are visual feedback only; they are not server-sent progress events. |
| `frontend/src/components/ResultsView.tsx` | Chooses single or multiverse result presentation. Single mode has Dialogue and Analysis tabs. Multiverse mode has Comparison Report, Decision Tree, branch-selectable Dialogue, and branch Analysis tabs. React Flow is dynamically imported with SSR disabled. |
| `frontend/src/components/DialogueViewer.tsx` | Displays turn-by-turn dialogue and overlays Observer sentiment. It maps sentiment to colours/dots and renders score bars. |
| `frontend/src/components/AnalysisPanel.tsx` | Displays trajectory, outcome summary, persona goal probabilities, turning points, and recommendations, with colour/icon variants. |
| `frontend/src/components/DecisionTree.tsx` | Builds a client-only React Flow graph with a scenario root, one node per branch, and optional outcome nodes. Branch nodes show average goal success and are highlighted using the report's best/worst/likely decision points. |
| `frontend/src/components/ComparisonReport.tsx` | Renders best, most-likely, and worst cards plus a ranked branch table. Percentages derive from backend 0–1 goal-success values. |
| `frontend/src/lib/types.ts` | TypeScript interfaces for personas, dialogue, Observer results, simulation responses, multiverse responses, reports, and UI modes. Intended to mirror `backend/api/schemas.py`. |
| `frontend/src/lib/api.ts` | Typed fetch client. It posts directly to `http://localhost:8000`, uses a 15-minute abort timeout, converts non-2xx responses to `Error`s, and exposes a health check. |

### Frontend configuration

| File | Responsibility and approach |
|---|---|
| `frontend/package.json` | Next.js scripts and dependencies: React, React Flow, Framer Motion, Lucide icons, `clsx`, Tailwind, and TypeScript tooling. |
| `frontend/package-lock.json` | npm lockfile for reproducible frontend dependency installation. |
| `frontend/next.config.js` | Defines an `/api/*` rewrite to port 8000 and an eight-minute experimental proxy timeout. Current `src/lib/api.ts` bypasses this rewrite and calls port 8000 directly. |
| `frontend/tailwind.config.ts` | Defines content paths plus custom dark sci-fi colours, fonts, shadows, animations, and keyframes. |
| `frontend/postcss.config.js` | Enables Tailwind CSS and Autoprefixer. |
| `frontend/tsconfig.json` | Enables strict TypeScript, bundler resolution, the `@/*` alias to `src/*`, incremental checking, and Next.js integration. |
| `frontend/README.md` | Frontend setup/design notes. Its proxy wording is older than the current direct-fetch implementation; use `src/lib/api.ts` as the request-routing source of truth. |

## Backend behaviour in detail

### Persona representation and memory

Every persona must provide `name`, `age`, `occupation`, `personality_traits`, `values`, `communication_style`, `emotional_triggers`, `background`, and `goals`. When `store_memories` is true, the API inserts seven fact documents per persona if that collection is empty. During speaking, the engine recalls one document using a query made from the decision point and previous message.

The vector store persists between runs. Changing a persona with the same name does not automatically remove old facts because the name maps to the same ChromaDB collection. Use `clean_chromadb.py` for a clean local memory state.

### Speaker selection

At each graph cycle, the engine:

1. Excludes the previous speaker when alternatives exist.
2. Requests a 0–10 urgency bid from remaining personas in parallel.
3. Gives a name-addressed persona urgency 7 without an LLM call.
4. Calculates `urgency + 3.0 if addressed - 0.5 * times_already_spoken`.
5. Selects the highest score.
6. Ends after the first turn if no one wants to continue; otherwise it requires a score of at least 4.0.

The first speaker uses a threshold of zero so a run cannot finish with an empty dialogue. The API default is six turns; the frontend starts with four. Engine constants at the top of `backend/simulation/engine.py` tune thresholds, history size, concurrency, and retries.

### Observer output

The Observer returns sentiment records, an improving/stable/deteriorating relationship trajectory, a trajectory explanation, one goal-success record per persona, an outcome category, summary, turning points, and recommendations. The prompt asks for very short strings and only two turning points and recommendations. Analysis is best-effort in `/simulate`: if the call or parsing fails, dialogue is still returned.

### Multiverse ranking

Multiverse mode repeats the same simulation once per decision branch. Branches are currently sequential, not parallel. A branch score is the arithmetic mean of its persona `success_probability` values. The API returns branches highest-to-lowest. The comparison report selects highest as best, lowest as worst, and the middle ascending-score item as most likely.

## API reference

The backend runs at `http://localhost:8000`.

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/health` | none | `{"status":"ok","service":"HumanSimulator API"}` |
| `POST` | `/characters/build` | `{ "description": "free-text character description" }` | Structured persona plus `system_prompt_preview` |
| `POST` | `/simulate` | Personas (minimum 2), scenario, `decision_point`, optional `max_turns` 2–20 and `store_memories` | Scenario, decision, dialogue log, optional Observer analysis |
| `POST` | `/multiverse` | Personas (minimum 2), scenario, 2–6 `decision_branches`, optional `max_turns` 2–20 and `store_memories` | Scenario, ranked branches, comparison report |

Interactive OpenAPI documentation is available at `http://localhost:8000/docs` after startup.

## Setup and running

Requirements: Python with the pinned dependencies, Ollama running with the models named by `ENGINE_MODEL`, `OBSERVER_MODEL`, and `EVALUATOR_MODEL`, a Gemini API key for persona extraction/embeddings, and Node.js/npm.

Create `.env` in the repository root:

```dotenv
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
ENGINE_MODEL=your_ollama_engine_model
OBSERVER_MODEL=your_ollama_observer_model
EVALUATOR_MODEL=your_ollama_evaluator_model
OLLAMA_BASE_URL=http://localhost:11434
```

Start the backend from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Requests are synchronous and model/rate-limit constrained, so the frontend uses a long client timeout.

## Standalone scripts and stored outputs

These scripts are executable experiments rather than a pytest suite. They construct sample Rahul/Arjun personas and print results.

| File | What it exercises |
|---|---|
| `test_character.py` | Stores Rahul's facts if absent and tests semantic recall for a query about challenging his decisions. |
| `test_simulation.py` | Loads two persona memories and runs one short three-turn simulation. |
| `test_multi_persona_simulation.py` | Runs a four-persona simulation and prints speaking order, counts, repeats, early termination, and round-robin comparison. |
| `test_observer.py` | Runs a simulation and passes dialogue to the Observer. |
| `test_multiverse.py` | Runs three branches, prints branch dialogue/analysis, and prints the comparison report. |
| `testing.py` | End-to-end sample: memory preload, three-branch multiverse, Observer output, comparison report, and realism evaluation. |
| `test_metric_at_k.py` | Evaluation harness: generates five scenarios and five branches, evaluates the first `k` branches for `k=1..5`, and aggregates realism metrics. It makes many LLM calls and is not a quick smoke test. |
| `output_logs.txt` | Checked-in text output from previous experiments; reference only. |
| `system_score.json` | Saved evaluation score artifact. |
| `system_scores/system_score1.json` | Additional saved evaluation score artifact. |
| `test_scenario_log.json` | Saved scenario/test data from the evaluation workflow. |
| `notebooks/` | Notebook workspace excluded from the normal runtime path. |
| `.hlss/` | Local project/tooling state, ignored by Git. |
| `chroma_store/` | Persistent local ChromaDB data; ignored and resettable with `clean_chromadb.py`. |

Run a short backend smoke test:

```powershell
python test_simulation.py
```

Run the complete sample pipeline:

```powershell
python testing.py
```

These scripts perform real model and embedding calls; they do not use mocks.

## Technology choices

| Area | Current choice |
|---|---|
| API | FastAPI + Uvicorn |
| Validation | Pydantic 2 |
| Dialogue orchestration | LangGraph `StateGraph` |
| LLM chains | LangChain prompts, parsers, retries, and Ollama integration |
| Engine/Observer/Evaluator provider | Ollama via `ChatOllama` |
| Character-builder provider | Gemini via `ChatGoogleGenerativeAI` |
| Embeddings | Gemini Embedding 001 |
| Vector memory | Persistent local ChromaDB |
| Frontend | Next.js 14 App Router, React 18, TypeScript |
| Visualisation | React Flow |
| Styling | Tailwind CSS plus custom CSS tokens |

## Current-version caveats

- There is no streaming protocol. The browser waits for the complete response; the progress screen is illustrative.
- Only one simulation is allowed at a time in the API process. A second receives HTTP 429.
- Multiverse branches run sequentially even though `run_multiverse()` retains a `max_workers` parameter.
- The backend Observer currently emits `outcome_category` values `In favor` or `disfavor`, while some frontend presentation logic expects `Best Case`, `Most Likely`, and `Worst Case`. The comparison report supplies those ranking concepts, but direct category badges/tree styling may not match until the contracts are unified.
- `frontend/src/lib/api.ts` calls port 8000 directly. The `/api` rewrite in `next.config.js` and the proxy description in `frontend/README.md` are not the active dashboard route.
- Persona facts are cached by sanitised name. Reusing a name reuses its collection; reset or rename when testing a changed profile.
- The system is a simulation and decision-support aid, not a psychological diagnosis or guarantee of real-world outcomes.
