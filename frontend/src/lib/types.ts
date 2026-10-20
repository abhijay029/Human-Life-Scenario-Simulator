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
  session_id?: string
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

// ── Observer Agent (real-time) ──────────────────────────────────────────────

export interface DyadState {
  from_party: string
  to_party: string
  trust: number
  rapport: number
  tension: number
  respect: number
  power_balance: number
}

export interface TurningPoint {
  turn_index: number
  dimension: string
  delta: number
  value_after: number
  reason: string
}

export interface TurnObservation {
  session_id: string
  turn_index: number
  speaker: string
  sentiment: 'positive' | 'neutral' | 'negative'
  sentiment_score: number
  emotion_labels: string[]
  dyad_deltas: Record<string, Record<string, number>>
  dyad_states: DyadState[]
  key_event: string | null
  confidence: number
  degraded: boolean
  timestamp: number
}

export interface TrajectorySummary {
  dyad_pair: string
  dimension: string
  start: number
  current: number
  min_value: number
  max_value: number
  slope: number
  label: 'improving' | 'stable' | 'deteriorating'
  turning_points: TurningPoint[]
  /** Full per-turn value history (index 0 = initial state) */
  history: number[]
}

export interface ConversationScorecard {
  session_id: string
  persona_consistency: number
  emotional_realism: number
  conversational_coherence: number
  goal_alignment: number
  conflict_realism: number
  social_plausibility: number
  overall_realism: number
  goal_success: Record<string, number>
  outcome_category: 'Best Case' | 'Most Likely' | 'Worst Case'
  key_turning_points: string[]
  recommendations: string[]
  summary: string
}

export interface ObserverSSEState {
  observations: TurnObservation[]
  trajectories: TrajectorySummary[]
  scorecard: ConversationScorecard | null
  connected: boolean
  finalized: boolean
}
