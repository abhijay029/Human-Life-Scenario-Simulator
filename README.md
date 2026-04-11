# Human Life Scenario Simulator (HLSS) v0.3.0

A Multi-Agent Simulation (MAS) framework that clones real-world personas using LLMs to stress-test real-life decisions before they occur.

**Team:** Abhijay Tambe (70) · Himanshu Khobragade (04) · Arpit Deshmukh (66)  
**Guide:** Prof. Harshita Patil

---

## Architecture

```
HLSS/
├── backend/                        ← Python / FastAPI
│   ├── agents/
│   │   ├── persona.py              Persona model + system prompt generator
│   │   ├── observer.py             Observer Agent (sentiment + outcome scoring)
│   │   └── hf_llm.py              HuggingFace fallback LLM (free-tier safety)
│   ├── memory/
│   │   └── memory_manager.py       ChromaDB + Gemini embeddings (thread-safe)
│   ├── simulation/
│   │   ├── engine.py               LangGraph stateful simulation engine
│   │   └── multiverse.py           Parallel multi-branch runner + comparison report
│   └── api/
│       ├── schemas.py              Pydantic request/response models
│       └── routes.py               FastAPI route handlers
├── main.py                         FastAPI app entry point
│
├── frontend/                       ← Next.js 14 Dashboard
│   └── src/
│       ├── app/page.tsx            Main app (3-step wizard)
│       ├── components/
│       │   ├── CharacterBuilder    Persona creation with AI Quick Build
│       │   ├── ScenarioSetup       Scenario + mode + branch configuration
│       │   ├── SimulatingScreen    Animated progress during simulation
│       │   ├── ResultsView         Tabs: dialogue, analysis, decision tree, report
│       │   ├── DialogueViewer      Turn-by-turn chat with sentiment overlays
│       │   ├── AnalysisPanel       Observer output: goals, trajectory, recs
│       │   ├── DecisionTree        React Flow interactive branch visualizer
│       │   └── ComparisonReport    Best/Worst/Most Likely comparison table
│       └── lib/
│           ├── types.ts            Shared TypeScript types (mirrors backend)
│           └── api.ts              Typed fetch client for FastAPI
│
└── test_*.py                       Backend test scripts
```

---

## Quick Start

### 1. Backend

```bash
# Create venv and install
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS/Linux

pip install -r requirements.txt

# Configure API keys
# Edit .env:
# GEMINI_API_KEY=your_gemini_key_here
# HF_API_TOKEN=your_huggingface_token_here   (optional fallback)
# GEMINI_MODEL=gemini-2.5-flash              (or gemini-2.5-flash-lite)

# Start the API
uvicorn main:app --reload --port 8000
# Docs: http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/simulate` | Single run + Observer analysis |
| POST | `/multiverse` | Multi-branch simulation + comparison report |
| POST | `/characters/build` | LLM persona builder from natural language |

---

## How It Works

### Persona System
Each character is defined with traits, values, communication style, emotional triggers, and goals. These are compiled into a system prompt that keeps the LLM agent in character. Traits are also embedded and stored in ChromaDB for memory recall.

### Simulation Engine (LangGraph)
A stateful graph alternates speaking turns between personas. Each turn: (1) recalls relevant memories, (2) builds a compact prompt, (3) invokes Gemini with rate limiting, (4) stores the exchange as a new memory. Falls back to HuggingFace if Gemini quota is hit.

### Observer Agent
After the dialogue completes, the Observer analyses the full log and returns: per-turn sentiment scores (−1 to +1), relationship trajectory, per-persona goal success probabilities (0–1), outcome category (Best/Most Likely/Worst Case), key turning points, and actionable recommendations.

### Multiverse Engine
Runs each decision branch sequentially (safe for free-tier rate limits), applies the Observer to each, then generates a comparison report ranking all branches by average goal success probability.

### Frontend Dashboard
A 3-step wizard: Character Builder → Scenario Setup → Results. Results are displayed across tabs including an interactive React Flow decision tree, sentiment-annotated dialogue, and the comparison report.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Primary LLM | Gemini 2.5 Flash |
| Fallback LLM | Qwen 2.5 7B via HuggingFace |
| Orchestration | LangGraph + LangChain |
| Vector DB | ChromaDB (local persistent) |
| Embeddings | Gemini Embedding 001 |
| API | FastAPI + Uvicorn |
| Frontend | Next.js 14 + React Flow + Tailwind |
