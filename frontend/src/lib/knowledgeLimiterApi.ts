export type Level = 'layperson' | 'basic' | 'advanced' | 'expert'
export type Tone = 'casual' | 'debate' | 'discussion'
export type BoundaryBehavior = 'admit' | 'bluff' | 'deflect' | 'ask_back' | 'analogize'

export interface KLConcept {
  term: string
  min_level: Level
}

export interface KLBriefFact {
  text: string
  min_level: Level // lowest persona level allowed to use this fact
}

export interface KLBriefSource {
  title: string
  url: string
}

export interface KLTopicBrief {
  facts: KLBriefFact[]
  sources: KLBriefSource[]
  grounded: boolean // true only if web search results backed this brief
}

export interface KLTopic {
  id: string
  name: string
  domain: string
  concepts: KLConcept[]
  levels: Record<string, Level> // persona_id -> Level
  brief?: KLTopicBrief | null
}

export interface KLPersona {
  id: string
  name: string
  profession: string
  personality: {
    traits: string[]
    speech_style: string
    boundary_behavior: BoundaryBehavior
  }
  default_level: Level
  own_domain: string
  background_summary: string
}

export interface KnowledgeConfig {
  scenario_id: string
  per_persona: Record<string, Record<string, Level>>
  concept_lexicon: Record<string, { domain: string; min_level: Level }>
  expert_briefs?: Record<string, KLBriefFact[]> // domain -> facts, gated by level at chat time
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function generateKLTopics(params: {
  scenario_description: string
  tone: Tone
  personas: { name: string; profession: string; background_summary: string }[]
  /** Decision point (single run) or decision branches (multiverse) being explored. */
  decision_points?: string[]
}): Promise<{ topics: KLTopic[] }> {
  const res = await fetch(`${API_BASE}/kl/topics/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const errorText = await res.text()
    throw new Error(`Failed to generate topics: ${errorText}`)
  }
  return res.json()
}

export async function saveKnowledgeConfig(params: {
  scenario_id: string
  personas: KLPersona[]
  topics: KLTopic[]
}): Promise<{ knowledge_config: KnowledgeConfig; message: string }> {
  const res = await fetch(`${API_BASE}/kl/config/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const errorText = await res.text()
    throw new Error(`Failed to save knowledge config: ${errorText}`)
  }
  return res.json()
}

/**
 * Research expert briefs (web-grounded) for topics where a persona is advanced/expert.
 * The server searches using only each topic's name, domain and key concepts.
 */
export async function generateKLBriefs(topics: KLTopic[]): Promise<{
  briefs: Record<string, KLTopicBrief>
  errors: Record<string, string>
  skipped: string[]
}> {
  const res = await fetch(`${API_BASE}/kl/briefs/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topics }),
  })
  if (!res.ok) {
    const errorText = await res.text()
    throw new Error(`Failed to research briefs: ${errorText}`)
  }
  return res.json()
}
