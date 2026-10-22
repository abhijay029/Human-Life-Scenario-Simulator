'use client'
import { useEffect, useRef, useState, useCallback } from 'react'
import type { ObserverSSEState, ConversationScorecard } from '@/lib/types'
import { openObserverStream } from '@/lib/observerApi'

const BASE = 'http://localhost:8000'

const INITIAL_STATE: ObserverSSEState = {
  scorecard: null,
}

/** Subscribe only to final Observer scorecard results. */
export function useObserverStream(sessionId: string | null) {
  const [state, setState] = useState<ObserverSSEState>(INITIAL_STATE)
  const esRef = useRef<EventSource | null>(null)

  const hydrateFromRest = useCallback(async () => {
    if (!sessionId) return
    try {
      const response = await fetch(`${BASE}/observer/sessions/${sessionId}/scorecard`)
      if (!response.ok) return
      const scorecard: ConversationScorecard = await response.json()
      setState({ scorecard })
    } catch {}
  }, [sessionId])

  const connect = useCallback(() => {
    if (!sessionId) return
    esRef.current?.close()

    const es = openObserverStream(sessionId)
    esRef.current = es

    es.addEventListener('final', (e: MessageEvent) => {
      try {
        const scorecard: ConversationScorecard = JSON.parse(e.data)
        setState({ scorecard })
      } catch {}
      es.close()
      esRef.current = null
    })

    es.addEventListener('error', () => {
      es.close()
      esRef.current = null
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
