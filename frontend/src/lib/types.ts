// ── Persona ────────────────────────────────────────────────────────────────
export interface PersonaSchema {
  name: string
  age: number
  occupation: string
  personality_traits: string[]
  values: string[]
  communication_style: string
  emotional_triggers: string[]
  background: string
  goals: string[]
}

// ── Observer Analysis ──────────────────────────────────────────────────────
export interface TurnSentiment {
  turn: number
  speaker: string
  sentiment: 'positive' | 'neutral' | 'negative'
  score: number
  note: string
}

export interface PersonaGoalSuccess {
  persona: string
  goal_summary: string
  success_probability: number
  reasoning: string
}

export interface ObserverAnalysis {
  turn_sentiments: TurnSentiment[]
  relationship_trajectory: 'improving' | 'stable' | 'deteriorating'
  trajectory_explanation: string
  persona_goal_success: PersonaGoalSuccess[]
  outcome_category: 'Best Case' | 'Most Likely' | 'Worst Case'
  outcome_summary: string
  key_turning_points: string[]
  recommendations: string[]
}

// ── Simulation ─────────────────────────────────────────────────────────────
export interface DialogueTurn {
  speaker: string
  message: string
}

export interface SimulationResponse {
  scenario: string
  decision_point: string
  dialogue_log: DialogueTurn[]
  analysis?: ObserverAnalysis
}

// ── Multiverse ─────────────────────────────────────────────────────────────
export interface BranchSummary {
  decision_point: string
  outcome_category?: string
  avg_success_probability: number
}

export interface ComparisonReport {
  best_case: BranchSummary & { outcome_summary?: string }
  worst_case: BranchSummary & { outcome_summary?: string }
  most_likely: BranchSummary & { outcome_summary?: string }
  all_branches_ranked: BranchSummary[]
}

export interface MultiverseResponse {
  scenario: string
  branches: SimulationResponse[]
  comparison_report: ComparisonReport
}

// ── Character Builder ──────────────────────────────────────────────────────
export interface BuildPersonaResponse {
  persona: PersonaSchema
  system_prompt_preview: string
}

// ── App State ──────────────────────────────────────────────────────────────
export type AppStep = 'build' | 'simulate' | 'results'

export type SimMode = 'single' | 'multiverse'
