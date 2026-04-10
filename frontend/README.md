# HLSS Frontend — Next.js Dashboard

Visual dashboard for the Human Life Scenario Simulator.

## Stack
- **Next.js 14** (App Router)
- **React Flow** — interactive decision tree visualization
- **Framer Motion** — animations
- **Tailwind CSS** — styling with custom design tokens
- **TypeScript** — fully typed

## Design
Dark sci-fi / mission-control aesthetic:
- Deep void blacks with electric cyan accents
- Space Mono (monospace data) + Syne (display) + DM Sans (body)
- Scanline overlay, dot-grid background, neon glow effects
- Animated sentiment indicators per dialogue turn

## Setup

```bash
# From the frontend/ directory:
npm install
npm run dev
# → http://localhost:3000
```

The backend must be running at port 8000 (requests are proxied via next.config.js).

## Pages / Flow

1. **Character Builder** (`/`) — Build 2+ personas manually or via AI Quick Build
2. **Scenario Setup** — Define scenario + pick Single Run or Multiverse mode
3. **Simulating** — Animated progress screen while backend runs
4. **Results** — Tabbed view:
   - *Single mode*: Dialogue log + Observer Analysis
   - *Multiverse mode*: Comparison Report · Decision Tree · Per-branch Dialogue + Analysis

## Folder Structure

```
src/
├── app/
│   ├── globals.css       # Design system: fonts, colors, animations
│   ├── layout.tsx
│   └── page.tsx          # Main app orchestrator
├── components/
│   ├── ui.tsx            # Primitives: Panel, Button, Input, TagInput, etc.
│   ├── CharacterBuilder.tsx
│   ├── ScenarioSetup.tsx
│   ├── SimulatingScreen.tsx
│   ├── ResultsView.tsx
│   ├── DialogueViewer.tsx
│   ├── AnalysisPanel.tsx
│   ├── DecisionTree.tsx
│   └── ComparisonReport.tsx
└── lib/
    ├── types.ts           # TypeScript types mirroring backend schemas
    └── api.ts             # Typed API client for FastAPI backend
```

## API Proxy
`next.config.js` proxies `/api/*` → `http://localhost:8000/*` so no CORS issues in dev.
