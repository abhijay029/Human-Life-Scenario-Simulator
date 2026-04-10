import type {
  PersonaSchema,
  SimulationResponse,
  MultiverseResponse,
  BuildPersonaResponse,
} from './types'

const BASE = '/api'

// 8 minutes — enough for multiverse with Observer pauses
const TIMEOUT_MS = 8 * 60 * 1000

async function post<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? `HTTP ${res.status}`)
    }
    return res.json() as Promise<T>
  } catch (e: unknown) {
    if (e instanceof Error && e.name === 'AbortError') {
      throw new Error('Request timed out. The simulation is taking too long — try fewer turns.')
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export async function buildPersona(description: string): Promise<BuildPersonaResponse> {
  return post('/characters/build', { description })
}

export async function runSimulation(params: {
  personas: PersonaSchema[]
  scenario: string
  decision_point: string
  max_turns?: number
  store_memories?: boolean
}): Promise<SimulationResponse> {
  return post('/simulate', params)
}

export async function runMultiverse(params: {
  personas: PersonaSchema[]
  scenario: string
  decision_branches: string[]
  max_turns?: number
  store_memories?: boolean
}): Promise<MultiverseResponse> {
  return post('/multiverse', params)
}

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}
