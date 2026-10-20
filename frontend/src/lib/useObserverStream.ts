'use client'
import { useEffect, useRef, useState, useCallback } from 'react'
import type { ObserverSSEState, TurnObservation, TrajectorySummary, ConversationScorecard } from '@/lib/types'
import { openObserverStream } from '@/lib/observerApi'

const BASE = 'http://localhost:8000'

const INITIAL_STATE: ObserverSSEState = {
  observations: [],
  trajectories: [],
  scorecard: null,
  connected: false,
  finalized: false,
}

/**
 * Hook that opens an SSE connection to the Observer Agent stream for a given
 * session and also performs REST hydration so the UI never gets stuck on
 * "waiting for simulation to start".
 */
export function useObserverStream(sessionId: string | null) {
  const [state, setState] = useState<ObserverSSEState>(INITIAL_STATE)
  const esRef = useRef<EventSource | null>(null)

  // REST fallback / hydration function
  const hydrateFromRest = useCallback(async () => {
    if (!sessionId) return
    try {
      const [obsRes, trajRes, scRes] = await Promise.allSettled([
        fetch(`${BASE}/observer/sessions/${sessionId}/observations`).then((r) => r.ok ? r.json() : null),
        fetch(`${BASE}/observer/sessions/${sessionId}/trajectory`).then((r) => r.ok ? r.json() : null),
        fetch(`${BASE}/observer/sessions/${sessionId}/scorecard`).then((r) => r.ok ? r.json() : null),
      ])

      setState((prev) => {
        const next = { ...prev }
        if (obsRes.status === 'fulfilled' && obsRes.value?.observations?.length > 0) {
          next.observations = obsRes.value.observations
        }
        if (trajRes.status === 'fulfilled' && trajRes.value?.trajectories?.length > 0) {
          next.trajectories = trajRes.value.trajectories
        }
        if (scRes.status === 'fulfilled' && scRes.value) {
          next.scorecard = scRes.value
          next.finalized = true
        }
        return next
      })
    } catch {}
  }, [sessionId])

  const connect = useCallback(() => {
    if (!sessionId) return
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    const es = openObserverStream(sessionId)
    esRef.current = es

    es.addEventListener('open', () => {
      setState((s) => ({ ...s, connected: true }))
    })

    es.addEventListener('observation', (e: MessageEvent) => {
      try {
        const obs: TurnObservation = JSON.parse(e.data)
        setState((s) => ({
          ...s,
          observations: [...s.observations.filter((o) => o.turn_index !== obs.turn_index), obs].sort(
            (a, b) => a.turn_index - b.turn_index
          ),
        }))
      } catch {}
    })

    es.addEventListener('trajectory', (e: MessageEvent) => {
      try {
        const { trajectories }: { trajectories: TrajectorySummary[] } = JSON.parse(e.data)
        setState((s) => ({ ...s, trajectories }))
      } catch {}
    })

    es.addEventListener('final', (e: MessageEvent) => {
      try {
        const scorecard: ConversationScorecard = JSON.parse(e.data)
        setState((s) => ({ ...s, scorecard, finalized: true, connected: false }))
      } catch {}
      es.close()
      esRef.current = null
    })

    es.addEventListener('error', () => {
      setState((s) => ({ ...s, connected: false }))
      es.close()
      esRef.current = null
      // Try REST hydration if SSE connection closed or failed
      hydrateFromRest()
    })
  }, [sessionId, hydrateFromRest])

  useEffect(() => {
    if (!sessionId) return
    setState(INITIAL_STATE)
    hydrateFromRest()
    connect()
    return () => {
      esRef.current?.close()
      esRef.current = null
    }
  }, [sessionId, connect, hydrateFromRest])

  return state
}
