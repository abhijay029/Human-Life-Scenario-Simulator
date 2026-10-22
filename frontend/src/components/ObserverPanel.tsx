'use client'
import { useState } from 'react'
import type { ObserverSSEState, ConversationScorecard } from '@/lib/types'
import { Panel, ProgressBar } from './ui'
import TrajectoryChart from './TrajectoryChart'
import {
  Activity, TrendingUp, TrendingDown, Minus,
  AlertTriangle, Lightbulb, Wifi, WifiOff,
  ChevronDown, ChevronRight,
} from 'lucide-react'
import { clsx } from 'clsx'

// ── Helpers ────────────────────────────────────────────────────────────────

function sentimentColor(s: string) {
  if (s === 'positive') return 'text-green-400'
  if (s === 'negative') return 'text-red-400'
  return 'text-zinc-400'
}

function sentimentDot(s: string) {
  if (s === 'positive') return 'bg-green-400 shadow-[0_0_5px_rgba(74,222,128,0.5)]'
  if (s === 'negative') return 'bg-red-400 shadow-[0_0_5px_rgba(248,113,113,0.5)]'
  return 'bg-zinc-500'
}

function TrajectoryLabel({ label }: { label: string }) {
  if (label === 'improving') return <TrendingUp size={12} className="text-green-400" />
  if (label === 'deteriorating') return <TrendingDown size={12} className="text-red-400" />
  return <Minus size={12} className="text-zinc-500" />
}

// ── Scorecard ──────────────────────────────────────────────────────────────

const METRIC_LABELS: Record<string, string> = {
  persona_consistency: 'Persona Consistency',
  emotional_realism: 'Emotional Realism',
  conversational_coherence: 'Conversational Coherence',
  goal_alignment: 'Goal Alignment',
  conflict_realism: 'Conflict Realism',
  social_plausibility: 'Social Plausibility',
  overall_realism: 'Overall Realism',
}

function ScorecardView({ sc }: { sc: ConversationScorecard }) {
  const metrics = Object.entries(METRIC_LABELS).map(([key, label]) => ({
    key,
    label,
    value: sc[key as keyof ConversationScorecard] as number,
  }))

  return (
    <div className="space-y-4">
      {sc.summary && (
        <p className="text-xs text-zinc-400 font-body italic">{sc.summary}</p>
      )}

      {/* Realism metrics */}
      <div className="space-y-2.5">
        {metrics.map(({ key, label, value }) => (
          <div key={key}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-mono text-zinc-400">{label}</span>
              <span
                className={clsx(
                  'text-[11px] font-mono font-bold',
                  value >= 8 ? 'text-green-400' : value >= 6 ? 'text-amber-400' : 'text-red-400'
                )}
              >
                {value.toFixed(1)}
              </span>
            </div>
            <ProgressBar value={value / 10} />
          </div>
        ))}
      </div>

      {/* Turning points */}
      {sc.key_turning_points.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-mono text-zinc-500 tracking-wider uppercase">Key Turning Points</p>
          {sc.key_turning_points.map((pt, i) => (
            <div key={i} className="flex items-start gap-2">
              <AlertTriangle size={10} className="text-amber-400 mt-0.5 flex-shrink-0" />
              <p className="text-[11px] text-zinc-400 font-body leading-snug">{pt}</p>
            </div>
          ))}
        </div>
      )}

      {/* Recommendations */}
      {sc.recommendations.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-mono text-zinc-500 tracking-wider uppercase">Recommendations</p>
          {sc.recommendations.map((r, i) => (
            <div key={i} className="flex items-start gap-2">
              <Lightbulb size={10} className="text-cyan-400 mt-0.5 flex-shrink-0" />
              <p className="text-[11px] text-zinc-300 font-body leading-snug">{r}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Dyad Section ───────────────────────────────────────────────────────────

function DyadSection({
  pairKey,
  trajectories,
}: {
  pairKey: string
  trajectories: ObserverSSEState['trajectories']
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="rounded border border-zinc-800 overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-3 py-2 bg-zinc-900 hover:bg-zinc-800 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="text-[11px] font-mono text-zinc-300">{pairKey}</span>
        {open ? <ChevronDown size={12} className="text-zinc-500" /> : <ChevronRight size={12} className="text-zinc-500" />}
      </button>
      {open && (
        <div className="p-3">
          <TrajectoryChart trajectories={trajectories} pairKey={pairKey} />
        </div>
      )}
    </div>
  )
}

// ── Main ObserverPanel ─────────────────────────────────────────────────────

export default function ObserverPanel({ observer }: { observer: ObserverSSEState }) {
  const { observations, trajectories, scorecard, connected, finalized } = observer
  const [tab, setTab] = useState<'live' | 'scorecard'>('live')

  // Get all unique dyad pair keys from trajectories
  const pairKeys = Array.from(new Set(trajectories.map((t) => t.dyad_pair)))

  const hasData = observations.length > 0 || trajectories.length > 0

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex items-center gap-3 px-3 py-2 rounded border border-zinc-800 bg-zinc-900">
        <div className="flex items-center gap-2">
          {connected ? (
            <Wifi size={12} className="text-green-400 animate-pulse" />
          ) : finalized ? (
            <Activity size={12} className="text-cyan-400" />
          ) : (
            <WifiOff size={12} className="text-zinc-500" />
          )}
          <span className="text-[11px] font-mono text-zinc-400">
            {connected ? 'Observing live…' : finalized ? 'Analysis complete' : 'Connecting…'}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] font-mono text-zinc-600">
            {observations.length} turn{observations.length !== 1 ? 's' : ''} observed
          </span>
        </div>
      </div>

      {!hasData && !finalized && (
        <div className="flex flex-col items-center justify-center py-12 text-center gap-2">
          <Activity size={24} className="text-zinc-700 animate-pulse" />
          <p className="text-xs text-zinc-500 font-mono">Waiting for simulation to start…</p>
          <p className="text-[10px] text-zinc-700 font-body">
            Observer will analyze each turn in real time
          </p>
        </div>
      )}

      {hasData && (
        <>
          {/* Tab switcher */}
          {finalized && scorecard && (
            <div className="flex border-b border-zinc-800">
              {(['live', 'scorecard'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={clsx(
                    'px-4 py-2 text-xs font-mono border-b-2 transition-all',
                    tab === t
                      ? 'border-cyan-400 text-cyan-400'
                      : 'border-transparent text-zinc-500 hover:text-zinc-300'
                  )}
                >
                  {t === 'live' ? 'Trajectories' : 'Scorecard'}
                </button>
              ))}
            </div>
          )}

          {/* Live trajectories tab */}
          {tab === 'live' && (
            <div className="space-y-3">
              {/* Per-turn observations timeline */}
              {observations.length > 0 && (
                <Panel label="Turn-by-Turn Observations" className="p-3">
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {observations.map((obs) => (
                      <div
                        key={obs.turn_index}
                        className={clsx(
                          'flex items-start gap-2.5 p-2 rounded border text-xs transition-all',
                          obs.degraded
                            ? 'border-zinc-800 bg-zinc-900/50'
                            : 'border-zinc-800 bg-zinc-950'
                        )}
                      >
                        <span className="text-[10px] font-mono text-zinc-600 w-4 flex-shrink-0 mt-0.5">
                          {obs.turn_index + 1}
                        </span>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          <div className={clsx('w-1.5 h-1.5 rounded-full', sentimentDot(obs.sentiment))} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="font-mono font-bold text-zinc-300 text-[11px]">{obs.speaker}</span>
                            <span className={clsx('text-[10px] font-mono', sentimentColor(obs.sentiment))}>
                              {obs.sentiment} ({obs.sentiment_score > 0 ? '+' : ''}{obs.sentiment_score.toFixed(2)})
                            </span>
                            {obs.degraded && (
                              <span className="text-[9px] font-mono text-amber-500 border border-amber-500/30 px-1 rounded">
                                degraded
                              </span>
                            )}
                          </div>
                          {obs.emotion_labels.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {obs.emotion_labels.map((e) => (
                                <span key={e} className="text-[9px] font-mono text-zinc-500 border border-zinc-800 px-1 rounded">
                                  {e}
                                </span>
                              ))}
                            </div>
                          )}
                          {obs.key_event && (
                            <p className="text-[10px] text-amber-400 font-body italic mt-0.5 truncate">
                              ⚡ {obs.key_event}
                            </p>
                          )}
                        </div>
                        <div className="flex-shrink-0">
                          <TrajectoryLabel label={obs.sentiment === 'positive' ? 'improving' : obs.sentiment === 'negative' ? 'deteriorating' : 'stable'} />
                        </div>
                      </div>
                    ))}
                  </div>
                </Panel>
              )}

              {/* Dyad trajectory charts */}
              {pairKeys.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[10px] font-mono text-zinc-500 tracking-wider uppercase px-1">
                    Relationship Trajectories
                  </p>
                  {pairKeys.map((pk) => (
                    <DyadSection key={pk} pairKey={pk} trajectories={trajectories} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Scorecard tab */}
          {tab === 'scorecard' && scorecard && (
            <Panel label="Conversation Scorecard" className="p-4">
              <ScorecardView sc={scorecard} />
            </Panel>
          )}
        </>
      )}
    </div>
  )
}
