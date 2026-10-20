// Observer Agent API client
// Connects to FastAPI /observer/* endpoints

const BASE = 'http://localhost:8000'

export async function createObserverSession(
  sessionId: string,
  participants: string[],
  scenarioDescription: string
): Promise<void> {
  await fetch(`${BASE}/observer/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      participants,
      scenario_description: scenarioDescription,
    }),
  })
}

export async function finalizeObserverSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/observer/sessions/${sessionId}/finalize`, {
    method: 'POST',
  })
}

export function openObserverStream(sessionId: string): EventSource {
  return new EventSource(`${BASE}/observer/sessions/${sessionId}/stream`)
}
