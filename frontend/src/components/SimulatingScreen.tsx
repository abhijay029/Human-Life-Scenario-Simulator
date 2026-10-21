'use client'
import { useEffect, useState } from 'react'
import type { DialogueTurn, SimMode } from '@/lib/types'
import DialogueViewer from './DialogueViewer'

const SINGLE_STEPS = [
  'Initialising persona agents…',
  'Loading character memories from vector store…',
  'Building simulation graph with LangGraph…',
  'Running dialogue turns…',
  'Observer Agent analysing outcomes…',
  'Generating sentiment scores…',
  'Compiling final report…',
]

const MULTI_STEPS = [
  'Initialising persona agents…',
  'Loading character memories from vector store…',
  'Spawning decision branches…',
  'Simulating Branch A…',
  'Simulating Branch B…',
  'Simulating Branch C…',
  'Observer Agent scoring each branch…',
  'Ranking outcomes by success probability…',
  'Generating comparison report…',
]

export default function SimulatingScreen({
  mode,
  decisionPoint,
  liveDialogue,
  liveBranches,
}: {
  mode: SimMode
  decisionPoint: string
  liveDialogue: DialogueTurn[]
  liveBranches: Record<string, DialogueTurn[]>
}) {
  const steps = mode === 'multiverse' ? MULTI_STEPS : SINGLE_STEPS
  const [currentStep, setCurrentStep] = useState(0)
  const [dots, setDots] = useState('.')
  const observer = useObserverStream(sessionId ?? null)

  useEffect(() => {
    const stepInterval = setInterval(() => {
      setCurrentStep((s) => Math.min(s + 1, steps.length - 1))
    }, mode === 'multiverse' ? 4000 : 3000)
    return () => clearInterval(stepInterval)
  }, [steps.length, mode])

  useEffect(() => {
    const dotInterval = setInterval(() => {
      setDots((d) => (d.length >= 3 ? '.' : d + '.'))
    }, 500)
    return () => clearInterval(dotInterval)
  }, [])

  const latestObs = observer.observations.length > 0
    ? observer.observations[observer.observations.length - 1]
    : null

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8 max-w-xl mx-auto px-4">
      {/* Animated core */}
      <div className="relative w-20 h-20">
        {/* Outer ring */}
        <div
          className="absolute inset-0 rounded-full border-2 border-cyan/20 animate-spin"
          style={{ animationDuration: '3s' }}
        />
        {/* Inner ring */}
        <div
          className="absolute inset-2.5 rounded-full border border-cyan/40 animate-spin"
          style={{ animationDuration: '1.5s', animationDirection: 'reverse' }}
        />
        {/* Core dot */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-5 h-5 rounded-full bg-cyan/20 border border-cyan/60 neon-pulse" />
        </div>
      </div>

      {/* Status */}
      <div className="text-center space-y-2">
        <p className="font-display text-xl font-bold text-text-primary">
          {mode === 'multiverse' ? 'Simulating Multiverse' : 'Running Simulation'}
          {dots}
        </p>
        <p className="text-xs font-mono text-text-secondary tracking-wide">
          Personas are deliberating. Observer Agent evaluates each turn in real time.
        </p>
      </div>

      {/* Live Observer Real-Time Stream Card (if observations are arriving) */}
      {latestObs && (
        <div className="w-full bg-zinc-950 border border-cyan/30 rounded-lg p-4 shadow-lg stagger-child">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-2">
            <div className="flex items-center gap-2">
              <Activity size={13} className="text-cyan animate-pulse" />
              <span className="text-xs font-mono font-bold text-cyan tracking-wider uppercase">
                Live Observer Telemetry — Turn {latestObs.turn_index + 1}
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-400">
              <Wifi size={10} className="text-green-400 animate-pulse" />
              <span>Streaming</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-xs">
              <span className="font-mono font-bold text-zinc-200">{latestObs.speaker}:</span>
              <span
                className={clsx(
                  'font-mono px-1.5 py-0.5 rounded text-[10px]',
                  latestObs.sentiment === 'positive' && 'bg-green-500/10 text-green-400 border border-green-500/20',
                  latestObs.sentiment === 'negative' && 'bg-red-500/10 text-red-400 border border-red-500/20',
                  latestObs.sentiment === 'neutral' && 'bg-zinc-800 text-zinc-400'
                )}
              >
                {latestObs.sentiment} ({latestObs.sentiment_score > 0 ? '+' : ''}{latestObs.sentiment_score.toFixed(2)})
              </span>
            </div>

            {latestObs.key_event && (
              <p className="text-xs text-amber-400 font-body italic">
                ⚡ {latestObs.key_event}
              </p>
            )}

            {latestObs.emotion_labels?.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {latestObs.emotion_labels.map((e) => (
                  <span key={e} className="text-[9px] font-mono text-zinc-400 bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded">
                    {e}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step log */}
      <div className="w-full max-w-sm space-y-2">
        {steps.map((step, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 px-4 py-2 rounded transition-all duration-500 ${
              i < currentStep
                ? 'opacity-40'
                : i === currentStep
                ? 'bg-cyan/5 border border-cyan/15'
                : 'opacity-20'
            }`}
          >
            <div
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                i < currentStep
                  ? 'bg-green-good'
                  : i === currentStep
                  ? 'bg-cyan neon-pulse'
                  : 'bg-border'
              }`}
            />
            <p
              className={`text-xs font-mono ${
                i === currentStep ? 'text-cyan' : 'text-text-secondary'
              }`}
            >
              {step}
            </p>
          </div>
        ))}
      </div>

      {(liveDialogue.length > 0 || Object.keys(liveBranches).length > 0) && (
        <div className="w-full max-w-3xl space-y-6 text-left">
          {mode === 'single' ? (
            <DialogueViewer
              log={liveDialogue}
              decisionPoint={decisionPoint}
              label="Live dialogue"
            />
          ) : (
            Object.entries(liveBranches).map(([branchId, log], index) => (
              <DialogueViewer
                key={branchId}
                log={log}
                decisionPoint={decisionPoint}
                label={`Branch ${String.fromCharCode(65 + index)} · Live dialogue`}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}
